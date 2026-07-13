"""Immutable source snapshot — only terminal, processed, in-scope SourceVersions."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.db.models import RunSourceSnapshot, SourceDocument, SourceVersion


def _eligible_versions(
    db: Session, project_id: str, workspace_id: str
) -> list[SourceVersion]:
    return list(
        db.scalars(
            select(SourceVersion)
            .join(
                SourceDocument,
                SourceVersion.source_document_id == SourceDocument.source_id,
            )
            .where(
                SourceDocument.project_id == project_id,
                SourceDocument.workspace_id == workspace_id,
                SourceVersion.processing_status == "processed",
            )
        )
    )


def build_source_snapshot(
    db: Session,
    *,
    project_id: str,
    workspace_id: str,
    requested_version_ids: list[str] | None,
    allow_empty: bool = False,
) -> list[SourceVersion]:
    """Resolve + validate the frozen source set. Excludes processing/failed/
    needs_manual_input/deleted/foreign versions. Raises 422 if invalid — or if
    empty, ausser der Aufrufer erlaubt einen quellenlosen Lauf explizit
    (Intake-only: die strukturierte Projektbeschreibung ist der versionierte
    Input, eingefroren im RunProjectSnapshot)."""
    eligible = {v.source_version_id: v for v in _eligible_versions(db, project_id, workspace_id)}

    if requested_version_ids:
        chosen: list[SourceVersion] = []
        for version_id in requested_version_ids:
            version = eligible.get(version_id)
            if version is None:
                raise ProblemException(
                    status=422,
                    code="invalid_source_version",
                    title="Unprocessable Entity",
                    detail="A requested source is not a processed source of this project.",
                )
            chosen.append(version)
        versions = chosen
    else:
        versions = list(eligible.values())

    if not versions and not allow_empty:
        raise ProblemException(
            status=422,
            code="no_valid_sources",
            title="Unprocessable Entity",
            detail="No processed source is available to start a run.",
        )
    return versions


def persist_snapshot(
    db: Session, run_id: str, versions: list[SourceVersion]
) -> None:
    for version in versions:
        db.add(
            RunSourceSnapshot(
                id=str(uuid.uuid4()),
                run_id=run_id,
                source_version_id=version.source_version_id,
                source_id=version.source_document_id,
            )
        )
    db.flush()


def is_source_referenced(db: Session, source_id: str) -> bool:
    """True if any of the source's versions is frozen in a run snapshot."""
    version_ids = list(
        db.scalars(
            select(SourceVersion.source_version_id).where(
                SourceVersion.source_document_id == source_id
            )
        )
    )
    if not version_ids:
        return False
    return (
        db.scalar(
            select(RunSourceSnapshot.id).where(
                RunSourceSnapshot.source_version_id.in_(version_ids)
            )
        )
        is not None
    )
