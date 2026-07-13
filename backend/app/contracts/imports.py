"""R3.2 — Contracts für den Innolink-Antragsimport (HITL-Review-Flow)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ImportConfidence = Literal["found", "uncertain"]
ImportDecision = Literal["pending", "conflict", "accepted", "saved_as_source", "ignored"]
ImportMappingStatus = Literal[
    "content_detected", "empty", "legacy_migrated", "uncertain"
]


class ImportSectionMetadata(BaseModel):
    """Nachvollziehbare Abschnittszuordnung innerhalb eines Importkandidaten.

    ``candidate_text`` und ``original_excerpt`` können D2 enthalten und dürfen
    deshalb nie in Logs oder Audit-Details kopiert werden.
    """

    model_config = ConfigDict(extra="forbid")

    target_sections: list[str]
    source_location: str | None = None
    status: ImportMappingStatus
    candidate_text: str
    original_excerpt: str
    migration_version: str | None = None
    requires_manual_assignment: bool = False
    review_note: str | None = None


class ImportCandidate(BaseModel):
    """Ein erkanntes Feld aus einem hochgeladenen Antrag — wartet auf die
    explizite menschliche Entscheidung (kein Auto-Accept, nie bei uncertain)."""

    model_config = ConfigDict(extra="forbid")

    import_candidate_id: str
    source_id: str
    field_id: str
    # Deutsches Anzeige-Label (EXPORT_FIELD_LABELS) — UI zeigt nie rohe IDs.
    label: str
    extracted_text: str
    # «Bearbeitet übernommen»: editierter Text; extracted_text bleibt das
    # unveränderte Original (additiv, None = unbearbeitet übernommen).
    edited_text: str | None = None
    confidence: ImportConfidence
    source_location: str | None = None
    mapping_version: str = "legacy-anchor-v1"
    mapping_status: ImportMappingStatus = "uncertain"
    section_metadata: list[ImportSectionMetadata] = Field(default_factory=list)
    decision: ImportDecision
    decided_at: datetime | None = None
    accepted_draft_version_id: str | None = None


class ImportCandidatesCreate(BaseModel):
    """Upload läuft über den bestehenden Quellen-Endpoint; hier wird eine
    bereits verarbeitete Quelle auf die Portal-Felder gemappt."""

    model_config = ConfigDict(extra="forbid")

    source_id: str


class ImportDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["accepted", "saved_as_source", "ignored"]
    # Optional bei accepted: mit run_id wird sofort in den Run-Draft
    # geschrieben; ohne run_id wird die Übernahme projektbezogen vorgemerkt
    # und beim nächsten Analyse-Lauf als Entwurfsbasis konsumiert.
    run_id: str | None = None
    # «Bearbeitet übernommen» (nur bei accepted): der editierte Text.
    edited_text: str | None = None
    # Explizite Bestätigung, wenn ein bearbeiteter Draft überschrieben würde.
    confirm_overwrite: bool = False
