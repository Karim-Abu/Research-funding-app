"""Market comparison router (Milestone 9I-B) — BETA-INTERNAL (not in finalized OpenAPI).

createMarketComparison / getMarketComparison / latestForProject / updateItemStatus. The
comparison is built only from imported public sources; it never mutates drafts, requirement
assessments or approvals. Role member OR lead_admin (beta-internal, public/synthetic only).
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.config.settings import Settings
from app.contracts.market import (
    ItemStatusUpdate,
    MarketComparisonItem as MarketComparisonItemContract,
    MarketComparisonView,
)
from app.contracts.run import AsyncAccepted
from app.db.session import get_db
from app.market import service
from app.market.executor import comparison_executor
from app.repositories import idempotency
from app.repositories import projects as projects_repo
from app.security.deps import AuthContext, require_session, require_unsafe_guards, settings_dep

router = APIRouter(tags=["MarketComparison"])


def _require_project(db: Session, project_id: str, workspace_id: str):
    project = projects_repo.get_scoped(db, project_id, workspace_id)
    if project is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Project not found.",
        )
    return project


def _require_enabled(settings: Settings) -> None:
    available = settings.web_research_enabled and (
        settings.web_research_fake_provider or bool(settings.firecrawl_api_key)
    )
    if not available:
        raise ProblemException(
            status=503, code="market_comparison_unavailable", title="Service Unavailable",
            detail="Markt- und Konkurrenzvergleich ist in dieser Umgebung nicht verfügbar.",
        )


@router.post("/projects/{project_id}/market-comparisons", status_code=202)
def create_market_comparison(
    project_id: str,
    background: BackgroundTasks,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=128),
) -> AsyncAccepted:
    project = _require_project(db, project_id, context.user.workspace_id)
    _require_enabled(settings)
    scope = f"{context.user.workspace_id}:{context.user.id}:POST:/market-comparisons"
    fingerprint = idempotency.fingerprint("POST", f"/projects/{project_id}/market-comparisons", "")
    existing = idempotency.get(db, scope, idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ProblemException(
                status=409, code="idempotency_conflict", title="Conflict",
                detail="Idempotency-Key reused with a different request.",
            )
        return AsyncAccepted(**existing.response_body)

    try:
        _c, _op, accepted = service.create_comparison(
            db, project=project, actor_user_id=context.user.id,
            idempotency_key=idempotency_key,
        )
    except service.ComparisonBlocked as exc:
        db.commit()
        raise ProblemException(
            status=exc.status, code=exc.code, title="Comparison refused", detail=exc.detail,
        ) from exc
    db.commit()
    idempotency.save(
        db, scope=scope, key=idempotency_key, request_fingerprint=fingerprint,
        response_status=202, response_body=accepted.model_dump(mode="json"),
        resource_id=accepted.resource_id,
    )
    db.commit()
    background.add_task(comparison_executor, accepted.resource_id, accepted.operation_id)
    return accepted


@router.get("/market-comparisons/{comparison_id}", response_model=MarketComparisonView)
def get_market_comparison(
    comparison_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> MarketComparisonView:
    comparison = service.get_comparison(db, comparison_id, context.user.workspace_id)
    if comparison is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Market comparison not found.",
        )
    return service.view(db, comparison)


@router.get(
    "/projects/{project_id}/market-comparisons/latest",
    response_model=MarketComparisonView | None,
)
def latest_market_comparison(
    project_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> MarketComparisonView | None:
    _require_project(db, project_id, context.user.workspace_id)
    comparison = service.latest_for_project(db, project_id, context.user.workspace_id)
    if comparison is None:
        return None
    return service.view(db, comparison)


@router.post(
    "/market-comparison-items/{item_id}/status",
    response_model=MarketComparisonItemContract,
)
def update_item_status(
    item_id: str,
    payload: ItemStatusUpdate,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> MarketComparisonItemContract:
    item = service.get_item(db, item_id, context.user.workspace_id)
    if item is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Comparison item not found.",
        )
    service.update_item_status(db, item, payload.status, payload.support_status)
    db.commit()
    return service.item_to_contract(item)
