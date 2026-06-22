"""RunExecutor: bounded background execution of the LangGraph workflow.

For the local single-instance beta this uses FastAPI BackgroundTasks bounded by a
configurable semaphore. Operation/run status updates are atomic; checkpoint/exec
failures are fail-closed (run+operation → failed); startup recovers interrupted
work conservatively (never reported as success).
"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.config.settings import get_settings
from app.db.models import AnalysisRun, AsyncOperation
from app.db.session import SessionLocal
from app.repositories import audit
from app.runs.constants import TERMINAL_OPERATION_STATUSES, TERMINAL_RUN_STATUSES
from app.runs.graph import get_graph
from app.runs.transitions import transition_operation, transition_run

logger = logging.getLogger("app.runs.executor")
_semaphore = threading.BoundedSemaphore(get_settings().max_run_concurrency)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _problem(code: str, detail: str, status: int = 500) -> dict:
    return {
        "type": f"/problems/{code}",
        "title": "Run Error",
        "status": status,
        "detail": detail,
        "code": code,
        "correlation_id": str(uuid.uuid4()),
    }


def _mark_failed(run_id: str, operation_id: str, code: str, detail: str) -> None:
    db = SessionLocal()
    try:
        op = db.get(AsyncOperation, operation_id)
        run = db.get(AnalysisRun, run_id)
        if op is not None and op.status not in TERMINAL_OPERATION_STATUSES:
            op.status = "failed"
            op.finished_at = _now()
            op.last_error_code = code
            op.error = _problem(code, detail)
        if run is not None and run.status not in TERMINAL_RUN_STATUSES:
            run.status = "failed"
            run.ended_at = _now()
            run.last_error = _problem(code, detail)
            audit.record(
                db, workspace_id=run.workspace_id, actor_user_id=None,
                action="run.failed", target_type="run", target_id=run_id,
                detail={"code": code},
            )
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    finally:
        db.close()


def run_executor(run_id: str, operation_id: str) -> None:
    with _semaphore:
        # 1. Start: operation queued→running, run created→running.
        db = SessionLocal()
        project_id = workspace_id = None
        try:
            run = db.get(AnalysisRun, run_id)
            op = db.get(AsyncOperation, operation_id)
            if run is None or op is None:
                return
            if (
                run.status in TERMINAL_RUN_STATUSES
                or op.status in TERMINAL_OPERATION_STATUSES
            ):
                return  # cancelled before start / already recovered
            project_id, workspace_id = run.project_id, run.workspace_id
            transition_operation(op, "running")
            op.started_at = _now()
            transition_run(run, "running")
            run.started_at = _now()
            audit.record(
                db, workspace_id=run.workspace_id, actor_user_id=None,
                action="operation.started", target_type="operation",
                target_id=operation_id,
            )
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            db.close()
            _mark_failed(run_id, operation_id, "RUN_START_FAILED", "Run could not be started.")
            return
        finally:
            db.close()

        # 2. Execute the graph (fail-closed on checkpoint/execution error).
        try:
            get_graph().invoke(
                {
                    "run_id": run_id,
                    "project_id": project_id,
                    "workspace_id": workspace_id,
                    "cancelled": False,
                },
                config={"configurable": {"thread_id": run_id}},
            )
        except Exception:  # noqa: BLE001
            logger.exception("run execution failed")
            _mark_failed(run_id, operation_id, "RUN_EXECUTION_FAILED", "Run execution failed.")
            return

        # 3. Reconcile the operation from the authoritative run status.
        db = SessionLocal()
        try:
            run = db.get(AnalysisRun, run_id)
            op = db.get(AsyncOperation, operation_id)
            if run is None or op is None:
                return
            if run.status == "completed":
                if op.status not in TERMINAL_OPERATION_STATUSES:
                    transition_operation(op, "succeeded")
                    op.finished_at = _now()
                    op.progress_percent = 100
                    op.result = {"run_id": run_id, "status": "completed"}
                audit.record(
                    db, workspace_id=run.workspace_id, actor_user_id=None,
                    action="operation.succeeded", target_type="operation",
                    target_id=operation_id,
                )
            elif run.status == "cancelled":
                if op.status not in TERMINAL_OPERATION_STATUSES:
                    transition_operation(op, "cancelled")
                    op.finished_at = _now()
                audit.record(
                    db, workspace_id=run.workspace_id, actor_user_id=None,
                    action="operation.cancelled", target_type="operation",
                    target_id=operation_id,
                )
            elif op.status not in TERMINAL_OPERATION_STATUSES:
                op.status = "failed"
                op.finished_at = _now()
                op.last_error_code = "RUN_NOT_FINALIZED"
                op.error = _problem("RUN_NOT_FINALIZED", "Run did not finalize.")
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            _mark_failed(run_id, operation_id, "RUN_RECONCILE_FAILED", "Run reconcile failed.")
        finally:
            db.close()


def recover_interrupted_runs() -> int:
    """Startup: operations queued/running → failed (OPERATION_INTERRUPTED); their
    nonterminal runs → failed. Checkpoints preserved; no auto-resume."""
    db = SessionLocal()
    count = 0
    try:
        operations = db.scalars(
            select(AsyncOperation).where(
                AsyncOperation.status.in_(("queued", "running"))
            )
        ).all()
        for op in operations:
            op.status = "failed"
            op.finished_at = _now()
            op.last_error_code = "OPERATION_INTERRUPTED"
            op.error = _problem(
                "OPERATION_INTERRUPTED", "The operation was interrupted by a restart."
            )
            run = (
                db.get(AnalysisRun, op.resource_id)
                if op.resource_type == "run"
                else None
            )
            if run is not None and run.status not in TERMINAL_RUN_STATUSES:
                run.status = "failed"
                run.ended_at = _now()
                run.last_error = _problem(
                    "OPERATION_INTERRUPTED", "The run was interrupted by a restart."
                )
                audit.record(
                    db, workspace_id=run.workspace_id, actor_user_id=None,
                    action="run.failed", target_type="run", target_id=run.run_id,
                    detail={"code": "OPERATION_INTERRUPTED"},
                )
            count += 1
        if count:
            db.commit()
        return count
    finally:
        db.close()
