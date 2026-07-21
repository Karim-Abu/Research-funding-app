"""Search Query Firewall router (Milestone 9J) — beta-internal privacy surface.

Endpoints:
  POST /projects/{id}/search-query-firewall/preview   — screen a query; for a
       confidential class that needs review, create a pending approval.
  POST /search-query-approvals/{id}/approve|reject     — decide a pending approval.

The raw query is screened and hashed; it is never echoed back nor persisted. Only the
sanitized query, a coarse risk label and category-only redaction summary are returned.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.config.settings import Settings
from app.contracts.firewall import (
    ApprovalStatusResponse,
    FirewallPreviewRequest,
    FirewallPreviewResponse,
    RedactionItem,
)
from app.db.models import SearchQueryApproval
from app.db.session import get_db
from app.repositories import idempotency
from app.repositories import projects as projects_repo
from app.security import approval_service
from app.security.deps import AuthContext, require_unsafe_guards, settings_dep

router = APIRouter(tags=["SearchQueryFirewall"])


def _require_project(db: Session, project_id: str, workspace_id: str):
    project = projects_repo.get_scoped(db, project_id, workspace_id)
    if project is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Project not found.",
        )
    return project


def _require_web_research_enabled(settings: Settings) -> None:
    available = settings.web_research_enabled and (
        settings.web_research_fake_provider or bool(settings.firecrawl_api_key)
    )
    if not available:
        raise ProblemException(
            status=503, code="web_research_unavailable", title="Service Unavailable",
            detail="Öffentliche Recherche ist in dieser Umgebung nicht verfügbar.",
        )


def _risk_label(risk_score: int) -> str:
    if risk_score <= 2:
        return "low"
    if risk_score <= 5:
        return "medium"
    return "high"


def _summary(items: list[dict]) -> list[RedactionItem]:
    return [RedactionItem(**i) for i in items]


@router.post(
    "/projects/{project_id}/search-query-firewall/preview",
    response_model=FirewallPreviewResponse,
)
def preview_search_query(
    project_id: str,
    payload: FirewallPreviewRequest,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> FirewallPreviewResponse:
    _require_web_research_enabled(settings)
    project = _require_project(db, project_id, context.user.workspace_id)
    outcome = approval_service.run_preview(
        db, project=project, actor_user_id=context.user.id,
        raw_query=payload.raw_query, intended_tool=payload.intended_tool,
        purpose=payload.purpose,
    )
    db.commit()
    r = outcome.result
    return FirewallPreviewResponse(
        data_class=str(approval_service.derive_data_class(project.data_classification)),
        decision=r.decision,
        risk_label=_risk_label(r.risk_score),
        sanitized_query=r.sanitized_query if r.decision != "block" else "",
        redaction_summary=_summary(r.redaction_summary),
        reasons=list(r.reasons),
        approval_id=outcome.approval.approval_id if outcome.approval else None,
    )


def _decide(
    approval_id: str, *, approve: bool, context: AuthContext, db: Session,
    idempotency_key: str | None,
) -> ApprovalStatusResponse:
    verb = "approve" if approve else "reject"
    fingerprint = idempotency.fingerprint(
        "POST", f"/search-query-approvals/{approval_id}/{verb}", ""
    )
    scope = (
        f"{context.user.workspace_id}:{context.user.id}:POST:"
        f"/search-query-approvals/{approval_id}/{verb}"
    )
    if idempotency_key:
        replay = idempotency.get(db, scope, idempotency_key)
        if replay is not None:
            if replay.request_fingerprint != fingerprint:
                raise ProblemException(
                    status=409, code="idempotency_conflict", title="Conflict",
                    detail="Idempotency-Key reused with a different request.",
                )
            return ApprovalStatusResponse(**replay.response_body)
    approval: SearchQueryApproval | None = approval_service.get_scoped(
        db, approval_id, context.user.workspace_id
    )
    if approval is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Freigabe nicht gefunden.",
        )
    try:
        approval_service.decide(
            db, approval=approval, actor_user_id=context.user.id, approve=approve
        )
    except approval_service.ApprovalError as exc:
        raise ProblemException(
            status=exc.status, code=exc.code, title="Approval conflict", detail=exc.detail,
        ) from exc
    response = ApprovalStatusResponse(
        approval_id=approval.approval_id,
        status=approval.status,
        decision=approval.decision,
        risk_label=_risk_label(approval.risk_score),
        sanitized_query=approval.sanitized_query,
        redaction_summary=_summary(approval.redaction_summary),
    )
    db.commit()
    if idempotency_key:
        idempotency.save(
            db, scope=scope, key=idempotency_key,
            request_fingerprint=fingerprint, response_status=200,
            response_body=response.model_dump(mode="json"),
            resource_id=approval.approval_id,
        )
        db.commit()
    return response


@router.post(
    "/search-query-approvals/{approval_id}/approve",
    response_model=ApprovalStatusResponse,
)
def approve_search_query(
    approval_id: str,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(
        None, alias="Idempotency-Key", min_length=8, max_length=128
    ),
) -> ApprovalStatusResponse:
    return _decide(
        approval_id, approve=True, context=context, db=db,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/search-query-approvals/{approval_id}/reject",
    response_model=ApprovalStatusResponse,
)
def reject_search_query(
    approval_id: str,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(
        None, alias="Idempotency-Key", min_length=8, max_length=128
    ),
) -> ApprovalStatusResponse:
    return _decide(
        approval_id, approve=False, context=context, db=db,
        idempotency_key=idempotency_key,
    )
