"""Integrated draft runner (R5.9).

Drives the 8 supported Innolink draft fields (``registry.m6_draft_fields()``) for one F1
case: the 6 A2 fields go through the UNCHANGED ``run_a2_field_drafting`` orchestrator (fake
provider); the 2 name fields are filled deterministically (NAME ← project title, NAME_EN →
missing_inputs, no auto-translation). Usage is aggregated with the existing EVAL.1 helpers.
No new KI/research logic, no auto-accept, no submit.

Contract constraints handled without touching the frozen contract: ``analysis_runs`` has a
UNIQUE ``project_id`` (one run per project) AND ``A2.introduction_public_summary`` (used by
both ABSTRACT and EXECUTIVE_SUMMARY) has ``max_per_run=1``. So each A2 field runs in its own
child Project + AnalysisRun cloned from the base F1 project — every profile is invoked at
most once per run, and both intro fields can draft.
"""
from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents import a2_fields, field_drafting
from app.agents.field_drafting_context import retrieve_advisory_research_context
from app.db.models import (
    AgentInvocation,
    AnalysisRun,
    DraftVersion,
    PortalFieldDraft,
    Project,
    UsageRecord,
)
from app.drafts.templates import build_template
from app.evaluation.usage import run_usage_totals, usage_by_agent_task
from app.integrated_draft.package import DraftPackage, FieldDraftItem, classify_status
from app.registry.loader import get_registry

_MARKET_PROFILE = "A2.value_creation_market_logic"   # VC — consumes market research context
_PARTNER_PROFILE = "A2.solution_innovation"          # SOL — consumes partner research context

ResolverFor = Callable[[str], Callable] | None
# seed_context(db, field_id, child_project) — lets the caller seed advisory research context
# (market/partner candidates, imported D0 sources) onto the VC/SOL child projects.
SeedContext = Callable[[Session, str, Project], None] | None


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _slug(field_id: str) -> str:
    return field_id.lower().replace(".", "-")


def _clone_project(db: Session, base: Project, field_id: str) -> Project:
    child = Project(
        project_id=f"{base.project_id}-{_slug(field_id)}"[:120],
        workspace_id=base.workspace_id, title=base.title, description=base.description,
        innovation_field=base.innovation_field,
        funding_instrument_profile_id=base.funding_instrument_profile_id,
        data_classification=dict(base.data_classification or {}),
        created_by=base.created_by, status="draft",
    )
    db.add(child)
    db.flush()
    return child


def _new_run(db: Session, project: Project, actor_user_id: str) -> AnalysisRun:
    run = AnalysisRun(
        run_id="irun-" + uuid.uuid4().hex[:8], project_id=project.project_id,
        workspace_id=project.workspace_id, created_by=actor_user_id, status="running",
        current_stage="draft_fields", progress_percent=50, processing_mode="cloud_assisted",
        effective_data_classification=dict(project.data_classification or {}),
        snapshot_versions={},
    )
    db.add(run)
    db.flush()
    return run


def _seed_draft(db: Session, run: AnalysisRun, field, char_limit: int | None) -> tuple[str, str]:
    seed_text = build_template(field, get_registry())
    draft_id = "idraft-" + uuid.uuid4().hex[:8]
    version_id = "iver-" + uuid.uuid4().hex[:8]
    db.add(DraftVersion(
        draft_version_id=version_id, draft_id=draft_id, text=seed_text,
        character_count=len(seed_text), created_by="template", content_hash=_hash(seed_text),
    ))
    db.add(PortalFieldDraft(
        draft_id=draft_id, run_id=run.run_id, workspace_id=run.workspace_id,
        field_id=field.field_id, field_name=field.label_or_question, status="draft",
        character_limit=char_limit, current_version_id=version_id, open_issue_count=0,
        template_catalog_version="tpl-1",
    ))
    db.flush()
    return draft_id, version_id


def _deterministic_name_item(field, project: Project) -> FieldDraftItem:
    title = (project.title or "").strip()
    if not title:
        return FieldDraftItem(
            field_id=field.field_id, field_label=field.label_or_question,
            status="missing_inputs",
            missing_inputs=[{"label": "Antragstitel", "reason": "kein Projekttitel vorhanden"}],
            notes=["Deterministisch aus Projekttitel — Titel fehlt."],
        )
    return FieldDraftItem(
        field_id=field.field_id, field_label=field.label_or_question,
        status="deterministic", suggestion_text=title,
        notes=["Deterministisch aus dem Projekttitel übernommen (kein LLM)."],
    )


def _deterministic_name_en_item(field) -> FieldDraftItem:
    return FieldDraftItem(
        field_id=field.field_id, field_label=field.label_or_question,
        status="missing_inputs",
        missing_inputs=[{
            "label": "Englischer Antragstitel",
            "reason": "kein englischer Titel vorhanden; keine automatische Übersetzung",
        }],
        notes=["Kein englischer Titel; keine Auto-Übersetzung in diesem Ticket."],
    )


def _a2_item(
    db: Session, run: AnalysisRun, field, config, *, resolver_for: ResolverFor,
) -> FieldDraftItem:
    draft_id, version_id = _seed_draft(db, run, field, config.char_limit)
    resolver = resolver_for(field.field_id) if resolver_for else None
    outcome = field_drafting.run_a2_field_drafting(
        db, run, field_id=field.field_id, draft_id=draft_id, base_version_id=version_id,
        operation_id="iop-" + uuid.uuid4().hex[:8], provider_resolver=resolver,
    )
    view = outcome.view or {}
    proposal = view.get("ai_proposal") or {}
    missing = list(proposal.get("missing_inputs") or [])
    status, avail_note = classify_status(
        outcome.status, outcome.reason, has_missing_inputs=bool(missing),
    )
    item = FieldDraftItem(
        field_id=field.field_id, field_label=field.label_or_question, status=status,
        suggestion_text=view.get("suggested_text"),
        ai_proposal=proposal or None, missing_inputs=missing,
        provider=proposal.get("provider"), model=proposal.get("model"),
        usage_record_id=proposal.get("usage_record_id"),
    )
    if outcome.status not in ("succeeded", "reused"):
        item.notes.append(f"A2-Outcome: {outcome.status}/{outcome.reason}")
    if avail_note:
        item.notes.append(avail_note)
    if item.usage_record_id:
        rec = db.get(UsageRecord, item.usage_record_id)
        if rec is not None:
            item.input_tokens = rec.input_tokens
            item.output_tokens = rec.output_tokens
            item.total_tokens = (rec.input_tokens or 0) + (rec.output_tokens or 0)
            item.cost_status = rec.cost_status
    if outcome.invocation_id:
        inv = db.get(AgentInvocation, outcome.invocation_id)
        if inv is not None:
            item.latency_ms = inv.latency_ms
    return item


def _research_counts(rc: dict) -> dict:
    return {
        "used": bool(rc),
        "candidates": len(rc.get("candidates", [])),
        "imported_sources": len(rc.get("imported_sources", [])),
    }


def run_integrated_draft(
    db: Session,
    *,
    base_project: Project,
    actor_user_id: str,
    case_id: str,
    provider_mode: str = "fake",
    data_mode: str = "synthetic_eval",
    resolver_for: ResolverFor = None,
    seed_context: SeedContext = None,
) -> DraftPackage:
    """Run all 8 supported draft fields for the F1 case and return a DraftPackage.

    Each A2 field runs under its own child Project + AnalysisRun (cloned from
    ``base_project``) so no profile exceeds its contract max_per_run. ``resolver_for`` lets
    tests inject a per-field fake resolver (else the caller relies on
    ``settings.agent_fake_provider``). ``seed_context(db, field_id, child_project)`` lets the
    caller seed advisory research context onto the VC/SOL child projects. The package always
    requires human review and never marks anything final/copy-ready.
    """
    items: list[FieldDraftItem] = []
    a2_runs: list[AnalysisRun] = []
    market_run: AnalysisRun | None = None
    partner_run: AnalysisRun | None = None

    for field in get_registry().m6_draft_fields():
        config = a2_fields.resolve_field_config(field.field_id)
        if config is not None:
            child = _clone_project(db, base_project, field.field_id)
            run = _new_run(db, child, actor_user_id)
            if seed_context is not None:
                seed_context(db, field.field_id, child)
            a2_runs.append(run)
            if config.profile_id == _MARKET_PROFILE:
                market_run = run
            elif config.profile_id == _PARTNER_PROFILE:
                partner_run = run
            items.append(_a2_item(db, run, field, config, resolver_for=resolver_for))
        elif field.field_id == "INTRO.APP.NAME_EN":
            items.append(_deterministic_name_en_item(field))
        else:  # INTRO.APP.NAME (and any other non-A2 name-like field)
            items.append(_deterministic_name_item(field, base_project))

    research_summary = {
        "market": _research_counts(
            retrieve_advisory_research_context(db, market_run, _MARKET_PROFILE)
            if market_run else {}
        ),
        "partner": _research_counts(
            retrieve_advisory_research_context(db, partner_run, _PARTNER_PROFILE)
            if partner_run else {}
        ),
    }
    return DraftPackage(
        package_id="dpkg-" + uuid.uuid4().hex[:8],
        project_id=base_project.project_id,
        case_id=case_id,
        run_id=a2_runs[0].run_id if a2_runs else "",
        created_at=datetime.now(timezone.utc).isoformat(),
        provider_mode=provider_mode,
        data_mode=data_mode,
        fields=items,
        usage_summary=_usage_summary(db, a2_runs),
        research_summary=research_summary,
    )


def _usage_summary(db: Session, runs: list[AnalysisRun]) -> dict:
    input_t = output_t = urc = 0
    status_counts: dict[str, int] = {}
    by_profile: list[dict] = []
    for run in runs:
        totals = run_usage_totals(db, run.run_id)
        input_t += totals["input_tokens"]
        output_t += totals["output_tokens"]
        urc += totals["usage_record_count"]
        for k, v in totals["cost_status_counts"].items():
            status_counts[k] = status_counts.get(k, 0) + v
        by_profile.extend(usage_by_agent_task(db, run.run_id))
    by_profile.sort(key=lambda r: r["agent_task"])
    return {
        "input_tokens": input_t, "output_tokens": output_t,
        "total_tokens": input_t + output_t, "usage_record_count": urc,
        "cost_status_counts": status_counts, "by_profile": by_profile,
    }
