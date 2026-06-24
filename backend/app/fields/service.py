"""Field mutation services shared by API routes and explicit demo seeds."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.db.models import AnalysisRun, EvidenceAnchor, PortalFieldDraft
from app.repositories import audit
from app.repositories import evidence as evidence_repo

_NOT_FOUND = "Resource not found"


def create_draft_evidence_link(
    db: Session,
    *,
    run: AnalysisRun,
    draft: PortalFieldDraft,
    anchor_id: str,
    base_version_id: str,
    actor_user_id: str,
):
    if draft.current_version_id != base_version_id:
        raise ProblemException(
            status=409,
            code="stale_base_version",
            title="Conflict",
            detail="Dieser Abschnitt wurde zwischenzeitlich geaendert.",
        )
    anchor = db.get(EvidenceAnchor, anchor_id)
    if (
        anchor is None
        or anchor.run_id != run.run_id
        or anchor.workspace_id != run.workspace_id
    ):
        raise ProblemException(
            status=404,
            code="not_found",
            title=_NOT_FOUND,
            detail="Evidence anchor not found in this run.",
        )
    link = evidence_repo.upsert_draft_link(
        db, run, anchor_id, draft.current_version_id
    )
    run.recheck_required = True
    audit.record(
        db,
        workspace_id=run.workspace_id,
        actor_user_id=actor_user_id,
        action="evidence_link.created",
        target_type="evidence_link",
        target_id=link.evidence_link_id,
        detail={"anchor_id": anchor_id},
    )
    audit.record(
        db,
        workspace_id=run.workspace_id,
        actor_user_id=actor_user_id,
        action="run.recheck_required",
        target_type="run",
        target_id=run.run_id,
    )
    db.flush()
    return link
