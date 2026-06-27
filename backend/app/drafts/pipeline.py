"""Deterministic template-draft pipeline orchestration (Milestone 6).

draft_fields (A2 disabled, no provider) + create_template_drafts (deterministic
templates from immutable run inputs). Upsert-only; the caller owns the
transaction. No LLM/network/embeddings.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AnalysisRun
from app.registry import get_registry
from app.repositories import audit, controls
from app.repositories import drafts as drafts_repo


def record_a2_disabled(db: Session, run: AnalysisRun) -> None:
    """draft_fields stage: the agent (A2) drafting route is disabled — record a
    contract control and continue to deterministic templates. No provider call."""
    controls.record(
        db, workspace_id=run.workspace_id, project_id=run.project_id,
        source_id=None, control_id="CTRL.DATA_POLICY", status="passed",
        detail="a2_disabled deterministic_template",
    )
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None,
        action="draft.fields_a2_skipped", target_type="run", target_id=run.run_id,
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
