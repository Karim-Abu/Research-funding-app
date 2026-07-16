"""Draft-Stage-Orchestrierung des normalen Laufs (Milestone 6 + A2-Anbindung).

create_template_drafts (deterministische Templates aus unveränderlichen
Run-Inputs) und run_a2_field_suggestions (advisory A2-Vorschläge je Feld über
den bestehenden Redraft-Kern). A2 schreibt NUR DraftSuggestions (proposed) —
nie DraftVersions, nie Auto-Übernahme. Upsert-only; der Aufrufer besitzt die
Transaktion (der A2-Kern committet je Feld-Operation selbst).
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents import field_drafting
from app.agents.a2_fields import A2_FIELD_PROFILES
from app.db.models import (
    AgentInvocation,
    AnalysisRun,
    AsyncOperation,
    PortalFieldDraft,
    RunPolicySnapshot,
    UsageRecord,
)
from app.registry import get_registry
from app.repositories import audit, controls
from app.repositories import drafts as drafts_repo

# Statuses, die als verbrauchter LLM-Call gegen das Run-Budget zählen —
# identisch zur CostGuard-Zählung je Profil (cost_guard._COUNTED_STATUSES).
_COUNTED_STATUSES = ("queued", "running", "succeeded", "failed", "timed_out")


def record_a2_skipped(db: Session, run: AnalysisRun, reason: str) -> None:
    """draft_fields stage: die A2-Route läuft in diesem Lauf nicht (Modus ohne
    KI-Freigabe) — Contract-Control mit ehrlichem Grund, kein Provider-Call."""
    controls.record(
        db, workspace_id=run.workspace_id, project_id=run.project_id,
        source_id=None, control_id="CTRL.DATA_POLICY", status="passed",
        detail=f"a2_skipped {reason}",
    )
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None,
        action="draft.fields_a2_skipped", target_type="run", target_id=run.run_id,
        detail={"reason": reason},
    )


def create_template_drafts(db: Session, run: AnalysisRun) -> int:
    """Create one PortalFieldDraft + initial template DraftVersion per supported
    field, idempotently, from the immutable run inputs + versioned registry."""
    registry = get_registry()
    fields = registry.m6_draft_fields()
    for field in fields:
        drafts_repo.create_initial_draft(db, run, field)
    controls.record(
        db, workspace_id=run.workspace_id, project_id=run.project_id,
        source_id=None, control_id="CTRL.RUN_SNAPSHOT_SCOPE", status="passed",
        detail=f"template_catalog={drafts_repo.TEMPLATE_CATALOG_VERSION} fields={len(fields)}",
    )
    controls.record(
        db, workspace_id=run.workspace_id, project_id=run.project_id,
        source_id=None, control_id="CTRL.OUTPUT_SCHEMA", status="passed",
        detail="portal_field_draft",
    )
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None,
        action="draft.stage_completed", target_type="run", target_id=run.run_id,
        detail={"drafts": len(fields)},
    )
    return len(fields)


def _llm_calls_used(db: Session, run_id: str) -> int:
    return db.scalar(
        select(func.count(AgentInvocation.invocation_id)).where(
            AgentInvocation.run_id == run_id,
            AgentInvocation.status.in_(_COUNTED_STATUSES),
        )
    ) or 0


def _priced_cost_chf(db: Session, run_id: str) -> float:
    # Nur cost_status='priced' summieren — unknown_price/not_applicable dürfen
    # nie als «gratis» in eine Summe einfliessen (EVAL.1-Semantik).
    return db.scalar(
        select(func.coalesce(func.sum(UsageRecord.cost_chf), 0.0)).where(
            UsageRecord.run_id == run_id,
            UsageRecord.cost_status == "priced",
        )
    ) or 0.0


def budget_stop_reason(
    db: Session, run: AnalysisRun, policy: RunPolicySnapshot | None
) -> str | None:
    """Run-Budget-Gate aus dem eingefrorenen Policy-Snapshot: Anzahl LLM-Calls
    und (soweit bepreist) Kosten. None = weiterer Agent-Call zulässig."""
    if policy is None:
        return None
    if _llm_calls_used(db, run.run_id) >= policy.max_llm_calls:
        return "llm_budget_exhausted"
    if policy.max_cost_chf > 0 and _priced_cost_chf(db, run.run_id) >= policy.max_cost_chf:
        return "cost_budget_exhausted"
    return None


def run_a2_field_suggestions(db: Session, run: AnalysisRun) -> dict:
    """Advisory A2-Vorschläge für alle A2-fähigen Felder des Laufs.

    Je Feld eine echte AsyncOperation über den gemeinsamen Redraft-Kern
    (Owner-Entscheid) — dadurch bleibt der bestehende Annahme-Pfad unverändert.
    Vor jedem Call greift das Run-Budget-Gate (max_llm_calls/max_cost_chf aus
    dem RunPolicySnapshot). Feld-Fehler stoppen die übrigen Felder nicht
    (Partial Success). Rückgabe: Zähler-Dict fürs Phasendetail."""
    from app.fields import redraft_service

    policy = db.get(RunPolicySnapshot, run.run_id)
    counters: dict = {
        "suggestions_created": 0,
        "fields_failed": 0,
        "fields_skipped": 0,
        "field_reasons": {},
    }
    for field_id in A2_FIELD_PROFILES:
        draft = db.scalar(
            select(PortalFieldDraft).where(
                PortalFieldDraft.run_id == run.run_id,
                PortalFieldDraft.field_id == field_id,
            )
        )
        if draft is None or draft.current_version_id is None:
            counters["fields_skipped"] += 1
            counters["field_reasons"][field_id] = "no_draft"
            continue
        available, reason = field_drafting.availability(run, field_id)
        if not available:
            counters["fields_skipped"] += 1
            counters["field_reasons"][field_id] = reason
            continue
        config = field_drafting.a2_fields.resolve_field_config(field_id)
        targets: tuple[str | None, ...] = (
            tuple(config.mandatory_markers) if config and config.mandatory_markers
            else (None,)
        )
        for target_section in targets:
            reason_key = (
                f"{field_id}:{target_section}" if target_section else field_id
            )
            stop = budget_stop_reason(db, run, policy)
            if stop is not None:
                counters["budget_stop"] = stop
                counters["fields_skipped"] += 1
                counters["field_reasons"][reason_key] = stop
                continue
            operation = AsyncOperation(
                operation_id=str(uuid.uuid4()),
                workspace_id=run.workspace_id,
                project_id=run.project_id,
                resource_type="redraft",
                resource_id=draft.draft_id,
                status="queued",
            )
            db.add(operation)
            db.flush()
            outcome = redraft_service.execute_a2_operation(
                db, operation=operation, run=run, draft_id=draft.draft_id,
                base_version_id=draft.current_version_id, field_id=field_id,
                target_section=target_section,
            )
            if outcome.status in ("succeeded", "reused"):
                counters["suggestions_created"] += 1
            elif outcome.status == "skipped":
                counters["fields_skipped"] += 1
                counters["field_reasons"][reason_key] = outcome.reason
            else:
                counters["fields_failed"] += 1
                counters["field_reasons"][reason_key] = outcome.reason
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None,
        action="draft.fields_a2_completed", target_type="run",
        target_id=run.run_id,
        detail={
            "suggestions_created": counters["suggestions_created"],
            "fields_failed": counters["fields_failed"],
            "fields_skipped": counters["fields_skipped"],
        },
    )
    return counters
