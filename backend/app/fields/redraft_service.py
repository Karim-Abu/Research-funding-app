"""createRedraft service + async executor (Milestone 9D).

Generates an advisory A2 suggestion for SOL.INNOVATION_SOLUTION.EDITOR. Mirrors the
M3 run-executor async pattern: a queued AsyncOperation runs the A2 orchestrator in the
background and stores the suggestion in ``operation.result``. The endpoint pre-checks
base-version currency (409) and per-run availability (503) — it NEVER upgrades the run's
processing mode.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.agents import field_drafting
from app.api.errors import ProblemException
from app.contracts.run import AsyncAccepted
from app.db.models import AnalysisRun, AsyncOperation, PortalFieldDraft
from app.db.session import SessionLocal
from app.repositories import audit
from app.runs.constants import TERMINAL_OPERATION_STATUSES
from app.runs.transitions import transition_operation

logger = logging.getLogger("app.fields.redraft")

FIELD_ID = "SOL.INNOVATION_SOLUTION.EDITOR"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def prepare_redraft(
    db,
    run: AnalysisRun,
    draft: PortalFieldDraft,
    *,
    base_version_id: str,
    guidance: str | None,
    actor_user_id: str,
    idempotency_key: str | None,
    correlation_id: str | None,
) -> tuple[AsyncOperation, AsyncAccepted, str | None]:
    """Validate + queue. Returns (operation, accepted, guidance). Raises 409/503."""
    # Optimistic concurrency: the suggestion is for the *current* version.
    if draft.current_version_id != base_version_id:
        raise ProblemException(
            status=409, code="stale_base_version", title="Conflict",
            detail="Dieser Abschnitt wurde zwischenzeitlich geändert.",
        )
    available, reason = field_drafting.availability(run)
    if not available:
        raise ProblemException(
            status=503, code="ai_unavailable", title="Service Unavailable",
            detail="KI-Vorschläge sind für diese Datenklasse oder Umgebung nicht verfügbar.",
        )
    operation_id = str(uuid.uuid4())
    operation = AsyncOperation(
        operation_id=operation_id, workspace_id=run.workspace_id,
        project_id=run.project_id, resource_type="redraft", resource_id=draft.draft_id,
        status="queued", idempotency_key=idempotency_key, correlation_id=correlation_id,
    )
    db.add(operation)
    db.flush()
    accepted = AsyncAccepted(
        operation_id=operation_id, resource_type="redraft", resource_id=draft.draft_id,
        status="queued", poll_url=f"/api/v1/operations/{operation_id}",
    )
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=actor_user_id,
        action="redraft.requested", target_type="portal_field_draft",
        target_id=draft.draft_id, detail={"field_id": FIELD_ID},
    )
    return operation, accepted, guidance


def redraft_executor(
    operation_id: str, run_id: str, draft_id: str, base_version_id: str,
    guidance: str | None,
) -> None:
    """Background task: run A2 and store the suggestion in operation.result."""
    db = SessionLocal()
    try:
        op = db.get(AsyncOperation, operation_id)
        run = db.get(AnalysisRun, run_id)
        if op is None or run is None or op.status in TERMINAL_OPERATION_STATUSES:
            return
        transition_operation(op, "running")
        op.started_at = _now()
        db.commit()

        outcome = field_drafting.run_a2_solution_innovation(
            db, run, draft_id=draft_id, base_version_id=base_version_id,
            operation_id=operation_id, guidance=guidance,
        )

        op = db.get(AsyncOperation, operation_id)
        if op is None:
            return
        if outcome.status in ("succeeded", "reused") and outcome.view is not None:
            transition_operation(op, "succeeded")
            op.result = outcome.view
            op.progress_percent = 100
        else:
            op.status = "failed"
            op.last_error_code = outcome.reason or "ai_unavailable"
            op.error = {
                "code": outcome.reason or "ai_unavailable",
                "detail": "Es konnte kein Vorschlag erstellt werden.",
            }
        op.finished_at = _now()
        audit.record(
            db, workspace_id=run.workspace_id, actor_user_id=None,
            action=f"operation.{op.status}", target_type="operation",
            target_id=operation_id,
        )
        db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("redraft execution failed")
        db.rollback()
        _mark_failed(operation_id)
    finally:
        db.close()


def _mark_failed(operation_id: str) -> None:
    db = SessionLocal()
    try:
        op = db.get(AsyncOperation, operation_id)
        if op is not None and op.status not in TERMINAL_OPERATION_STATUSES:
            op.status = "failed"
            op.finished_at = _now()
            op.last_error_code = "REDRAFT_EXECUTION_FAILED"
            op.error = {"code": "REDRAFT_EXECUTION_FAILED",
                        "detail": "Es konnte kein Vorschlag erstellt werden."}
            db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    finally:
        db.close()
