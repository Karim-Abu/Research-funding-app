"""R3.2 — Import-Service: Kandidaten erzeugen + menschliche Entscheidungen.

Grundsätze:
- Upload/Klassifikation/Fail-closed laufen über den bestehenden Quellen-Pfad;
  hier wird nur eine bereits verarbeitete Quelle gemappt.
- Jede Entscheidung ist explizit menschlich; ``uncertain`` wird nie
  automatisch übernommen (es gibt schlicht keinen Auto-Pfad).
- «Übernehmen» nutzt den bestehenden Draft-Mechanismus (``apply_update``):
  Optimistic Concurrency, Zeichenlimit, ``recheck_required`` und
  Approval-Invalidierung kommen von dort — nichts wird nachgebaut.
- Nie stilles Überschreiben: existiert ein bearbeiteter Draft, wird der
  Kandidat als ``conflict`` markiert und braucht eine explizite Bestätigung.
- Audit-Details enthalten nur IDs/Zählwerte — nie ``extracted_text``.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.contracts.imports import ImportCandidate as ImportCandidateSchema
from app.db.models import (
    AnalysisRun,
    DraftVersion,
    ImportCandidate,
    SourceDocument,
    SourceVersion,
)
from app.exports.generators.common import EXPORT_FIELD_LABELS
from app.imports.mapping import MAPPING_VERSION, map_document
from app.ingestion.parsers import ParserError
from app.repositories import audit
from app.repositories import drafts as drafts_repo
from app.storage import get_storage

# Import-Scope R3: digitale PDF/TXT, kein OCR (docx/url bleiben normale Quellen).
_SUPPORTED_TYPES = ("pdf", "txt")

_TERMINAL_DECISIONS = ("accepted", "saved_as_source", "ignored")


def _problem(status: int, code: str, title: str, detail: str) -> ProblemException:
    return ProblemException(status=status, code=code, title=title, detail=detail)


def list_candidates(db: Session, project_id: str) -> list[ImportCandidate]:
    return list(
        db.scalars(
            select(ImportCandidate)
            .where(ImportCandidate.project_id == project_id)
            .order_by(ImportCandidate.created_at, ImportCandidate.field_id)
        )
    )


def create_candidates(
    db: Session, *, source: SourceDocument, actor_user_id: str
) -> list[ImportCandidate]:
    """Mappt eine verarbeitete Quelle auf die Portal-Felder (idempotent je
    Quellversion): erneuter Aufruf liefert die bestehenden Kandidaten."""
    if source.type not in _SUPPORTED_TYPES:
        raise _problem(
            422, "unsupported_import_type", "Unprocessable Entity",
            "Der Antragsimport unterstützt nur digitale PDF- oder Textquellen.",
        )
    if source.status != "processed" or not source.current_source_version_id:
        raise _problem(
            422, "source_not_processed", "Unprocessable Entity",
            "Die Quelle ist noch nicht verarbeitet. Bitte warten, bis die "
            "Verarbeitung abgeschlossen ist, oder die Datei manuell übertragen.",
        )
    version = db.get(SourceVersion, source.current_source_version_id)

    existing = list(
        db.scalars(
            select(ImportCandidate).where(
                ImportCandidate.source_version_id == version.source_version_id
            )
        )
    )
    if existing:
        if all(row.mapping_version == MAPPING_VERSION for row in existing):
            return existing
        if any(row.decision in _TERMINAL_DECISIONS for row in existing):
            raise _problem(
                409,
                "import_mapping_outdated_decided",
                "Conflict",
                "Für diese Dateiversion wurden bereits Importentscheidungen "
                "getroffen. Bitte die Datei erneut hochladen und bereits "
                "übernommene Entwürfe manuell prüfen.",
            )
        # Offene Kandidaten der alten Anchor-Logik dürfen sicher ersetzt
        # werden: keine menschliche Endentscheidung und kein Draft-Verweis.
        for row in existing:
            db.delete(row)
        db.flush()

    data = get_storage().open(version.storage_ref)
    try:
        result = map_document(source.type, data)
    except ParserError as exc:
        raise _problem(
            422, "import_parse_failed", "Unprocessable Entity",
            "Die Datei konnte nicht gelesen werden. Bitte einen digitalen "
            "PDF-Export verwenden (kein Scan).",
        ) from exc
    if result.needs_manual_input:
        # Defensive: eine solche Quelle wird nie "processed" — fail-closed.
        raise _problem(
            422, "import_needs_manual_input", "Unprocessable Entity",
            "Aus dieser Datei lässt sich kein Text extrahieren (z. B. Scan "
            "oder verschlüsseltes PDF). Bitte Inhalte manuell übertragen.",
        )

    candidates: list[ImportCandidate] = []
    for mapped in result.fields:
        candidates.append(
            ImportCandidate(
                import_candidate_id=str(uuid.uuid4()),
                workspace_id=source.workspace_id,
                project_id=source.project_id,
                source_id=source.source_id,
                source_version_id=version.source_version_id,
                field_id=mapped.field_id,
                extracted_text=mapped.extracted_text,
                confidence=mapped.confidence,
                source_location=mapped.source_location,
                mapping_version=mapped.mapping_version,
                mapping_status=mapped.mapping_status,
                section_metadata=[asdict(section) for section in mapped.sections],
                decision="pending",
            )
        )
        db.add(candidates[-1])
    db.flush()
    audit.record(
        db, workspace_id=source.workspace_id, actor_user_id=actor_user_id,
        action="import.candidates_created", target_type="source",
        target_id=source.source_id,
        detail={
            "candidate_count": len(candidates),
            "uncertain_count": sum(
                1 for c in candidates if c.confidence == "uncertain"
            ),
            "mapping_version": MAPPING_VERSION,
            "legacy_migrated_count": sum(
                1 for c in candidates if c.mapping_status == "legacy_migrated"
            ),
            "warnings": list(result.warnings),
        },
    )
    return candidates


def _mark_decided(
    candidate: ImportCandidate, decision: str, actor_user_id: str
) -> None:
    candidate.decision = decision
    candidate.decided_by = actor_user_id
    candidate.decided_at = datetime.now(timezone.utc)


def decide_candidate(
    db: Session,
    *,
    candidate: ImportCandidate,
    decision: str,
    run: AnalysisRun | None,
    confirm_overwrite: bool,
    actor_user_id: str,
    edited_text: str | None = None,
) -> ImportCandidate:
    if candidate.decision in _TERMINAL_DECISIONS:
        raise _problem(
            409, "import_already_decided", "Conflict",
            "Dieser Kandidat wurde bereits entschieden.",
        )
    if edited_text is not None and decision != "accepted":
        raise _problem(
            422, "edited_text_not_allowed", "Unprocessable Entity",
            "Ein bearbeiteter Text ist nur beim Übernehmen möglich.",
        )

    if (
        decision == "accepted"
        and edited_text is None
        and any(
            bool(section.get("requires_manual_assignment"))
            for section in (candidate.section_metadata or [])
        )
    ):
        raise _problem(
            422,
            "import_manual_assignment_required",
            "Unprocessable Entity",
            "Dieser Kandidat enthält eine mehrdeutige Altzuordnung. Bitte den "
            "Text unter «Bearbeiten & übernehmen» fachlich einordnen.",
        )

    if decision in ("saved_as_source", "ignored"):
        # Das Dokument liegt bereits als Quelle vor; «Als Quelle speichern»
        # protokolliert die Entscheidung, ohne einen Entwurf zu verändern.
        _mark_decided(candidate, decision, actor_user_id)
        audit.record(
            db, workspace_id=candidate.workspace_id, actor_user_id=actor_user_id,
            action="import.candidate_decided", target_type="import_candidate",
            target_id=candidate.import_candidate_id,
            detail={"decision": decision, "field_id": candidate.field_id},
        )
        db.flush()
        return candidate

    # --- decision == "accepted" — Übernahme in den Entwurf (HITL) -----------
    # «Bearbeitet übernommen»: der editierte Text zählt; extracted_text bleibt
    # als Originalausschnitt unverändert erhalten.
    effective_text = edited_text if edited_text is not None else candidate.extracted_text
    if not effective_text.strip():
        raise _problem(
            422, "import_candidate_empty", "Unprocessable Entity",
            "Dieser Kandidat enthält keinen Text — es gibt nichts zu übernehmen.",
        )
    if run is None:
        # Übernahme VOR dem ersten Analyse-Lauf: die Entscheidung wird
        # projektbezogen vorgemerkt (accepted_draft_version_id bleibt leer)
        # und beim nächsten Lauf in create_initial_draft als Entwurfsbasis
        # konsumiert. Kein Draft-Write ohne Run — Drafts sind run-gebunden.
        candidate.edited_text = edited_text
        _mark_decided(candidate, "accepted", actor_user_id)
        audit.record(
            db, workspace_id=candidate.workspace_id, actor_user_id=actor_user_id,
            action="import.candidate_decided", target_type="import_candidate",
            target_id=candidate.import_candidate_id,
            detail={
                "decision": "accepted",
                "field_id": candidate.field_id,
                "staged": True,
                "edited": edited_text is not None,
            },
        )
        db.flush()
        return candidate
    draft = drafts_repo.get_draft(db, run.run_id, candidate.field_id)
    if draft is None:
        raise _problem(
            409, "field_without_draft", "Conflict",
            "Für dieses Feld existiert in der aktuellen Analyse kein Entwurf.",
        )

    current = db.get(DraftVersion, draft.current_version_id)
    if current is not None and current.created_by != "template" and not confirm_overwrite:
        candidate.decision = "conflict"
        audit.record(
            db, workspace_id=candidate.workspace_id, actor_user_id=actor_user_id,
            action="import.candidate_conflict", target_type="import_candidate",
            target_id=candidate.import_candidate_id,
            detail={"field_id": candidate.field_id},
        )
        db.flush()
        raise _problem(
            409, "import_conflict", "Conflict",
            "Für dieses Feld existiert bereits ein bearbeiteter Entwurf. "
            "Übernehmen ersetzt den aktuellen Text — bitte explizit bestätigen.",
        )

    drafts_repo.apply_update(
        db, run, draft,
        base_version_id=draft.current_version_id,
        text=effective_text,
        source_operation_id=None,
        actor_user_id=actor_user_id,
        origin="import",
    )
    candidate.edited_text = edited_text
    _mark_decided(candidate, "accepted", actor_user_id)
    candidate.accepted_draft_version_id = draft.current_version_id
    audit.record(
        db, workspace_id=candidate.workspace_id, actor_user_id=actor_user_id,
        action="import.candidate_decided", target_type="import_candidate",
        target_id=candidate.import_candidate_id,
        detail={
            "decision": "accepted",
            "field_id": candidate.field_id,
            "draft_version_id": draft.current_version_id,
            "overwrite_confirmed": confirm_overwrite,
            "edited": edited_text is not None,
        },
    )
    db.flush()
    return candidate


def to_contract(candidate: ImportCandidate) -> ImportCandidateSchema:
    return ImportCandidateSchema(
        import_candidate_id=candidate.import_candidate_id,
        source_id=candidate.source_id,
        field_id=candidate.field_id,
        label=EXPORT_FIELD_LABELS.get(candidate.field_id, candidate.field_id),
        extracted_text=candidate.extracted_text,
        edited_text=candidate.edited_text,
        confidence=candidate.confidence,
        source_location=candidate.source_location,
        mapping_version=candidate.mapping_version,
        mapping_status=candidate.mapping_status,
        section_metadata=candidate.section_metadata or [],
        decision=candidate.decision,
        decided_at=candidate.decided_at,
        accepted_draft_version_id=candidate.accepted_draft_version_id,
    )
