"""Formal evidence scope shared by deterministic and A1 retrieval."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisRun,
    RunProjectSnapshot,
    RunSourceSnapshot,
    SourceDocument,
    SourceVersion,
)

_GENERATED_MARKERS = (
    "generated output",
    "ki-entwurf",
    "ai draft",
    "review package",
    "review finding",
    "qualitätsprüfung",
)


@dataclass(frozen=True, slots=True)
class FormalEvidenceScope:
    status: str
    source_id: str | None
    source_version_id: str | None
    reason_code: str | None = None


def is_generated_or_review_source(document: SourceDocument | None) -> bool:
    if document is None:
        return True
    name = (document.name or "").casefold()
    return any(marker in name for marker in _GENERATED_MARKERS)


def formal_application_scope(
    db: Session, run: AnalysisRun
) -> FormalEvidenceScope:
    snapshot = db.get(RunProjectSnapshot, run.run_id)
    project_json = snapshot.project_json if snapshot is not None else {}
    source_id = project_json.get("primary_application_source_id")
    version_id = project_json.get("primary_application_source_version_id")
    status = project_json.get("primary_application_status") or "not_configured"
    if not source_id or not version_id:
        return FormalEvidenceScope(
            status=status,
            source_id=None,
            source_version_id=None,
            reason_code=(
                "primary_application_needs_selection"
                if status == "needs_selection"
                else "primary_application_not_configured"
            ),
        )
    frozen = db.scalar(
        select(RunSourceSnapshot.id).where(
            RunSourceSnapshot.run_id == run.run_id,
            RunSourceSnapshot.source_id == source_id,
            RunSourceSnapshot.source_version_id == version_id,
        )
    )
    version = db.get(SourceVersion, version_id)
    document = db.get(SourceDocument, source_id)
    if (
        frozen is None
        or version is None
        or version.source_document_id != source_id
        or document is None
        or document.project_id != run.project_id
        or document.workspace_id != run.workspace_id
    ):
        return FormalEvidenceScope(
            status="invalid",
            source_id=source_id,
            source_version_id=version_id,
            reason_code="primary_application_snapshot_mismatch",
        )
    if is_generated_or_review_source(document):
        return FormalEvidenceScope(
            status="rejected",
            source_id=source_id,
            source_version_id=version_id,
            reason_code="generated_or_review_content",
        )
    return FormalEvidenceScope("configured", source_id, version_id)


def application_source(
    db: Session, run: AnalysisRun
) -> tuple[SourceVersion, SourceDocument] | None:
    scope = formal_application_scope(db, run)
    if scope.status != "configured" or scope.source_version_id is None:
        return None
    version = db.get(SourceVersion, scope.source_version_id)
    document = db.get(SourceDocument, scope.source_id)
    if version is None or document is None or version.normalized_text is None:
        return None
    return version, document


def candidate_in_application_scope(
    db: Session,
    run: AnalysisRun,
    *,
    source_id: str,
    source_version_id: str,
) -> tuple[bool, str | None]:
    scope = formal_application_scope(db, run)
    if scope.status != "configured":
        return False, scope.reason_code
    if source_id != scope.source_id:
        return False, "application_source_not_primary"
    if source_version_id != scope.source_version_id:
        return False, "primary_application_version_mismatch"
    return True, None


def source_scope(
    db: Session,
    run: AnalysisRun,
    *,
    document: SourceDocument | None,
    source_version_id: str,
) -> tuple[str, bool]:
    """Label frozen context without promoting it to formal requirement evidence."""
    formal = formal_application_scope(db, run)
    if (
        document is not None
        and formal.status == "configured"
        and document.source_id == formal.source_id
        and source_version_id == formal.source_version_id
    ):
        return "application", True
    classification = document.data_classification if document is not None else {}
    if (
        document is not None
        and (
            document.source_url is not None
            or classification.get("origin")
            in {"public_source", "public_web", "external_public"}
            or classification.get("web_research_mode") == "validated_public"
        )
    ):
        return "external", False
    return "drafting_context", False
