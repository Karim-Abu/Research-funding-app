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

from sqlalchemy.orm import Session

from app.db.models import Partner, Project, RunProjectSnapshot
from app.registry.loader import Registry
from app.repositories import partners as partners_repo


def _project_dict(project: Project) -> dict:
    return {
        "project_id": project.project_id,
        "funding_instrument_profile_id": project.funding_instrument_profile_id,
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
    return _project_dict(project), [
        partners_repo.snapshot_dict(p) for p in partner_rows
    ]


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
