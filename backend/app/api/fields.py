"""Fields router: listFields / getField / updateField + draft EvidenceLinks."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request, Response
from sqlalchemy.orm import Session

from app.api.errors import ProblemException, correlation_id
from app.contracts.draft import DraftPatch, EvidenceLinkCreate, PortalFieldDraft, RedraftRequest
from app.contracts.evidence import EvidenceLink
from app.contracts.run import AsyncAccepted
from app.db.models import AnalysisRun
from app.db.session import get_db
from app.fields import redraft_service
from app.fields import service as fields_service
from app.registry import get_registry
from app.repositories import audit
from app.repositories import drafts as drafts_repo
from app.repositories import evidence as evidence_repo
from app.repositories import runs as runs_repo
from app.review.invalidation import invalidate_approvals
from app.security.deps import AuthContext, require_session, require_unsafe_guards

from app.agents.a2_fields import A2_FIELD_PROFILES

router = APIRouter(tags=["Fields"])

_NOT_FOUND = "Resource not found"


def _require_run(db: Session, run_id: str, workspace_id: str) -> AnalysisRun:
    run = runs_repo.get_scoped(db, run_id, workspace_id)
    if run is None:
        raise ProblemException(
            status=404,
            code="not_found",
            title=_NOT_FOUND,
            detail="Run not found.",
        )
    return run


def _supported_field(field_id: str) -> bool:
    field = get_registry().portal_fields.get(field_id)
    return field is not None and field.is_m6_draft_field


def _require_draft(db: Session, run: AnalysisRun, field_id: str):
    if not _supported_field(field_id):
        raise ProblemException(
            status=404,
            code="not_found",
            title=_NOT_FOUND,
            detail="Field is not a supported draft field.",
        )
    draft = drafts_repo.get_draft(db, run.run_id, field_id)
    if draft is None:
        raise ProblemException(
            status=404,
            code="not_found",
            title=_NOT_FOUND,
            detail="Draft not found.",
        )
    return draft


@router.get("/runs/{run_id}/fields", response_model=list[PortalFieldDraft])
def list_fields(
    run_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> list[PortalFieldDraft]:
    run = _require_run(db, run_id, context.user.workspace_id)
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
        db,
        run,
        draft,
        base_version_id=payload.base_version_id,
        text=payload.text,
        source_operation_id=payload.source_operation_id,
        actor_user_id=context.user.id,
    )
    db.commit()
    return drafts_repo.to_contract(db, draft)


@router.post(
    "/runs/{run_id}/fields/{field_id}/redrafts",
    response_model=AsyncAccepted,
    status_code=202,
)
def create_redraft(
    run_id: str,
    field_id: str,
    payload: RedraftRequest,
    request: Request,
    background: BackgroundTasks,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> AsyncAccepted:
    """Milestone 9D/9E: request an advisory A2 suggestion for an A2-enabled field
    (Solution & Innovation or Value Creation). Async (202); 409 on a stale base
    version; 503 when AI is unavailable for the run's data class / processing mode.
    The draft is never auto-modified."""
    run = _require_run(db, run_id, context.user.workspace_id)
    # A2 is scoped to the explicit registry-backed field/profile allow-list.
    if field_id not in A2_FIELD_PROFILES:
        raise ProblemException(
            status=404, code="not_found", title=_NOT_FOUND,
            detail="AI suggestions are not available for this field.",
        )
    draft = _require_draft(db, run, field_id)
    operation, accepted, guidance = redraft_service.prepare_redraft(
        db, run, draft, base_version_id=payload.base_version_id,
        guidance=payload.guidance, actor_user_id=context.user.id,
        idempotency_key=None, correlation_id=correlation_id(request),
    )
    db.commit()
    background.add_task(
        redraft_service.redraft_executor, operation.operation_id, run.run_id,
        draft.draft_id, payload.base_version_id, guidance, field_id,
    )
    return accepted


@router.post(
    "/runs/{run_id}/fields/{field_id}/evidence-links",
    response_model=EvidenceLink,
    status_code=201,
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
    link = fields_service.create_draft_evidence_link(
        db,
        run=run,
        draft=draft,
        anchor_id=payload.anchor_id,
        base_version_id=payload.base_version_id,
        actor_user_id=context.user.id,
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
            status=404,
            code="not_found",
            title=_NOT_FOUND,
            detail="Evidence link not found.",
        )
    evidence_repo.remove_link(db, link)
    run.recheck_required = True
    invalidate_approvals(db, run, actor_user_id=context.user.id)
    audit.record(
        db,
        workspace_id=run.workspace_id,
        actor_user_id=context.user.id,
        action="evidence_link.removed",
        target_type="evidence_link",
        target_id=link.evidence_link_id,
    )
    audit.record(
        db,
        workspace_id=run.workspace_id,
        actor_user_id=context.user.id,
        action="run.recheck_required",
        target_type="run",
        target_id=run.run_id,
    )
    db.commit()
    return Response(status_code=204)
