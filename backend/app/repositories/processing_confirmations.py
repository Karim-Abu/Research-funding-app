"""Processing-confirmation persistence (Milestone 9D.2).

One-run cloud-processing confirmations. Created with status=valid; consumed
(status=used) exactly once when a cloud_assisted run that references it is created.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.processing import ProcessingConfirmation as ConfirmationSchema
from app.db.models import (
    ProcessingConfirmation,
    Project,
    SourceDocument,
    SourceVersion,
)

VALID = "valid"
USED = "used"


def project_source_version_ids(db: Session, project_id: str) -> set[str]:
    """All source version ids belonging to a project (for confirmation scoping)."""
    rows = db.scalars(
        select(SourceVersion.source_version_id)
        .join(SourceDocument, SourceVersion.source_document_id == SourceDocument.source_id)
        .where(SourceDocument.project_id == project_id)
    )
    return set(rows)


def to_contract(confirmation: ProcessingConfirmation) -> ConfirmationSchema:
    return ConfirmationSchema(
        confirmation_id=confirmation.confirmation_id,
        project_id=confirmation.project_id,
        created_by=confirmation.created_by,
        status=confirmation.status,
        source_version_ids=list(confirmation.source_version_ids or []),
        policy_version=confirmation.accepted_policy_version,
        created_at=confirmation.created_at,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create(
    db: Session,
    project: Project,
    *,
    created_by: str,
    source_version_ids: list[str],
    accepted_policy_version: str,
    purpose: str,
    provider_route_class: str,
    confirmation_text_version: str,
    data_classification_shown: dict,
    processing_mode: str = "cloud_assisted",
) -> ProcessingConfirmation:
    confirmation = ProcessingConfirmation(
        confirmation_id=str(uuid.uuid4()),
        project_id=project.project_id,
        workspace_id=project.workspace_id,
        created_by=created_by,
        status=VALID,
        processing_mode=processing_mode,
        source_version_ids=list(source_version_ids),
        accepted_policy_version=accepted_policy_version,
        purpose=purpose,
        provider_route_class=provider_route_class,
        confirmation_text_version=confirmation_text_version,
        data_classification_shown=dict(data_classification_shown),
        expires_after_one_run=True,
    )
    db.add(confirmation)
    db.flush()
    return confirmation


def get_scoped(
    db: Session, confirmation_id: str, workspace_id: str
) -> ProcessingConfirmation | None:
    return db.scalar(
        select(ProcessingConfirmation).where(
            ProcessingConfirmation.confirmation_id == confirmation_id,
            ProcessingConfirmation.workspace_id == workspace_id,
        )
    )


def mark_used(db: Session, confirmation: ProcessingConfirmation, run_id: str) -> None:
    confirmation.status = USED
    confirmation.used_by_run_id = run_id
    confirmation.decided_at = _now()
    db.flush()
