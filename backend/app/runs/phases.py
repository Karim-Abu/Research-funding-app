"""Persistierte Nutzerphasen eines Analyse-Laufs (Reload-sicher).

Sechs feste Phasen bilden die Graph-Knoten auf die Nutzersicht ab. Die Knoten
schreiben Status/Zähler hier hinein; ``AnalysisRun.current_stage`` bleibt die
technische Contract-Wahrheit. ``detail`` enthält ausschliesslich Zähler und
Skip-Gründe — nie Rohtexte, Prompts oder Keys.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AgentInvocation, AgentInvocationAttempt, AnalysisRun, RunPhase, UsageRecord,
)

# Reihenfolge = Anzeige-Reihenfolge im Frontend.
PHASE_KEYS = (
    "prepare_documents",
    "detect_facts",
    "formal_checks",
    "web_research",
    "draft_fields",
    "quality_review",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get(db: Session, run_id: str, phase_key: str) -> RunPhase | None:
    return db.scalar(
        select(RunPhase).where(
            RunPhase.run_id == run_id, RunPhase.phase_key == phase_key
        )
    )


def ensure_pending(db: Session, run: AnalysisRun) -> None:
    """Alle sechs Phasen idempotent als ``pending`` anlegen, damit die UI von
    Beginn an die vollständige Leiter zeigt."""
    existing = {
        row.phase_key
        for row in db.scalars(
            select(RunPhase).where(RunPhase.run_id == run.run_id)
        )
    }
    for key in PHASE_KEYS:
        if key not in existing:
            db.add(
                RunPhase(
                    run_phase_id=str(uuid.uuid4()),
                    run_id=run.run_id,
                    phase_key=key,
                    status="pending",
                    detail={},
                )
            )
    db.flush()


def start(db: Session, run: AnalysisRun, phase_key: str) -> None:
    """Phase auf ``running`` setzen (idempotent; terminale Phasen unangetastet)."""
    phase = _get(db, run.run_id, phase_key)
    if phase is None:
        phase = RunPhase(
            run_phase_id=str(uuid.uuid4()),
            run_id=run.run_id,
            phase_key=phase_key,
            detail={},
        )
        db.add(phase)
    if phase.status in ("pending", "running"):
        phase.status = "running"
        if phase.started_at is None:
            phase.started_at = _now()
    db.flush()


def add_detail(db: Session, run: AnalysisRun, phase_key: str, detail: dict) -> None:
    """Zähler in eine laufende Phase mergen, ohne ihren Status zu ändern."""
    phase = _get(db, run.run_id, phase_key)
    if phase is None:
        return
    phase.detail = {**(phase.detail or {}), **detail}
    db.flush()


def finish(
    db: Session,
    run: AnalysisRun,
    phase_key: str,
    status: str,
    *,
    detail: dict | None = None,
    error_code: str | None = None,
) -> None:
    """Phase terminal abschliessen (``succeeded``/``failed``/``skipped``);
    ``detail`` wird gemerged, nie ersetzt."""
    phase = _get(db, run.run_id, phase_key)
    if phase is None:
        phase = RunPhase(
            run_phase_id=str(uuid.uuid4()),
            run_id=run.run_id,
            phase_key=phase_key,
            detail={},
        )
        db.add(phase)
    phase.status = status
    if detail:
        phase.detail = {**(phase.detail or {}), **detail}
    if error_code is not None:
        phase.error_code = error_code
    if phase.started_at is None:
        phase.started_at = _now()
    phase.ended_at = _now()
    db.flush()


def list_for_run(db: Session, run_id: str) -> list[RunPhase]:
    rows = {
        row.phase_key: row
        for row in db.scalars(
            select(RunPhase).where(RunPhase.run_id == run_id)
        )
    }
    return [rows[key] for key in PHASE_KEYS if key in rows]


def technical_summary(db: Session, run: AnalysisRun) -> dict:
    """Aggregierte technische Angaben je Agent (Provider, Modell, Tokens,
    Kosten, Latenz) aus vorhandenen AgentInvocations/UsageRecords. Kosten
    werden nur über ``cost_status='priced'`` summiert; ``unknown_price`` wird
    ausgewiesen, nie als «gratis» gelesen."""
    invocations = list(
        db.scalars(
            select(AgentInvocation)
            .where(AgentInvocation.run_id == run.run_id)
            .order_by(AgentInvocation.created_at)
        )
    )
    usage_by_id = {
        u.usage_record_id: u
        for u in db.scalars(
            select(UsageRecord).where(UsageRecord.run_id == run.run_id)
        )
    }
    attempts_by_invocation: dict[str, list[AgentInvocationAttempt]] = {}
    invocation_ids = [inv.invocation_id for inv in invocations]
    if invocation_ids:
        for attempt in db.scalars(
            select(AgentInvocationAttempt)
            .where(AgentInvocationAttempt.invocation_id.in_(invocation_ids))
            .order_by(AgentInvocationAttempt.attempt_index)
        ):
            attempts_by_invocation.setdefault(attempt.invocation_id, []).append(attempt)
    agents: dict[str, dict] = {}
    for inv in invocations:
        entry = agents.setdefault(
            inv.agent_id,
            {
                "agent_id": inv.agent_id,
                "invocations": 0,
                "providers": [],
                "models": [],
                "input_tokens": 0,
                "output_tokens": 0,
                "priced_cost_chf": 0.0,
                "has_unpriced_usage": False,
                "latency_ms_total": 0,
                "generation_kinds": [],
                "model_calls": 0,
                "prompt_versions": [],
                "actual_models": [],
                "skill_versions": [],
                "retry_count": 0,
                "termination_reasons": [],
                "attempts": [],
            },
        )
        entry["invocations"] += 1
        meta = dict(inv.context_meta or {})
        generation_kind = meta.get("generation_kind")
        if generation_kind and generation_kind not in entry["generation_kinds"]:
            entry["generation_kinds"].append(generation_kind)
        real_call = bool(meta.get("model_call_attempted"))
        if real_call:
            entry["model_calls"] += 1
        if real_call and inv.provider and inv.provider not in entry["providers"]:
            entry["providers"].append(inv.provider)
        if real_call and inv.model_id and inv.model_id not in entry["models"]:
            entry["models"].append(inv.model_id)
        if (
            real_call and inv.prompt_version
            and inv.prompt_version not in entry["prompt_versions"]
        ):
            entry["prompt_versions"].append(inv.prompt_version)
        if real_call and inv.actual_model_id and inv.actual_model_id not in entry["actual_models"]:
            entry["actual_models"].append(inv.actual_model_id)
        if inv.skill_version and inv.skill_version not in entry["skill_versions"]:
            entry["skill_versions"].append(inv.skill_version)
        entry["retry_count"] += inv.retry_count or 0
        if inv.termination_reason and inv.termination_reason not in entry["termination_reasons"]:
            entry["termination_reasons"].append(inv.termination_reason)
        for attempt in attempts_by_invocation.get(inv.invocation_id, []):
            attempt_usage = usage_by_id.get(attempt.usage_record_id)
            entry["attempts"].append({
                "route_alias": attempt.route_alias,
                "provider": attempt.provider,
                "requested_model_id": attempt.requested_model_id,
                "actual_model_id": attempt.actual_model_id,
                "status": attempt.status,
                "error_class": attempt.error_class,
                "retry_index": attempt.retry_index,
                "termination_reason": attempt.termination_reason,
                "latency_ms": attempt.latency_ms,
                "estimated_cost_chf": attempt.estimated_cost_chf,
                "estimated_cost_status": attempt.estimated_cost_status,
                "input_tokens": attempt_usage.input_tokens if attempt_usage else 0,
                "output_tokens": attempt_usage.output_tokens if attempt_usage else 0,
                "cost_chf": attempt_usage.cost_chf if attempt_usage else 0.0,
                "cost_status": (
                    attempt_usage.cost_status if attempt_usage else "not_available"
                ),
            })
        if inv.latency_ms:
            entry["latency_ms_total"] += inv.latency_ms
        invocation_attempts = attempts_by_invocation.get(inv.invocation_id, [])
        usage_ids = {
            attempt.usage_record_id for attempt in invocation_attempts
            if attempt.usage_record_id
        }
        if not usage_ids and inv.usage_record_id:
            usage_ids.add(inv.usage_record_id)
        for usage_id in usage_ids:
            usage = usage_by_id.get(usage_id)
            if usage is not None and real_call:
                entry["input_tokens"] += usage.input_tokens
                entry["output_tokens"] += usage.output_tokens
                if usage.cost_status == "priced":
                    entry["priced_cost_chf"] += usage.cost_chf
                elif usage.cost_status == "unknown_price":
                    entry["has_unpriced_usage"] = True

    a2_providers = set(agents.get("A2", {}).get("providers", []))
    a3_providers = set(agents.get("A3", {}).get("providers", []))
    same_provider = (
        (a2_providers == a3_providers) if a2_providers and a3_providers else None
    )
    return {
        "run_id": run.run_id,
        "agents": [agents[key] for key in sorted(agents)],
        "priced_cost_chf_total": round(
            sum(a["priced_cost_chf"] for a in agents.values()), 6
        ),
        "has_unpriced_usage": any(a["has_unpriced_usage"] for a in agents.values()),
        "same_provider_a2_a3": same_provider,
        "model_called": any(a["model_calls"] > 0 for a in agents.values()),
    }
