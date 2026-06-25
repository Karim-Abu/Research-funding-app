"""Export creation service (Milestone 8).

Freezes the snapshot + draft-marking atomically, enforces the registered-tool
call limit (429), persists ExportArtifact + ToolInvocation + AsyncOperation, and
returns the exact 202 AsyncAccepted. Shared by the API route.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.config.settings import get_settings
from app.contracts.run import AsyncAccepted
from app.db.models import AnalysisRun, AsyncOperation, ExportArtifact, ToolInvocation
from app.exports.eligibility import evaluate_draft_marked
from app.exports.generators.common import build_filename
from app.exports.snapshot import build_snapshot
from app.exports.tool import TOOL_ID
from app.repositories import audit
from app.review import package as review_package


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _accepted_count(db: Session, run_id: str, export_type: str) -> int:
    return db.scalar(
        select(func.count(ExportArtifact.export_id)).where(
            ExportArtifact.run_id == run_id, ExportArtifact.type == export_type
        )
    ) or 0


def prepare_export(
    db: Session,
    *,
    run: AnalysisRun,
    export_type: str,
    force_draft: bool,
    actor_user_id: str,
    idempotency_key: str | None,
    correlation_id: str | None,
) -> tuple[ExportArtifact, AsyncOperation, AsyncAccepted]:
    """Caller owns idempotency persistence, commit and background dispatch."""
    if run.status != "completed":
        raise ProblemException(
            status=409, code="run_not_reviewable", title="Conflict",
            detail="Exports are available only after the run has completed.",
        )

    limit = get_settings().max_exports_per_run_and_type
    if _accepted_count(db, run.run_id, export_type) >= limit:
        raise ProblemException(
            status=429, code="export_limit_reached", title="Too Many Requests",
            detail=(
                "The export limit for this run and format has been reached. "
                "Please reuse an existing export."
            ),
        )

    frozen_at = _now()
    # Freeze + revalidate the review scope immediately before persisting; at most
    # one controlled retry. Never persist a mixed-state snapshot (corr. #2).
    decision = snapshot = snapshot_hash = None
    for _ in range(2):
        decision = evaluate_draft_marked(db, run, force_draft)
        snapshot, snapshot_hash = build_snapshot(
            db, run, export_type=export_type, decision=decision,
            actor_user_id=actor_user_id, frozen_at=frozen_at,
        )
        current_hash = review_package.compute_scope_hash(db, run)
        current_version = review_package.package_version(current_hash)
        if (
            current_hash == decision.scope_hash
            and current_version == decision.review_package_version
        ):
            break
    else:
        raise ProblemException(
            status=409, code="export_state_changed", title="Conflict",
            detail="The review state changed while preparing the export. Retry.",
        )

    export_id = str(uuid.uuid4())
    invocation = ToolInvocation(
        invocation_id=str(uuid.uuid4()),
        workspace_id=run.workspace_id,
        run_id=run.run_id,
        tool_id=TOOL_ID,
        caller="orchestrator",
        input_hash=snapshot_hash,
        status="queued",
    )
    db.add(invocation)
    artifact = ExportArtifact(
        export_id=export_id,
        run_id=run.run_id,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        created_by=actor_user_id,
        type=export_type,
        status="queued",
        draft_marked=decision.draft_marked,
        filename=build_filename(snapshot),
        approval_id=decision.approval.approval_id if decision.approval else None,
        approval_scope_hash=decision.scope_hash,
        review_package_version=decision.review_package_version,
        effective_data_classification=run.effective_data_classification,
        export_snapshot_json=snapshot,
        export_snapshot_hash=snapshot_hash,
        tool_invocation_id=invocation.invocation_id,
        created_at=frozen_at,
    )
    db.add(artifact)

    operation = AsyncOperation(
        operation_id=str(uuid.uuid4()),
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        resource_type="export",
        resource_id=export_id,
        status="queued",
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )
    db.add(operation)
    for action in ("export.requested", "export.queued"):
        audit.record(
            db, workspace_id=run.workspace_id, actor_user_id=actor_user_id,
            action=action, target_type="export", target_id=export_id,
            detail={"type": export_type, "draft_marked": decision.draft_marked},
        )
    db.flush()

    accepted = AsyncAccepted(
        operation_id=operation.operation_id,
        resource_type="export",
        resource_id=export_id,
        status="queued",
        poll_url=f"/api/v1/operations/{operation.operation_id}",
    )
    return artifact, operation, accepted
