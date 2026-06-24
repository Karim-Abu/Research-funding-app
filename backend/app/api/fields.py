"""Fields router — listFields / getField / updateField + draft EvidenceLinks."""
from __future__ import annotations

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, Header, Response

from app.api.errors import ProblemException
from app.contracts.draft import DraftPatch, EvidenceLinkCreate, PortalFieldDraft
from app.contracts.evidence import EvidenceLink
from app.db.models import AnalysisRun, EvidenceAnchor
from app.db.session import get_db
from app.registry import get_registry
from app.repositories import audit
from app.repositories import drafts as drafts_repo
from app.repositories import evidence as evidence_repo
from app.repositories import runs as runs_repo
from app.security.deps import AuthContext, require_session, require_unsafe_guards

router = APIRouter(tags=["Fields"])

_NOT_FOUND = "Resource not found"


def _require_run(db: Session, run_id: str, workspace_id: str) -> AnalysisRun:
    run = runs_repo.get_scoped(db, run_id, workspace_id)
    if run is None:
        raise ProblemException(
            status=404, code="not_found", title=_NOT_FOUND, detail="Run not found.",
        )
    return run


def _supported_field(field_id: str) -> bool:
    field = get_registry().portal_fields.get(field_id)
    return field is not None and field.is_m6_draft_field


def _require_draft(db: Session, run: AnalysisRun, field_id: str):
    if not _supported_field(field_id):
        raise ProblemException(
            status=404, code="not_found", title=_NOT_FOUND,
            detail="Field is not a supported draft field.",
        )
    draft = drafts_repo.get_draft(db, run.run_id, field_id)
    if draft is None:
        raise ProblemException(
            status=404, code="not_found", title=_NOT_FOUND, detail="Draft not found.",
        )
    return draft


@router.get("/runs/{run_id}/fields", response_model=list[PortalFieldDraft])
def list_fields(
    run_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> list[PortalFieldDraft]:
    run = _require_run(db, run_id, context.user.workspace_id)
    # Stable canonical registry order, supported fields only.
    out: list[PortalFieldDraft] = []
    for field in get_registry().m6_draft_fields():
        draft = drafts_repo.get_draft(db, run.run_id, field.field_id)
        if draft is not None:
            out.append(drafts_repo.to_contract(db, draft))
    return out


@router.get("/runs/{run_id}/fields/{field_id}", response_model=PortalFieldDraft)
def get_field(
    run_id: str,
    field_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> PortalFieldDraft:
    run = _require_run(db, run_id, context.user.workspace_id)
    draft = _require_draft(db, run, field_id)
    return drafts_repo.to_contract(db, draft)


@router.patch("/runs/{run_id}/fields/{field_id}", response_model=PortalFieldDraft)
def update_field(
    run_id: str,
    field_id: str,
    payload: DraftPatch,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> PortalFieldDraft:
    run = _require_run(db, run_id, context.user.workspace_id)
    draft = _require_draft(db, run, field_id)
    drafts_repo.apply_update(
        db, run, draft,
        base_version_id=payload.base_version_id,
        text=payload.text,
        source_operation_id=payload.source_operation_id,
        actor_user_id=context.user.id,
    )
    db.commit()
    return drafts_repo.to_contract(db, draft)


@router.post(
    "/runs/{run_id}/fields/{field_id}/evidence-links",
    response_model=EvidenceLink, status_code=201,
)
def create_evidence_link(
    run_id: str,
    field_id: str,
    payload: EvidenceLinkCreate,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=8, max_length=128
    ),
) -> EvidenceLink:
    run = _require_run(db, run_id, context.user.workspace_id)
    draft = _require_draft(db, run, field_id)
    # The base version must be the current draft version (optimistic concurrency).
    if draft.current_version_id != payload.base_version_id:
        raise ProblemException(
            status=409, code="stale_base_version", title="Conflict",
            detail="Dieser Abschnitt wurde zwischenzeitlich geändert.",
        )
    anchor = db.get(EvidenceAnchor, payload.anchor_id)
    if anchor is None or anchor.run_id != run.run_id or anchor.workspace_id != run.workspace_id:
        raise ProblemException(
            status=404, code="not_found", title=_NOT_FOUND,
            detail="Evidence anchor not found in this run.",
        )
    link = evidence_repo.upsert_draft_link(
        db, run, payload.anchor_id, draft.current_version_id
    )
    run.recheck_required = True
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=context.user.id,
        action="evidence_link.created", target_type="evidence_link",
        target_id=link.evidence_link_id, detail={"anchor_id": payload.anchor_id},
    )
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=context.user.id,
        action="run.recheck_required", target_type="run", target_id=run.run_id,
    )
    db.commit()
    return evidence_repo.to_link_contract(link)


@router.delete(
    "/runs/{run_id}/fields/{field_id}/evidence-links/{evidence_link_id}",
    status_code=204,
)
def delete_evidence_link(
    run_id: str,
    field_id: str,
    evidence_link_id: str,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> Response:
    run = _require_run(db, run_id, context.user.workspace_id)
    _require_draft(db, run, field_id)
    link = evidence_repo.get_link_scoped(db, evidence_link_id, run.run_id)
    if link is None or link.target_type != "draft_version":
        raise ProblemException(
            status=404, code="not_found", title=_NOT_FOUND,
            detail="Evidence link not found.",
        )
    evidence_repo.remove_link(db, link)
    run.recheck_required = True
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=context.user.id,
        action="evidence_link.removed", target_type="evidence_link",
        target_id=link.evidence_link_id,
    )
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=context.user.id,
        action="run.recheck_required", target_type="run", target_id=run.run_id,
    )
    db.commit()
    return Response(status_code=204)
