"""Exports router: createExport / getExport / downloadExport (Milestone 8)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request, Response
from sqlalchemy.orm import Session

from app.api.errors import ProblemException, correlation_id
from app.contracts.export import ExportArtifact as ExportArtifactSchema
from app.contracts.export import ExportCreate
from app.contracts.run import AsyncAccepted
from app.db.models import AnalysisRun, ExportArtifact
from app.db.session import get_db
from app.exports.executor import export_executor
from app.exports.service import prepare_export
from app.repositories import audit, idempotency
from app.repositories import runs as runs_repo
from app.storage.exports import ExportIntegrityError, get_export_storage
from app.security.deps import AuthContext, require_session, require_unsafe_guards

router = APIRouter(tags=["Exports"])

_NOT_FOUND = "Resource not found"
_IDEMPOTENCY = Header(..., alias="Idempotency-Key", min_length=8, max_length=128)


def _require_run(db: Session, run_id: str, workspace_id: str) -> AnalysisRun:
    run = runs_repo.get_scoped(db, run_id, workspace_id)
    if run is None:
        raise ProblemException(
            status=404, code="not_found", title=_NOT_FOUND, detail="Run not found."
        )
    return run


def _require_export(db: Session, export_id: str, workspace_id: str) -> ExportArtifact:
    artifact = db.get(ExportArtifact, export_id)
    if artifact is None or artifact.workspace_id != workspace_id:
        raise ProblemException(
            status=404, code="not_found", title=_NOT_FOUND,
            detail="Export not found.",
        )
    return artifact


def _to_contract(artifact: ExportArtifact) -> ExportArtifactSchema:
    return ExportArtifactSchema(
        export_id=artifact.export_id,
        run_id=artifact.run_id,
        type=artifact.type,
        status=artifact.status,
        draft_marked=artifact.draft_marked,
        filename=artifact.filename,
        created_at=artifact.created_at,
    )


@router.post(
    "/runs/{run_id}/exports", response_model=AsyncAccepted, status_code=202
)
def create_export(
    run_id: str,
    payload: ExportCreate,
    request: Request,
    background: BackgroundTasks,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = _IDEMPOTENCY,
) -> AsyncAccepted:
    run = _require_run(db, run_id, context.user.workspace_id)

    scope = f"{context.user.workspace_id}:{context.user.id}:POST:/exports"
    fingerprint = idempotency.fingerprint(
        "POST", f"/runs/{run_id}/exports", payload.model_dump_json()
    )
    existing = idempotency.get(db, scope, idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ProblemException(
                status=409, code="idempotency_conflict", title="Conflict",
                detail="Idempotency-Key reused with a different request.",
            )
        return AsyncAccepted(**existing.response_body)

    _artifact, _operation, accepted = prepare_export(
        db,
        run=run,
        export_type=payload.type,
        force_draft=payload.force_draft,
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
    background.add_task(export_executor, accepted.resource_id, accepted.operation_id)
    return accepted


@router.get("/exports/{export_id}", response_model=ExportArtifactSchema)
def get_export(
    export_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> ExportArtifactSchema:
    artifact = _require_export(db, export_id, context.user.workspace_id)
    return _to_contract(artifact)


@router.get("/exports/{export_id}/download")
def download_export(
    export_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> Response:
    artifact = _require_export(db, export_id, context.user.workspace_id)
    if artifact.status != "available" or not artifact.storage_key:
        raise ProblemException(
            status=409, code="export_not_ready", title="Conflict",
            detail="The export is not available for download yet.",
        )
    try:
        data = get_export_storage().open_verified(
            artifact.storage_key, expected_hash=artifact.content_hash
        )
    except (ExportIntegrityError, OSError):
        audit.record(
            db, workspace_id=artifact.workspace_id, actor_user_id=context.user.id,
            action="export.failed", target_type="export", target_id=export_id,
            detail={"code": "EXPORT_INTEGRITY"},
        )
        db.commit()
        raise ProblemException(
            status=409, code="export_unavailable", title="Conflict",
            detail="The export file could not be verified.",
        )
    audit.record(
        db, workspace_id=artifact.workspace_id, actor_user_id=context.user.id,
        action="export.downloaded", target_type="export", target_id=export_id,
        detail={"type": artifact.type, "size_bytes": artifact.size_bytes},
    )
    db.commit()
    filename = artifact.filename or f"{export_id}.bin"
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(data)),
        },
    )
