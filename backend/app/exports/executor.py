"""Bounded background export execution + startup recovery (Milestone 8).

Mirrors the run executor: operation queued→running, generate via the tool
boundary, reconcile from the artifact status. Fail-closed. Never changes
run/review/approval state. No network/LLM.
"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.config.settings import get_settings
from app.db.models import AsyncOperation, ExportArtifact, ToolInvocation
from app.db.session import SessionLocal
from app.exports.tool import run_export
from app.exports.transitions import transition
from app.repositories import audit
from app.runs.constants import TERMINAL_OPERATION_STATUSES
from app.storage.exports import get_export_storage

logger = logging.getLogger("app.exports.executor")
_semaphore = threading.BoundedSemaphore(get_settings().max_export_concurrency)

_FINAL = ("available", "failed")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fail(export_id: str, operation_id: str, code: str, detail: str) -> None:
    db = SessionLocal()
    try:
        artifact = db.get(ExportArtifact, export_id)
        op = db.get(AsyncOperation, operation_id)
        if artifact is not None and artifact.status not in _FINAL:
            if artifact.storage_key:  # remove any partial/leftover file
                get_export_storage().delete(artifact.storage_key)
                artifact.storage_key = None
            transition(artifact, "failed")
            artifact.finished_at = _now()
            artifact.error_code = code
            artifact.error_detail = detail
            inv = db.get(ToolInvocation, artifact.tool_invocation_id)
            if inv is not None and inv.status not in ("succeeded", "failed"):
                inv.status = "failed"
                inv.finished_at = _now()
                inv.error_class = code
            audit.record(
                db, workspace_id=artifact.workspace_id, actor_user_id=None,
                action="export.failed", target_type="export", target_id=export_id,
                detail={"code": code},
            )
        if op is not None and op.status not in TERMINAL_OPERATION_STATUSES:
            op.status = "failed"
            op.finished_at = _now()
            op.last_error_code = code
            op.error = {
                "type": f"/problems/{code.lower()}", "title": "Export Error",
                "status": 500, "detail": detail, "code": code,
                "correlation_id": str(uuid.uuid4()),
            }
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    finally:
        db.close()


def export_executor(export_id: str, operation_id: str) -> None:
    with _semaphore:
        db = SessionLocal()
        try:
            artifact = db.get(ExportArtifact, export_id)
            op = db.get(AsyncOperation, operation_id)
            if artifact is None or op is None:
                return
            if artifact.status in _FINAL or op.status in TERMINAL_OPERATION_STATUSES:
                return
            op.status = "running"
            op.started_at = _now()
            transition(artifact, "generating")
            artifact.started_at = _now()
            audit.record(
                db, workspace_id=artifact.workspace_id, actor_user_id=None,
                action="export.started", target_type="export", target_id=export_id,
            )
            run_export(db, artifact)  # generating → available + tool/controls
            if op.status not in TERMINAL_OPERATION_STATUSES:
                op.status = "succeeded"
                op.finished_at = _now()
                op.progress_percent = 100
                op.result = {"export_id": export_id, "status": artifact.status}
            audit.record(
                db, workspace_id=artifact.workspace_id, actor_user_id=None,
                action="export.available", target_type="export", target_id=export_id,
                detail={"draft_marked": artifact.draft_marked},
            )
            db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("export generation failed")
            db.rollback()
            db.close()
            _fail(export_id, operation_id, "EXPORT_FAILED", "Export generation failed.")
            return
        finally:
            db.close()


def _fail_interrupted(db, artifact: ExportArtifact) -> None:
    artifact.storage_key = None
    artifact.status = "failed"
    artifact.finished_at = _now()
    artifact.error_code = "EXPORT_INTERRUPTED"
    op = db.scalar(
        select(AsyncOperation).where(
            AsyncOperation.resource_type == "export",
            AsyncOperation.resource_id == artifact.export_id,
        )
    )
    if op is not None and op.status not in TERMINAL_OPERATION_STATUSES:
        op.status = "failed"
        op.finished_at = _now()
        op.last_error_code = "EXPORT_INTERRUPTED"
    inv = db.get(ToolInvocation, artifact.tool_invocation_id)
    if inv is not None and inv.status not in ("succeeded", "failed"):
        inv.status = "failed"
        inv.error_class = "EXPORT_INTERRUPTED"
    audit.record(
        db, workspace_id=artifact.workspace_id, actor_user_id=None,
        action="export.failed", target_type="export",
        target_id=artifact.export_id, detail={"code": "EXPORT_INTERRUPTED"},
    )


def recover_interrupted_exports() -> int:
    """Startup: queued/generating exports → failed (with their operations), and
    orphaned export files are removed. Audit preserved; no auto-regenerate."""
    db = SessionLocal()
    count = 0
    keep: set[str] = set()
    try:
        for artifact in db.scalars(select(ExportArtifact)):
            if artifact.status in ("queued", "generating"):
                _fail_interrupted(db, artifact)
                count += 1
            elif artifact.status == "available" and artifact.storage_key:
                keep.add(artifact.storage_key)
        if count:
            db.commit()
        get_export_storage().purge_orphans(keep)
        return count
    finally:
        db.close()
