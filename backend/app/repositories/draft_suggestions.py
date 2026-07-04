"""A2 DraftSuggestion persistence (Milestone 9D, internal — no OpenAPI exposure).

Advisory AI draft suggestions for SOL.INNOVATION_SOLUTION.EDITOR. Immutable except
the status/decision fields; only an accepted suggestion creates a DraftVersion.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalysisRun, DraftSuggestion

# Statuses A2 may create / transition to.
PROPOSED = "proposed"
ACCEPTED = "accepted"
REJECTED = "rejected"
EXPIRED = "expired"
FAILED = "failed"


def content_hash(text: str) -> str:
    """Same hashing as DraftVersion content_hash, so accept can compare exactly."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create(
    db: Session,
    run: AnalysisRun,
    *,
    draft_id: str,
    base_version_id: str,
    field_id: str,
    profile_id: str,
    operation_id: str,
    agent_invocation_id: str | None,
    prompt_version: str | None,
    model_route: str | None,
    model_id: str | None,
    suggested_text: str,
    rationale: str | None,
    evidence_anchor_ids: list[str],
    open_issue_ids: list[str],
    placeholders: list,
    character_count: int,
) -> DraftSuggestion:
    suggestion = DraftSuggestion(
        suggestion_id=str(uuid.uuid4()),
        run_id=run.run_id,
        workspace_id=run.workspace_id,
        draft_id=draft_id,
        base_version_id=base_version_id,
        field_id=field_id,
        profile_id=profile_id,
        operation_id=operation_id,
        agent_invocation_id=agent_invocation_id,
        prompt_version=prompt_version,
        model_route=model_route,
        model_id=model_id,
        status=PROPOSED,
        suggested_text=suggested_text,
        rationale=rationale,
        evidence_anchor_ids=list(evidence_anchor_ids),
        open_issue_ids=list(open_issue_ids),
        placeholders=list(placeholders),
        content_hash=content_hash(suggested_text),
        character_count=character_count,
    )
    db.add(suggestion)
    db.flush()
    return suggestion


def get_by_operation(db: Session, operation_id: str) -> DraftSuggestion | None:
    return db.scalar(
        select(DraftSuggestion).where(DraftSuggestion.operation_id == operation_id)
    )


def get_proposed_for(
    db: Session, run_id: str, draft_id: str, base_version_id: str
) -> DraftSuggestion | None:
    """For replay/idempotency: a still-proposed suggestion for this exact base."""
    return db.scalar(
        select(DraftSuggestion).where(
            DraftSuggestion.run_id == run_id,
            DraftSuggestion.draft_id == draft_id,
            DraftSuggestion.base_version_id == base_version_id,
            DraftSuggestion.status == PROPOSED,
        )
    )


def mark_accepted(
    db: Session,
    suggestion: DraftSuggestion,
    *,
    accepted_draft_version_id: str,
    decided_by: str | None,
) -> None:
    suggestion.status = ACCEPTED
    suggestion.accepted_draft_version_id = accepted_draft_version_id
    suggestion.decided_at = _now()
    suggestion.decided_by = decided_by
    db.flush()


def expire_superseded(db: Session, draft_id: str, current_base_version_id: str) -> int:
    """Mark proposed suggestions for a draft whose base no longer matches as
    expired (a newer DraftVersion supersedes them)."""
    count = 0
    for suggestion in db.scalars(
        select(DraftSuggestion).where(
            DraftSuggestion.draft_id == draft_id,
            DraftSuggestion.status == PROPOSED,
            DraftSuggestion.base_version_id != current_base_version_id,
        )
    ):
        suggestion.status = EXPIRED
        suggestion.decided_at = _now()
        count += 1
    db.flush()
    return count
