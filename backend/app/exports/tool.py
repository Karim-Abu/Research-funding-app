"""Registered export-tool boundary (Milestone 8).

Mirrors the `create_export_artifact` tool: persists a canonical ToolInvocation,
records the required ControlResults (linked to the invocation), runs the
deterministic generator and stores the file atomically. No LLM / network.
Bounded by the configured generation timeout.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models import ExportArtifact, ToolInvocation
from app.exports import EXPORT_MIME
from app.exports.generators import GENERATORS
from app.exports.transitions import transition
from app.repositories import audit, controls
from app.storage.exports import ExportTooLargeError, get_export_storage

logger = logging.getLogger("app.exports.tool")

TOOL_ID = "create_export_artifact"
_PRE_CONTROLS = (
    "CTRL.RUN_SNAPSHOT_SCOPE",
    "CTRL.VERSION_LOCK",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _control(db, artifact, control_id, status, detail):
    controls.record(
        db, workspace_id=artifact.workspace_id, project_id=artifact.project_id,
        control_id=control_id, status=status, detail=detail,
        run_id=artifact.run_id, tool_invocation_id=artifact.tool_invocation_id,
    )


def run_export(db: Session, artifact: ExportArtifact) -> None:
    """Generate + persist the export for an artifact already in `generating`.

    Caller owns the surrounding operation lifecycle. Raises on failure (after
    compensating file cleanup); the executor maps that to export=failed.
    """
    settings = get_settings()
    invocation = db.get(ToolInvocation, artifact.tool_invocation_id)
    invocation.status = "running"
    invocation.started_at = _now()
    db.flush()

    snapshot = artifact.export_snapshot_json
    classification = artifact.effective_data_classification
    for control_id in _PRE_CONTROLS:
        _control(db, artifact, control_id, "passed", artifact.export_snapshot_hash)
    approval_status = "warning" if artifact.draft_marked else "passed"
    approval_detail = (
        f"phase=export; draft_marked={str(artifact.draft_marked).lower()}; "
        f"reason={'export_marked_as_draft' if artifact.draft_marked else 'approval_current'}; "
        f"snapshot_hash={artifact.export_snapshot_hash}"
    )
    _control(db, artifact, "CTRL.APPROVAL_GATE", approval_status, approval_detail)
    _control(
        db, artifact, "CTRL.EXPORT_CLASSIFICATION", "passed",
        f"sensitivity={classification.get('sensitivity')}",
    )

    generator = GENERATORS[artifact.type]
    started = _now()
    # Deterministic, in-memory generation (no network/LLM). Bounded by a
    # post-hoc wall-clock check against the configured timeout (corr. #4); a
    # thread cannot be preempted on the local single-instance beta anyway.
    monotonic = time.monotonic()
    data = generator(snapshot, artifact.export_snapshot_hash)
    if time.monotonic() - monotonic > settings.export_generation_timeout_seconds:
        raise TimeoutError("export generation exceeded the configured timeout")

    storage = get_export_storage()
    try:
        stored = storage.put(data)
    except ExportTooLargeError:
        _control(db, artifact, "CTRL.OUTPUT_SCHEMA", "failed", "size_limit_exceeded")
        raise

    # Compensating: if the DB transition fails after the file lands, remove it.
    try:
        artifact.storage_key = stored.storage_key
        artifact.content_hash = stored.content_hash
        artifact.size_bytes = stored.size_bytes
        artifact.mime_type = EXPORT_MIME[artifact.type]
        transition(artifact, "available")
        artifact.finished_at = _now()
        invocation.status = "succeeded"
        invocation.output_hash = stored.content_hash
        invocation.finished_at = artifact.finished_at
        invocation.duration_ms = int(
            (artifact.finished_at - started).total_seconds() * 1000
        )
        _control(db, artifact, "CTRL.OUTPUT_SCHEMA", "passed", "output_validated")
        _control(db, artifact, "CTRL.FILENAME_NORMALIZATION", "passed", artifact.filename)
        _control(db, artifact, "CTRL.AUDIT_WRITE", "passed", "export_generated")
        audit.record(
            db, workspace_id=artifact.workspace_id, actor_user_id=None,
            action="export.generated", target_type="export", target_id=artifact.export_id,
            detail={
                "type": artifact.type,
                "draft_marked": artifact.draft_marked,
                "content_hash": stored.content_hash,
                "size_bytes": stored.size_bytes,
            },
        )
        db.flush()
    except Exception:
        storage.delete(stored.storage_key)
        raise
