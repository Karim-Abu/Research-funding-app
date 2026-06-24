"""Source creation services shared by API routes and explicit demo seeds."""
from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app.contracts.source import TextSourceCreate
from app.db.models import Project, SourceDocument, SourceVersion
from app.policy.classification import resolve_effective_classification
from app.repositories import audit, controls
from app.repositories import sources as sources_repo
from app.storage import get_storage

UPLOAD_CONTROLS = (
    "source.size",
    "source.type",
    "source.signature",
    "source.archive_safety",
    "source.path_safety",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record_upload_controls(
    db: Session, doc: SourceDocument, version: SourceVersion, downgrade: bool
) -> None:
    for control_id in UPLOAD_CONTROLS:
        controls.record(
            db,
            workspace_id=doc.workspace_id,
            project_id=doc.project_id,
            source_id=doc.source_id,
            source_version_id=version.source_version_id,
            control_id=control_id,
            status="passed",
        )
    controls.record(
        db,
        workspace_id=doc.workspace_id,
        project_id=doc.project_id,
        source_id=doc.source_id,
        source_version_id=version.source_version_id,
        control_id="source.classification",
        status="warning" if downgrade else "passed",
        detail="downgrade_clamped_to_project" if downgrade else None,
    )


def prepare_text_source(
    db: Session,
    *,
    project: Project,
    payload: TextSourceCreate,
    actor_user_id: str,
    source_id: str | None = None,
    source_version_id: str | None = None,
) -> tuple[SourceDocument, SourceVersion]:
    """Create the source/document rows and audit/control entries.

    The caller owns transaction boundaries. Commit before calling the ingestion
    worker because processing opens its own session.
    """

    source_dc = payload.data_classification.model_dump()
    effective, downgrade = resolve_effective_classification(
        project.data_classification, source_dc
    )
    data = payload.text.encode("utf-8")
    ref = get_storage().put(data)
    doc = sources_repo.create_document(
        db,
        project_id=project.project_id,
        workspace_id=project.workspace_id,
        created_by=actor_user_id,
        name=payload.name,
        source_type="txt",
        classification=effective,
        status="uploaded",
        source_id=source_id,
    )
    version = sources_repo.create_version(
        db,
        document=doc,
        original_content_hash=sha256_bytes(data),
        classification=effective,
        storage_ref=ref,
        original_filename=payload.name,
        byte_size=len(data),
        mime_type="text/plain",
        status="uploaded",
        source_version_id=source_version_id,
    )
    record_upload_controls(db, doc, version, downgrade)
    audit.record(
        db,
        workspace_id=doc.workspace_id,
        actor_user_id=actor_user_id,
        action="source.create",
        target_type="source",
        target_id=doc.source_id,
    )
    return doc, version
