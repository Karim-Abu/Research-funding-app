"""R3.2 — Contracts für den Innolink-Antragsimport (HITL-Review-Flow)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ImportConfidence = Literal["found", "uncertain"]
ImportDecision = Literal["pending", "conflict", "accepted", "saved_as_source", "ignored"]


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
