"""Runs router: createRun / listProjectRuns / getRun / cancelRun / resumeRun."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ProblemException, correlation_id
from app.config.settings import Settings
from app.contracts.run import AnalysisRun as AnalysisRunSchema
from app.contracts.run import AsyncAccepted, RunCreate, RunList, ResumeRequest
from app.contracts.run_phases import RunPhases
from app.db.models import AsyncOperation
from app.db.session import get_db
from app.repositories import audit, controls, idempotency
from app.repositories import projects as projects_repo
from app.repositories import runs as runs_repo
from app.runs import phases as run_phases
from app.runs import service as run_service
from app.runs.constants import TERMINAL_OPERATION_STATUSES, TERMINAL_RUN_STATUSES
from app.runs.executor import run_executor
from app.runs.transitions import transition_operation, transition_run
from app.security.deps import (
    AuthContext,
    require_session,
    require_unsafe_guards,
    settings_dep,
)

router = APIRouter(tags=["Runs"])


def _require_project(db: Session, project_id: str, workspace_id: str):
    project = projects_repo.get_scoped(db, project_id, workspace_id)
    if project is None:
        raise ProblemException(
            status=404,
            code="not_found",
            title="Resource not found",
            detail="Project not found.",
        )
    return project


@router.post(
    "/projects/{project_id}/runs", response_model=AsyncAccepted, status_code=202
)
def create_run(
    project_id: str,
    payload: RunCreate,
    request: Request,
    background: BackgroundTasks,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=8, max_length=128
    ),
) -> AsyncAccepted:
    project = _require_project(db, project_id, context.user.workspace_id)

    scope = f"{context.user.workspace_id}:{context.user.id}:POST:/runs"
    fingerprint = idempotency.fingerprint(
        "POST", f"/projects/{project_id}/runs", payload.model_dump_json()
    )
    existing = idempotency.get(db, scope, idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ProblemException(
                status=409,
                code="idempotency_conflict",
                title="Conflict",
                detail="Idempotency-Key reused with a different request.",
            )
        return AsyncAccepted(**existing.response_body)

    _run, _operation, accepted = run_service.prepare_run(
        db,
        project=project,
        payload=payload,
        actor_user_id=context.user.id,
        settings=settings,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id(request),
    )
    idempotency.save(
        db,
        scope=scope,
        key=idempotency_key,
        request_fingerprint=fingerprint,
        response_status=202,
        response_body=accepted.model_dump(mode="json"),
        resource_id=accepted.resource_id,
    )
    db.commit()
    background.add_task(run_executor, accepted.resource_id, accepted.operation_id)
    return accepted


@router.get("/projects/{project_id}/runs", response_model=RunList)
def list_project_runs(
    project_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> RunList:
    _require_project(db, project_id, context.user.workspace_id)
    rows = runs_repo.list_by_project(db, project_id, context.user.workspace_id)
    return RunList(items=[runs_repo.to_contract(r) for r in rows], next_cursor=None)


@router.get("/runs/{run_id}", response_model=AnalysisRunSchema)
def get_run(
    run_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> AnalysisRunSchema:
    run = runs_repo.get_scoped(db, run_id, context.user.workspace_id)
    if run is None:
        raise ProblemException(
            status=404,
            code="not_found",
            title="Resource not found",
            detail="Run not found.",
        )
    return runs_repo.to_contract(run)


@router.get("/runs/{run_id}/phases", response_model=RunPhases)
def get_run_phases(
    run_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> RunPhases:
    """Persistierter Phasenstand + technische Zusammenfassung (read-only).
    Reload-sicher: die Phasen liegen in ``run_phases``, nicht im Client."""
    run = runs_repo.get_scoped(db, run_id, context.user.workspace_id)
    if run is None:
        raise ProblemException(
            status=404,
            code="not_found",
            title="Resource not found",
            detail="Run not found.",
        )
    return RunPhases(
        run_id=run.run_id,
        run_status=run.status,
        phases=[
            {
                "phase_key": row.phase_key,
                "status": row.status,
                "started_at": row.started_at,
                "ended_at": row.ended_at,
                "error_code": row.error_code,
                "detail": row.detail or {},
            }
            for row in run_phases.list_for_run(db, run.run_id)
        ],
        technical=run_phases.technical_summary(db, run),
    )


@router.post("/runs/{run_id}/cancel", response_model=AnalysisRunSchema)
def cancel_run(
    run_id: str,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=8, max_length=128
    ),
) -> AnalysisRunSchema:
    run = runs_repo.get_scoped(db, run_id, context.user.workspace_id)
    if run is None:
        raise ProblemException(
            status=404,
            code="not_found",
            title="Resource not found",
            detail="Run not found.",
        )
    if run.status in TERMINAL_RUN_STATUSES:
        if run.status == "cancelled":
            return runs_repo.to_contract(run)
        raise ProblemException(
            status=409,
            code="invalid_run_transition",
            title="Conflict",
            detail=f"A {run.status} run cannot be cancelled.",
        )

    run.cancel_requested = True
    transition_run(run, "cancelled")
    operation = db.scalar(
        select(AsyncOperation)
        .where(
            AsyncOperation.resource_id == run_id,
            AsyncOperation.resource_type == "run",
        )
        .order_by(AsyncOperation.created_at.desc())
    )
    if operation is not None and operation.status not in TERMINAL_OPERATION_STATUSES:
        transition_operation(operation, "cancelled")
    controls.record(
        db,
        workspace_id=context.user.workspace_id,
        project_id=run.project_id,
        source_id=None,
        control_id="run.operation_state",
        status="passed",
        detail="cancelled",
    )
    for action in ("cancel.requested", "run.cancelled"):
        audit.record(
            db,
            workspace_id=context.user.workspace_id,
            actor_user_id=context.user.id,
            action=action,
            target_type="run",
            target_id=run_id,
        )
    db.commit()
    return runs_repo.to_contract(run)


@router.post("/runs/{run_id}/resume", response_model=AsyncAccepted, status_code=202)
def resume_run(
    run_id: str,
    payload: ResumeRequest,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=8, max_length=128
    ),
) -> AsyncAccepted:
    run = runs_repo.get_scoped(db, run_id, context.user.workspace_id)
    if run is None:
        raise ProblemException(
            status=404,
            code="not_found",
            title="Resource not found",
            detail="Run not found.",
        )
    raise ProblemException(
        status=409,
        code="run_not_resumable",
        title="Conflict",
        detail="The run is not awaiting finalization.",
    )
