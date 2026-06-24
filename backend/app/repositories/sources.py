"""Source persistence (workspace+project scoped) + ORM→contract mapping."""
from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.contracts.source import SourceDocument as SourceDocumentSchema
from app.db.models import SourceDocument, SourceFragment, SourceVersion


def create_document(
    db: Session,
    *,
    project_id: str,
    workspace_id: str,
    created_by: str,
    name: str,
    source_type: str,
    classification: dict,
    status: str = "uploaded",
    source_id: str | None = None,
) -> SourceDocument:
    document = SourceDocument(
        source_id=source_id or str(uuid.uuid4()),
        project_id=project_id,
        workspace_id=workspace_id,
        name=name,
        type=source_type,
        status=status,
        data_classification=classification,
        created_by=created_by,
    )
    db.add(document)
    db.flush()
    return document


def create_version(
    db: Session,
    *,
    document: SourceDocument,
    original_content_hash: str,
    classification: dict,
    storage_ref: str,
    original_filename: str,
    byte_size: int,
    mime_type: str,
    status: str = "uploaded",
    source_version_id: str | None = None,
) -> SourceVersion:
    version = SourceVersion(
        source_version_id=source_version_id or str(uuid.uuid4()),
        source_document_id=document.source_id,
        version_number=1,
        original_content_hash=original_content_hash,
        data_classification=classification,
        storage_ref=storage_ref,
        original_filename=original_filename,
        byte_size=byte_size,
        mime_type=mime_type,
        processing_status=status,
    )
    db.add(version)
    db.flush()
    document.current_source_version_id = version.source_version_id
    db.flush()
    return version


def list_by_project(
    db: Session, project_id: str, workspace_id: str
) -> list[SourceDocument]:
    return list(
        db.scalars(
            select(SourceDocument)
            .where(
                SourceDocument.project_id == project_id,
                SourceDocument.workspace_id == workspace_id,
            )
            .order_by(SourceDocument.created_at.desc())
        )
    )


def get_scoped(
    db: Session, source_id: str, workspace_id: str
) -> SourceDocument | None:
    return db.scalar(
        select(SourceDocument).where(
            SourceDocument.source_id == source_id,
            SourceDocument.workspace_id == workspace_id,
        )
    )


def physically_delete(db: Session, document: SourceDocument) -> list[str]:
    """Delete fragments, versions and the document. Returns storage refs to purge."""
    versions = list(
        db.scalars(
            select(SourceVersion).where(
                SourceVersion.source_document_id == document.source_id
            )
        )
    )
    version_ids = [v.source_version_id for v in versions]
    storage_refs = [v.storage_ref for v in versions]
    if version_ids:
        db.execute(
            delete(SourceFragment).where(
                SourceFragment.source_version_id.in_(version_ids)
            )
        )
        db.execute(
            delete(SourceVersion).where(
                SourceVersion.source_document_id == document.source_id
            )
        )
    db.delete(document)
    db.flush()
    return storage_refs


def to_contract(document: SourceDocument) -> SourceDocumentSchema:
    return SourceDocumentSchema(
        source_id=document.source_id,
        project_id=document.project_id,
        name=document.name,
        type=document.type,
        status=document.status,
        data_classification=document.data_classification,
        current_source_version_id=document.current_source_version_id,
        created_at=document.created_at,
        error_message=document.error_message,
    )
