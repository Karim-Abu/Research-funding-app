"""Review router: getReview / createHumanDecision / createApproval /
startTargetedRecheck. Deterministic review layer (Milestone 7)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request
from sqlalchemy.orm import Session

from app.api.errors import ProblemException, correlation_id
from app.contracts.review import (
    ApprovalCreate,
    FixQueueView,
    HumanDecision,
    HumanDecisionCreate,
    RecheckCreate,
    ReviewApproval,
    ReviewCheckStatusView,
    ReviewPackage,
    ReviewStatusView,
)
from app.contracts.run import AsyncAccepted
from app.db.models import AnalysisRun
from app.db.session import get_db
from app.repositories import idempotency
from app.repositories import runs as runs_repo
from app.review import service as review_service
from app.review.check_status import build_check_status
from app.review.fix_queue import build_fix_queue
from app.review.recheck import prepare_recheck, recheck_executor
from app.security.deps import AuthContext, require_session, require_unsafe_guards

router = APIRouter(tags=["Review"])

_IDEMPOTENCY = Header(..., alias="Idempotency-Key", min_length=8, max_length=128)


def _require_run(db: Session, run_id: str, workspace_id: str) -> AnalysisRun:
    run = runs_repo.get_scoped(db, run_id, workspace_id)
    if run is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Run not found.",
        )
    return run


def _require_completed(run: AnalysisRun) -> None:
    if run.status != "completed":
        raise ProblemException(
            status=409, code="run_not_reviewable", title="Conflict",
            detail="Review is available only after the run has completed.",
        )


def _idempotent_replay(db, scope, key, fingerprint):
    existing = idempotency.get(db, scope, key)
    if existing is None:
        return None
    if existing.request_fingerprint != fingerprint:
        raise ProblemException(
            status=409, code="idempotency_conflict", title="Conflict",
            detail="Idempotency-Key reused with a different request.",
        )
    return existing


@router.get("/runs/{run_id}/review", response_model=ReviewPackage)
def get_review(
    run_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> ReviewPackage:
    run = _require_run(db, run_id, context.user.workspace_id)
    return review_service.read_review_package(db, run)


@router.get("/runs/{run_id}/review/status", response_model=ReviewStatusView)
def get_review_status(
    run_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> ReviewStatusView:
    """R1.2 — kanonischer Status-View (read-only, additiv). Alle Screens lesen
    Blocker-/Warn-/Prüfzahlen aus dieser einen Quelle statt eigener Zählungen."""
    run = _require_run(db, run_id, context.user.workspace_id)
    return review_service.read_status_view(db, run)


@router.get("/runs/{run_id}/review/check-status", response_model=ReviewCheckStatusView)
def get_review_check_status(
    run_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> ReviewCheckStatusView:
    """Teil A — autoritative Check-Status je Prüfbereich (read-only, additiv).
    ``passed`` nur nach tatsächlich gelaufenem Check; Abwesenheit von Findings
    ohne gelaufenen Check ist ``not_run``."""
    run = _require_run(db, run_id, context.user.workspace_id)
    return build_check_status(db, run)


@router.get("/runs/{run_id}/review/fix-queue", response_model=FixQueueView)
def get_fix_queue(
    run_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> FixQueueView:
    """R2.4 — gruppierte Findings + priorisierte Fix Queue (read-only,
    additiv). Gruppiert nach display_group_key; ändert keine Findings."""
    run = _require_run(db, run_id, context.user.workspace_id)
    return build_fix_queue(db, run)


@router.post(
    "/runs/{run_id}/human-decisions", response_model=HumanDecision, status_code=201
)
def create_human_decision(
    run_id: str,
    payload: HumanDecisionCreate,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = _IDEMPOTENCY,
) -> HumanDecision:
    run = _require_run(db, run_id, context.user.workspace_id)
    _require_completed(run)

    scope = f"{context.user.workspace_id}:{context.user.id}:POST:/human-decisions"
    fingerprint = idempotency.fingerprint(
        "POST", f"/runs/{run_id}/human-decisions", payload.model_dump_json()
    )
    existing = _idempotent_replay(db, scope, idempotency_key, fingerprint)
    if existing is not None:
        return HumanDecision(**existing.response_body)

    decision = review_service.record_human_decision(
        db, run, payload, context.user.id
    )
    idempotency.save(
        db, scope=scope, key=idempotency_key, request_fingerprint=fingerprint,
        response_status=201, response_body=decision.model_dump(mode="json"),
        resource_id=decision.decision_id,
    )
    db.commit()
    return decision


@router.post(
    "/runs/{run_id}/approvals", response_model=ReviewApproval, status_code=201
)
def create_approval(
    run_id: str,
    payload: ApprovalCreate,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = _IDEMPOTENCY,
) -> ReviewApproval:
    run = _require_run(db, run_id, context.user.workspace_id)

    scope = f"{context.user.workspace_id}:{context.user.id}:POST:/approvals"
    fingerprint = idempotency.fingerprint(
        "POST", f"/runs/{run_id}/approvals", payload.model_dump_json()
    )
    existing = _idempotent_replay(db, scope, idempotency_key, fingerprint)
    if existing is not None:
        return ReviewApproval(**existing.response_body)

    approval = review_service.create_approval(db, run, payload, context.user.id)
    idempotency.save(
        db, scope=scope, key=idempotency_key, request_fingerprint=fingerprint,
        response_status=201, response_body=approval.model_dump(mode="json"),
        resource_id=approval.approval_id,
    )
    db.commit()
    return approval


@router.post(
    "/runs/{run_id}/rechecks", response_model=AsyncAccepted, status_code=202
)
def start_targeted_recheck(
    run_id: str,
    payload: RecheckCreate,
    request: Request,
    background: BackgroundTasks,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = _IDEMPOTENCY,
) -> AsyncAccepted:
    run = _require_run(db, run_id, context.user.workspace_id)

    scope = f"{context.user.workspace_id}:{context.user.id}:POST:/rechecks"
    fingerprint = idempotency.fingerprint(
        "POST", f"/runs/{run_id}/rechecks", payload.model_dump_json()
    )
    existing = _idempotent_replay(db, scope, idempotency_key, fingerprint)
    if existing is not None:
        return AsyncAccepted(**existing.response_body)

    _operation, accepted = prepare_recheck(
        db,
        run=run,
        expected_review_package_version=payload.expected_review_package_version,
        actor_user_id=context.user.id,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id(request),
    )
    idempotency.save(
        db, scope=scope, key=idempotency_key, request_fingerprint=fingerprint,
        response_status=202, response_body=accepted.model_dump(mode="json"),
        resource_id=accepted.resource_id,
    )
    db.commit()
    background.add_task(recheck_executor, accepted.resource_id, accepted.operation_id)
    return accepted
