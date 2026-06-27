"""Approval invalidation on content edits (kept dependency-light so the edit
sites can call it without importing the full review service)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalysisRun, ReviewApproval
from app.repositories import audit


def invalidate_approvals(
    db: Session, run: AnalysisRun, *, actor_user_id: str | None
) -> int:
    """Mark every still-active approval on the run stale. Returns the count.

    Called whenever a draft edit or evidence-link change alters the review scope,
    so a prior sign-off can never silently cover changed content.
    """
    count = 0
    for approval in db.scalars(
        select(ReviewApproval).where(
            ReviewApproval.run_id == run.run_id,
            ReviewApproval.status == "approved",
            ReviewApproval.invalidated_at.is_(None),
        )
    ):
        approval.status = "stale"
        approval.invalidated_at = datetime.now(timezone.utc)
        count += 1
        audit.record(
            db, workspace_id=run.workspace_id, actor_user_id=actor_user_id,
            action="approval.invalidated", target_type="review_approval",
            target_id=approval.approval_id,
        )
    return count
