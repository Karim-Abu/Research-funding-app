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
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.api.errors import ProblemException
from app.contracts.imports import (
    ImportCandidate as ImportCandidateSchema,
    StructuredImportCandidate as StructuredImportCandidateSchema,
    StructuredImportProvenance,
    StructuredImportSummary,
    StructuredImportSummaryCounts,
)
from app.contracts.partner import PartnerCreate
from app.contracts.project import ProjectPatch
from app.db.models import (
    AnalysisRun,
    DraftVersion,
    ImportCandidate,
    Partner,
    Project,
    SourceDocument,
    SourceVersion,
    StructuredImportCandidate,
)
from app.exports.generators.common import EXPORT_FIELD_LABELS
from app.imports.mapping import (
    MAPPING_VERSION,
    STRUCTURED_MAPPING_VERSION,
    map_document,
    structured_label,
)
from app.ingestion.parsers import ParserError
from app.repositories import audit
from app.repositories import drafts as drafts_repo
from app.repositories import partners as partners_repo
from app.repositories import projects as projects_repo
from app.runs import project_snapshot
from app.storage import get_storage

# Import-Scope R3: digitale PDF/TXT, kein OCR (docx/url bleiben normale Quellen).
_SUPPORTED_TYPES = ("pdf", "txt")

_TERMINAL_DECISIONS = ("accepted", "saved_as_source", "ignored")
_STRUCTURED_TERMINAL_DECISIONS = ("accepted", "ignored")


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


def list_structured_candidates(
    db: Session, project_id: str
) -> list[StructuredImportCandidate]:
    return list(
        db.scalars(
            select(StructuredImportCandidate)
            .where(StructuredImportCandidate.project_id == project_id)
            .order_by(
                StructuredImportCandidate.created_at,
                StructuredImportCandidate.candidate_kind,
                StructuredImportCandidate.target_key,
            )
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
    create_narrative = not existing
    if existing:
        if all(row.mapping_version == MAPPING_VERSION for row in existing):
            create_narrative = False
        else:
            if any(row.decision in _TERMINAL_DECISIONS for row in existing):
                raise _problem(
                    409,
                    "import_mapping_outdated_decided",
                    "Conflict",
                    "Für diese Dateiversion wurden bereits Importentscheidungen "
                    "getroffen. Bitte die Datei erneut hochladen und bereits "
                    "übernommene Entwürfe manuell prüfen.",
                )
            for row in existing:
                db.delete(row)
            db.flush()
            existing = []
            create_narrative = True

    structured_existing = list(
        db.scalars(
            select(StructuredImportCandidate).where(
                StructuredImportCandidate.source_version_id
                == version.source_version_id
            )
        )
    )
    if structured_existing and any(
        row.mapping_version != STRUCTURED_MAPPING_VERSION
        for row in structured_existing
    ):
        if any(
            row.decision in _STRUCTURED_TERMINAL_DECISIONS
            for row in structured_existing
        ):
            raise _problem(
                409,
                "structured_import_mapping_outdated_decided",
                "Conflict",
                "Für diese Dateiversion wurden bereits strukturierte "
                "Importentscheidungen getroffen. Bitte die Datei erneut hochladen.",
            )
        for row in structured_existing:
            db.delete(row)
        db.flush()
        structured_existing = []

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

    candidates: list[ImportCandidate] = list(existing)
    if create_narrative:
        for mapped in result.fields:
            candidates.append(ImportCandidate(
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
            ))
            db.add(candidates[-1])

    structured_by_key = {
        (row.candidate_kind, row.target_key): row for row in structured_existing
    }
    structured_created: list[StructuredImportCandidate] = []
    for mapped in result.structured_candidates:
        key = (mapped.candidate_kind, mapped.target_key)
        if key in structured_by_key:
            continue
        row = StructuredImportCandidate(
            candidate_id=str(uuid.uuid4()),
            workspace_id=source.workspace_id,
            project_id=source.project_id,
            source_id=source.source_id,
            source_version_id=version.source_version_id,
            candidate_kind=mapped.candidate_kind,
            target_key=mapped.target_key,
            payload_json=mapped.payload_json,
            confidence=mapped.confidence,
            source_location=mapped.source_location,
            mapping_version=mapped.mapping_version,
            decision="pending",
        )
        db.add(row)
        structured_created.append(row)
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
            "structured_candidate_count": len(result.structured_candidates),
            "structured_created_count": len(structured_created),
            "structured_kind_counts": {
                kind: sum(
                    1
                    for item in result.structured_candidates
                    if item.candidate_kind == kind
                )
                for kind in ("project_metadata", "partner", "budget", "answer")
            },
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


_PROJECT_TARGET_FIELDS = {
    "project.title": "title",
    "project.title_en": "title_en",
    "project.start_date": "start_date",
    "project.end_date": "end_date",
    "project.duration_months": "duration_months",
    "project.direct_total_project_costs_excluding_overhead": (
        "direct_total_project_costs_excluding_overhead"
    ),
    "project.implementation_own_contribution": "implementation_own_contribution",
    "project.cash_contribution": "cash_contribution",
    "project.total_requested_funding": "total_requested_funding",
    "project.total_requested_funding_including_overhead": (
        "total_requested_funding_including_overhead"
    ),
}
_PARTNER_METADATA_KEYS = {"personnel_answers", "financial_confirmations"}
_PARTNER_PAYLOAD_KEYS = {
    "name",
    "partner_type",
    "project_role",
    "country",
    "location",
    "department",
    "contribution",
    "uid",
    "industry",
    "fte",
    "startup_status",
    "swiss_value_creation",
    "research_partner_eligibility_status",
    "official_representative",
    "personnel_independence_status",
    "financial_independence_status",
    "review_comment",
}


def _effective_payload(candidate: StructuredImportCandidate) -> dict[str, Any]:
    return candidate.edited_payload_json or candidate.payload_json


def _json_value(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _normal_name(value: str) -> str:
    return " ".join(value.casefold().split())


def _clean_partner_payload(payload: dict[str, Any]) -> dict[str, Any]:
    unknown = set(payload) - _PARTNER_PAYLOAD_KEYS - _PARTNER_METADATA_KEYS
    if unknown:
        raise _problem(
            422,
            "structured_import_payload_invalid",
            "Unprocessable Entity",
            "Die bearbeiteten Partnerangaben enthalten unbekannte Felder.",
        )
    clean = {key: value for key, value in payload.items() if key in _PARTNER_PAYLOAD_KEYS}
    representative = clean.get("official_representative")
    if representative is not None:
        if not isinstance(representative, dict) or set(representative) - {"display_name"}:
            raise _problem(
                422,
                "structured_import_contact_pii_not_allowed",
                "Unprocessable Entity",
                "Beim PDF-Import wird nur der Name der offiziellen Vertretung übernommen.",
            )
        display_name = representative.get("display_name")
        if not isinstance(display_name, str) or "@" in display_name:
            raise _problem(
                422,
                "structured_import_contact_pii_not_allowed",
                "Unprocessable Entity",
                "Kontaktangaben dürfen nicht über den PDF-Import übernommen werden.",
            )
    return clean


def _validate_structured_payload(
    candidate: StructuredImportCandidate, payload: dict[str, Any]
) -> dict[str, Any]:
    if candidate.candidate_kind in {"project_metadata", "budget"}:
        field = _PROJECT_TARGET_FIELDS.get(candidate.target_key)
        if field is None or set(payload) != {field} or payload.get(field) is None:
            raise _problem(
                422,
                "structured_import_payload_invalid",
                "Unprocessable Entity",
                "Bitte einen gültigen Wert für dieses Projektfeld erfassen.",
            )
        try:
            ProjectPatch(**{field: payload[field]})
        except ValidationError as exc:
            raise _problem(
                422,
                "structured_import_payload_invalid",
                "Unprocessable Entity",
                "Der erkannte Projektwert hat kein gültiges Format.",
            ) from exc
        return {field: payload[field]}

    if candidate.candidate_kind == "partner":
        clean = _clean_partner_payload(payload)
        try:
            validated = PartnerCreate(**clean)
        except ValidationError as exc:
            raise _problem(
                422,
                "structured_import_payload_invalid",
                "Unprocessable Entity",
                "Bitte die Partnerangaben vollständig und gültig erfassen.",
            ) from exc
        if partners_repo.review_comment_required(validated) and not (
            validated.review_comment or ""
        ).strip():
            raise _problem(
                422,
                "partner_comment_required",
                "Unprocessable Entity",
                "Bitte die unklare Unabhängigkeitsangabe kurz kommentieren.",
            )
        return clean

    if candidate.target_key == "answer.scientific_integrity":
        if set(payload) - {"sanction_answer", "comment"} or not isinstance(
            payload.get("sanction_answer"), bool
        ):
            raise _problem(
                422,
                "structured_import_payload_invalid",
                "Unprocessable Entity",
                "Bitte die Scientific-Integrity-Antwort mit Ja oder Nein bestätigen.",
            )
        comment = payload.get("comment")
        if payload["sanction_answer"] is True and not (
            isinstance(comment, str) and comment.strip()
        ):
            raise _problem(
                422,
                "scientific_integrity_comment_required",
                "Unprocessable Entity",
                "Bei Ja ist ein Kommentar und eine menschliche Prüfung erforderlich.",
            )
        return {"sanction_answer": payload["sanction_answer"], "comment": comment}

    if candidate.target_key == "answer.management_hours":
        if set(payload) - {"management_hours", "total_project_hours"}:
            raise _problem(
                422,
                "structured_import_payload_invalid",
                "Unprocessable Entity",
                "Die Management-Stunden enthalten unbekannte Felder.",
            )
        hours = payload.get("management_hours")
        total = payload.get("total_project_hours")
        if (
            isinstance(hours, bool)
            or not isinstance(hours, (int, float))
            or hours < 0
            or isinstance(total, bool)
            or (total is not None and (not isinstance(total, (int, float)) or total < hours))
        ):
            raise _problem(
                422,
                "structured_import_payload_invalid",
                "Unprocessable Entity",
                "Bitte gültige, nicht negative Management-Stunden erfassen.",
            )
        return {"management_hours": hours, "total_project_hours": total}

    raise _problem(
        422,
        "structured_import_target_unknown",
        "Unprocessable Entity",
        "Dieses strukturierte Importziel wird nicht unterstützt.",
    )


def _partner_contract_payload(partner: Partner, *, safe: bool = True) -> dict[str, Any]:
    representative = partner.official_representative
    if safe and representative:
        representative = {"display_name": representative.get("display_name")}
    return {
        "name": partner.name,
        "partner_type": partner.partner_type,
        "project_role": partner.project_role,
        "country": partner.country,
        "location": partner.location,
        "department": partner.department,
        "contribution": partner.contribution,
        "uid": partner.uid,
        "industry": partner.industry,
        "fte": partner.fte,
        "startup_status": partner.startup_status,
        "swiss_value_creation": partner.swiss_value_creation,
        "research_partner_eligibility_status": (
            partner.research_partner_eligibility_status
        ),
        "official_representative": representative,
        "personnel_independence_status": partner.personnel_independence_status,
        "financial_independence_status": partner.financial_independence_status,
        "review_comment": partner.review_comment,
    }


def _matching_partners(
    db: Session, candidate: StructuredImportCandidate, payload: dict[str, Any]
) -> list[Partner]:
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        return []
    wanted = _normal_name(name)
    return [
        partner
        for partner in partners_repo.list_by_project(
            db, candidate.project_id, candidate.workspace_id
        )
        if _normal_name(partner.name) == wanted
    ]


def _latest_answer(
    db: Session, candidate: StructuredImportCandidate
) -> StructuredImportCandidate | None:
    return db.scalar(
        select(StructuredImportCandidate)
        .where(
            StructuredImportCandidate.project_id == candidate.project_id,
            StructuredImportCandidate.workspace_id == candidate.workspace_id,
            StructuredImportCandidate.candidate_kind == "answer",
            StructuredImportCandidate.target_key == candidate.target_key,
            StructuredImportCandidate.decision == "accepted",
            StructuredImportCandidate.candidate_id != candidate.candidate_id,
        )
        .order_by(StructuredImportCandidate.decided_at.desc())
        .limit(1)
    )


def _structured_current_state(
    db: Session,
    candidate: StructuredImportCandidate,
    payload: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    if candidate.candidate_kind in {"project_metadata", "budget"}:
        project = db.get(Project, candidate.project_id)
        field = _PROJECT_TARGET_FIELDS.get(candidate.target_key)
        current = getattr(project, field) if project is not None and field else None
        current_json = {field: _json_value(current)} if field and current is not None else None
        if current_json is not None and current_json != payload:
            return current_json, "existing_project_value"
        return current_json, None

    if candidate.candidate_kind == "partner":
        matches = _matching_partners(db, candidate, payload)
        if len(matches) > 1:
            return None, "multiple_exact_partner_matches"
        if not matches:
            return None, None
        current = _partner_contract_payload(matches[0], safe=True)
        clean = _clean_partner_payload(payload)
        differs = any(
            value is not None and current.get(key) != value
            for key, value in clean.items()
        )
        return current, "existing_partner_value" if differs else None

    previous = _latest_answer(db, candidate)
    if previous is None:
        return None, None
    current = _effective_payload(previous)
    return current, "existing_answer_value" if current != payload else None


def to_structured_contract(
    db: Session, candidate: StructuredImportCandidate
) -> StructuredImportCandidateSchema:
    effective = _effective_payload(candidate)
    current, conflict = _structured_current_state(db, candidate, effective)
    return StructuredImportCandidateSchema(
        candidate_id=candidate.candidate_id,
        source_id=candidate.source_id,
        candidate_kind=candidate.candidate_kind,
        target_key=candidate.target_key,
        label=structured_label(candidate.target_key),
        payload_json=candidate.payload_json,
        edited_payload_json=candidate.edited_payload_json,
        effective_payload_json=effective,
        confidence=candidate.confidence,
        source_location=candidate.source_location,
        mapping_version=candidate.mapping_version,
        decision=candidate.decision,
        decided_at=candidate.decided_at,
        applied_resource_id=candidate.applied_resource_id,
        current_value_json=current,
        has_conflict=conflict is not None,
        conflict_reason=conflict,
        requires_manual_edit=candidate.confidence == "uncertain",
    )


def decide_structured_candidate(
    db: Session,
    *,
    candidate: StructuredImportCandidate,
    decision: str,
    actor_user_id: str,
    edited_payload_json: dict[str, Any] | None = None,
    confirm_overwrite: bool = False,
) -> StructuredImportCandidate:
    if candidate.decision in _STRUCTURED_TERMINAL_DECISIONS:
        raise _problem(
            409,
            "structured_import_already_decided",
            "Conflict",
            "Dieser strukturierte Kandidat wurde bereits entschieden.",
        )
    if edited_payload_json is not None and decision != "accepted":
        raise _problem(
            422,
            "structured_import_edit_not_allowed",
            "Unprocessable Entity",
            "Bearbeitete Werte sind nur beim Übernehmen erlaubt.",
        )
    if decision == "ignored":
        candidate.decision = "ignored"
        candidate.decided_by = actor_user_id
        candidate.decided_at = datetime.now(timezone.utc)
        audit.record(
            db,
            workspace_id=candidate.workspace_id,
            actor_user_id=actor_user_id,
            action="structured_import.candidate_decided",
            target_type="structured_import_candidate",
            target_id=candidate.candidate_id,
            detail={
                "decision": "ignored",
                "candidate_kind": candidate.candidate_kind,
                "target_key": candidate.target_key,
            },
        )
        db.flush()
        return candidate

    if candidate.confidence == "uncertain" and edited_payload_json is None:
        raise _problem(
            422,
            "structured_import_manual_edit_required",
            "Unprocessable Entity",
            "Dieser Wert ist unsicher. Bitte prüfen und bearbeiten Sie ihn vor der Übernahme.",
        )
    effective = edited_payload_json or candidate.payload_json
    validated = _validate_structured_payload(candidate, effective)
    current, conflict = _structured_current_state(db, candidate, validated)
    if conflict == "multiple_exact_partner_matches":
        candidate.decision = "conflict"
        db.flush()
        raise _problem(
            409,
            "structured_import_partner_ambiguous",
            "Conflict",
            "Mehrere bestehende Partner haben denselben Namen. Bitte den Kandidaten ignorieren und den Partner manuell zuordnen.",
        )
    if conflict and not confirm_overwrite:
        candidate.decision = "conflict"
        audit.record(
            db,
            workspace_id=candidate.workspace_id,
            actor_user_id=actor_user_id,
            action="structured_import.candidate_conflict",
            target_type="structured_import_candidate",
            target_id=candidate.candidate_id,
            detail={
                "candidate_kind": candidate.candidate_kind,
                "target_key": candidate.target_key,
                "reason": conflict,
            },
        )
        db.flush()
        raise _problem(
            409,
            "structured_import_conflict",
            "Conflict",
            "Es besteht bereits ein abweichender Wert. Bitte den Vergleich prüfen und das Überschreiben ausdrücklich bestätigen.",
        )

    project = db.get(Project, candidate.project_id)
    if project is None:
        raise _problem(404, "not_found", "Resource not found", "Project not found.")
    changed = False
    applied_resource_id = project.project_id
    if candidate.candidate_kind in {"project_metadata", "budget"}:
        field = _PROJECT_TARGET_FIELDS[candidate.target_key]
        before = _json_value(getattr(project, field))
        patch = ProjectPatch(**validated)
        projects_repo.apply_patch(db, project, patch)
        changed = before != _json_value(getattr(project, field))
    elif candidate.candidate_kind == "partner":
        matches = _matching_partners(db, candidate, validated)
        if matches:
            partner = matches[0]
            merged = _partner_contract_payload(partner, safe=False)
            merged.update(
                {key: value for key, value in validated.items() if value is not None}
            )
            data = PartnerCreate(**merged)
            changed = _partner_contract_payload(partner, safe=False) != data.model_dump()
            if changed:
                partners_repo.replace(db, partner, data)
        else:
            data = PartnerCreate(**validated)
            partner = partners_repo.create(
                db,
                project_id=candidate.project_id,
                workspace_id=candidate.workspace_id,
                created_by=actor_user_id,
                data=data,
            )
            changed = True
        applied_resource_id = partner.partner_id
    else:
        previous = _latest_answer(db, candidate)
        changed = current != validated
        if previous is not None:
            candidate.supersedes_candidate_id = previous.candidate_id

    candidate.edited_payload_json = edited_payload_json
    candidate.decision = "accepted"
    candidate.decided_by = actor_user_id
    candidate.decided_at = datetime.now(timezone.utc)
    candidate.applied_resource_id = applied_resource_id
    if changed:
        project_snapshot.mark_current_runs_stale(
            db, project=project, actor_user_id=actor_user_id
        )
    audit.record(
        db,
        workspace_id=candidate.workspace_id,
        actor_user_id=actor_user_id,
        action="structured_import.candidate_decided",
        target_type="structured_import_candidate",
        target_id=candidate.candidate_id,
        detail={
            "decision": "accepted",
            "candidate_kind": candidate.candidate_kind,
            "target_key": candidate.target_key,
            "applied_resource_id": applied_resource_id,
            "edited": edited_payload_json is not None,
            "changed": changed,
        },
    )
    db.flush()
    return candidate


def structured_summary(db: Session, project_id: str) -> StructuredImportSummary:
    rows = list_structured_candidates(db, project_id)

    def counts(kind: str) -> StructuredImportSummaryCounts:
        selected = [row for row in rows if row.candidate_kind == kind]
        reviewed = sum(
            row.decision in _STRUCTURED_TERMINAL_DECISIONS for row in selected
        )
        return StructuredImportSummaryCounts(
            detected=len(selected),
            reviewed=reviewed,
            unchecked=len(selected) - reviewed,
        )

    provenance: list[StructuredImportProvenance] = []
    for row in rows:
        if (
            row.decision != "accepted"
            or row.candidate_kind not in {"partner", "budget"}
            or not row.applied_resource_id
        ):
            continue
        effective = _effective_payload(row)
        state = "confirmed"
        if row.candidate_kind == "partner":
            partner = db.get(Partner, row.applied_resource_id)
            if partner is None:
                state = "missing"
            else:
                current = _partner_contract_payload(partner, safe=True)
                clean = _clean_partner_payload(effective)
                if any(
                    value is not None and current.get(key) != value
                    for key, value in clean.items()
                ):
                    state = "changed_after_import"
        else:
            project = db.get(Project, row.project_id)
            field = _PROJECT_TARGET_FIELDS.get(row.target_key)
            if project is None or field is None:
                state = "missing"
            elif {_PROJECT_TARGET_FIELDS[row.target_key]: _json_value(getattr(project, field))} != effective:
                state = "changed_after_import"
        provenance.append(
            StructuredImportProvenance(
                candidate_kind=row.candidate_kind,
                target_key=row.target_key,
                applied_resource_id=row.applied_resource_id,
                source_location=row.source_location,
                state=state,
            )
        )
    return StructuredImportSummary(
        partners=counts("partner"),
        budget=counts("budget"),
        provenance=provenance,
    )


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
