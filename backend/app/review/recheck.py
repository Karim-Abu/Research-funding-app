"""Targeted recheck: a deterministic, async review recompute on a completed run.

Re-runs the deterministic aggregator + rebuilds the ReviewPackage and clears
``recheck_required`` because the review state is current again — even if blocker
findings remain. It NEVER re-runs the graph, re-ingests sources, re-discovers
evidence, mutates historical artifacts, calls a provider/LLM, or auto-approves.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.contracts.run import AsyncAccepted
from app.db.models import AnalysisRun, AsyncOperation
from app.db.session import SessionLocal
from app.repositories import audit
from app.review import package as review_package
from app.runs.constants import TERMINAL_OPERATION_STATUSES

logger = logging.getLogger("app.review.recheck")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def prepare_recheck(
    db: Session,
    *,
    run: AnalysisRun,
    expected_review_package_version: str,
    actor_user_id: str,
    idempotency_key: str | None = None,
    correlation_id: str | None = None,
) -> tuple[AsyncOperation, AsyncAccepted]:
    """Validate the expected package version and queue a recheck operation.

    Caller owns idempotency persistence, commit and background dispatch.
    """
    if run.status != "completed":
        raise ProblemException(
            status=409, code="run_not_reviewable", title="Conflict",
            detail="Review is available only after the run has completed.",
        )
    current_version = review_package.package_version(
        review_package.compute_scope_hash(db, run)
    )
    if expected_review_package_version != current_version:
        raise ProblemException(
            status=409, code="review_package_stale", title="Conflict",
            detail=(
                "The review package changed since it was loaded. Reload the "
                "review and try again."
            ),
        )

    operation = AsyncOperation(
        operation_id=str(uuid.uuid4()),
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        resource_type="recheck",
        resource_id=run.run_id,
        status="queued",
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )
    db.add(operation)
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=actor_user_id,
        action="review.recheck_requested", target_type="run", target_id=run.run_id,
        detail={"operation_id": operation.operation_id},
    )
    accepted = AsyncAccepted(
        operation_id=operation.operation_id,
        resource_type="recheck",
        resource_id=run.run_id,
        status="queued",
        poll_url=f"/api/v1/operations/{operation.operation_id}",
    )
    return operation, accepted


def recheck_executor(run_id: str, operation_id: str) -> None:
    """Background deterministic recompute. Fail-closed; never changes run.status."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        op = db.get(AsyncOperation, operation_id)
        if run is None or op is None:
            return
        if op.status in TERMINAL_OPERATION_STATUSES:
            return
        op.status = "running"
        op.started_at = _now()
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        db.close()
        _mark_failed(run_id, operation_id)
        return
    finally:
        db.close()

    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        op = db.get(AsyncOperation, operation_id)
        if run is None or op is None:
            return
        package = review_package.refresh_package(db, run, clear_recheck=True)
        if op.status not in TERMINAL_OPERATION_STATUSES:
            op.status = "succeeded"
            op.finished_at = _now()
            op.progress_percent = 100
            op.result = {
                "run_id": run_id,
                "review_package_version": package.review_package_version,
                "approval_status": package.approval_status,
            }
        audit.record(
            db, workspace_id=run.workspace_id, actor_user_id=None,
            action="review.recheck_completed", target_type="run", target_id=run_id,
            detail={"version": package.review_package_version},
        )
        db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("targeted recheck failed")
        db.rollback()
        _mark_failed(run_id, operation_id)
    finally:
        db.close()


def _mark_failed(run_id: str, operation_id: str) -> None:
    db = SessionLocal()
    try:
        op = db.get(AsyncOperation, operation_id)
        if op is not None and op.status not in TERMINAL_OPERATION_STATUSES:
            op.status = "failed"
            op.finished_at = _now()
            op.last_error_code = "RECHECK_FAILED"
            op.error = {
                "type": "/problems/recheck_failed",
                "title": "Recheck Error",
                "status": 500,
                "detail": "Targeted recheck failed.",
                "code": "RECHECK_FAILED",
                "correlation_id": str(uuid.uuid4()),
            }
            db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    finally:
        db.close()
