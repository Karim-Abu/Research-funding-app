"""Reliability router (Milestone 9K) — beta-internal MAS reliability & value assurance.

Not part of the finalized OpenAPI. ``POST /runs/{id}/reliability`` runs the deterministic
reliability pass (async); ``GET /runs/{id}/reliability`` returns the RunQualitySummary +
per-claim lineage/sufficiency + reliability findings (authenticated, workspace-scoped).
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.contracts.reliability import ReliabilityView
from app.contracts.run import AsyncAccepted
from app.db.models import AnalysisRun
from app.db.session import get_db
from app.reliability import service as reliability_service
from app.reliability.executor import reliability_executor
from app.repositories import idempotency
from app.repositories import runs as runs_repo
from app.security.deps import AuthContext, require_session, require_unsafe_guards

router = APIRouter(tags=["Reliability"])

_IDEMPOTENCY = Header(..., alias="Idempotency-Key", min_length=8, max_length=128)


def _require_run(db: Session, run_id: str, workspace_id: str) -> AnalysisRun:
    run = runs_repo.get_scoped(db, run_id, workspace_id)
    if run is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Run not found.",
        )
    return run


@router.post("/runs/{run_id}/reliability", response_model=AsyncAccepted, status_code=202)
def start_reliability_pass(
    run_id: str,
    background: BackgroundTasks,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = _IDEMPOTENCY,
) -> AsyncAccepted:
    run = _require_run(db, run_id, context.user.workspace_id)
    scope = f"{context.user.workspace_id}:{context.user.id}:POST:/reliability"
    fingerprint = idempotency.fingerprint("POST", f"/runs/{run_id}/reliability", "")
    existing = idempotency.get(db, scope, idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ProblemException(
                status=409, code="idempotency_conflict", title="Conflict",
                detail="Idempotency-Key reused with a different request.",
            )
        return AsyncAccepted(**existing.response_body)

    _operation, accepted = reliability_service.create_reliability_pass(
        db, run=run, actor_user_id=context.user.id, idempotency_key=idempotency_key,
    )
    idempotency.save(
        db, scope=scope, key=idempotency_key, request_fingerprint=fingerprint,
        response_status=202, response_body=accepted.model_dump(mode="json"),
        resource_id=accepted.resource_id,
    )
    db.commit()
    background.add_task(reliability_executor, accepted.resource_id, accepted.operation_id)
    return accepted


@router.get("/runs/{run_id}/reliability", response_model=ReliabilityView)
def get_reliability(
    run_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> ReliabilityView:
    run = _require_run(db, run_id, context.user.workspace_id)
    return reliability_service.get_view(db, run)
