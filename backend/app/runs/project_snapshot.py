"""Immutable project + partner input snapshot for a run + staleness detection.

At run creation the structured project + partner inputs are frozen into
``RunProjectSnapshot`` with a deterministic content hash. The run is always
evaluated against this frozen copy. Staleness = the *current* project/partner
inputs hash differs from the snapshot hash — surfaced to the user as a
"please re-run" notice (the run is never silently re-evaluated).
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisRun,
    Partner,
    Project,
    RunProjectSnapshot,
    StructuredImportCandidate,
)
from app.registry.loader import Registry
from app.repositories import audit
from app.repositories import partners as partners_repo
from app.review.invalidation import invalidate_approvals
from app.runs.constants import ACTIVE_RUN_STATUSES


def _accepted_answers(db: Session, project: Project) -> dict:
    rows = list(
        db.scalars(
            select(StructuredImportCandidate)
            .where(
                StructuredImportCandidate.project_id == project.project_id,
                StructuredImportCandidate.workspace_id == project.workspace_id,
                StructuredImportCandidate.candidate_kind == "answer",
                StructuredImportCandidate.decision == "accepted",
            )
            .order_by(StructuredImportCandidate.decided_at.desc())
        )
    )
    answers: dict[str, dict] = {}
    for row in rows:
        if row.target_key in answers:
            continue
        payload = row.edited_payload_json or row.payload_json
        if row.target_key == "answer.scientific_integrity":
            answers["scientific_integrity"] = {
                "sanction_answer": payload.get("sanction_answer"),
                "comment": payload.get("comment"),
                "human_decision_present": True,
            }
        elif row.target_key == "answer.management_hours":
            answers["management_hours"] = {
                "management_hours": payload.get("management_hours"),
                "total_project_hours": payload.get("total_project_hours"),
            }
    return answers


def _project_dict(project: Project, structured_answers: dict | None = None) -> dict:
    return {
        "project_id": project.project_id,
        "funding_instrument_profile_id": project.funding_instrument_profile_id,
        # Strukturierte Projektbeschreibung aus dem Intake: versionierter
        # Run-Input (A1-Kontext) — eine spätere Änderung macht den Lauf
        # sichtbar stale, genau wie eine Budget-Änderung.
        "title": project.title,
        "title_en": project.title_en,
        "start_date": project.start_date.isoformat() if project.start_date else None,
        "end_date": project.end_date.isoformat() if project.end_date else None,
        "description": project.description,
        # Structured budget/duration inputs (Slice 1). Part of the frozen
        # snapshot so a later budget edit makes the run visibly stale.
        "direct_total_project_costs_excluding_overhead": (
            project.direct_total_project_costs_excluding_overhead
        ),
        "implementation_own_contribution": project.implementation_own_contribution,
        "cash_contribution": project.cash_contribution,
        "total_requested_funding": project.total_requested_funding,
        "total_requested_funding_including_overhead": (
            project.total_requested_funding_including_overhead
        ),
        "budget_exception_basis": project.budget_exception_basis,
        "duration_months": project.duration_months,
        "structured_answers": structured_answers or {},
    }


def compute_hash(project_json: dict, partners_json: list[dict]) -> str:
    payload = json.dumps(
        {"project": project_json, "partners": partners_json},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def current_inputs(
    db: Session, project: Project
) -> tuple[dict, list[dict]]:
    partner_rows = partners_repo.list_by_project(
        db, project.project_id, project.workspace_id
    )
    return _project_dict(project, _accepted_answers(db, project)), [
        partners_repo.snapshot_dict(p) for p in partner_rows
    ]


def mark_current_runs_stale(
    db: Session, *, project: Project, actor_user_id: str
) -> list[str]:
    """Persistente Recheck-Markierung; der immutable Snapshot bleibt intakt."""
    rows = list(
        db.scalars(
            select(AnalysisRun).where(
                AnalysisRun.project_id == project.project_id,
                AnalysisRun.workspace_id == project.workspace_id,
                (
                    AnalysisRun.status.in_(ACTIVE_RUN_STATUSES)
                    | (AnalysisRun.run_id == project.active_run_id)
                ),
            )
        )
    )
    changed: list[str] = []
    for run in rows:
        run.recheck_required = True
        invalidate_approvals(db, run, actor_user_id=actor_user_id)
        audit.record(
            db,
            workspace_id=project.workspace_id,
            actor_user_id=actor_user_id,
            action="run.recheck_required",
            target_type="run",
            target_id=run.run_id,
            detail={"reason": "structured_import_changed"},
        )
        changed.append(run.run_id)
    db.flush()
    return changed


def build_and_persist(
    db: Session, *, run_id: str, project: Project, registry: Registry
) -> RunProjectSnapshot:
    project_json, partners_json = current_inputs(db, project)
    snapshot = RunProjectSnapshot(
        run_id=run_id,
        project_id=project.project_id,
        project_json=project_json,
        partners_json=partners_json,
        content_hash=compute_hash(project_json, partners_json),
        requirement_registry_version=registry.requirement_registry_version,
        rule_registry_version=registry.rule_registry_version,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def is_stale(db: Session, snapshot: RunProjectSnapshot) -> bool:
    """True when the current project/partner inputs differ from the snapshot."""
    project = db.get(Project, snapshot.project_id)
    if project is None:
        return False
    project_json, partners_json = current_inputs(db, project)
    return compute_hash(project_json, partners_json) != snapshot.content_hash
