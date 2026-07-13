"""R5.2 — AIProposal: typisiertes Schema für A2-Feldvorschläge (Post-Gateway).

Kein Contract-Schema: der Gateway-Output bleibt ``PortalFieldDraftBundle@v1``
(eingefrorene YAML); AIProposal ist der interne, typisierte Pin für die
Persistenz-/View-Schicht und wird NICHT in ``SCHEMA_MODELS`` registriert.

Regeln (Ticket R5.2):
- ``used_anchor_ids`` dürfen nur aus ``allowed_anchor_ids`` stammen
  (``proposal_anchor_violations``, Muster ``fact_reference_violations``).
- ``missing_inputs`` statt erfundener Angaben (gespiegelt aus den
  Bundle-Placeholders).
- ``human_review_required`` ist im Typ auf ``Literal[True]`` fixiert —
  keine automatische Übernahme, keine finale Freigabe ohne Review.
- Keine Rohprompts/Rohantworten: das Proposal trägt nur den Vorschlagstext,
  IDs, Hashes und Metering-Metadaten.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict

from app.db.models import AgentInvocation, DraftSuggestion


class MissingInputRecord(BaseModel):
    """Fehlende Angabe (spiegelt PlaceholderRecord: label + reason)."""

    model_config = ConfigDict(extra="forbid")

    label: str
    reason: str | None = None


class AIProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestion_text: str
    used_anchor_ids: list[str] = []
    missing_inputs: list[MissingInputRecord] = []
    profile_id: str
    prompt_version: str | None = None
    context_hash: str | None = None
    model_ref: str
    created_at: datetime
    data_mode: str
    provider: str
    model: str
    usage_record_id: str | None = None
    safety_notes: list[str] = []
    # No-Auto-Accept im Typ selbst: jeder Wert ausser True ist invalide.
    human_review_required: Literal[True] = True


def proposal_anchor_violations(
    used_anchor_ids: Iterable[str], allowed_anchor_ids: set[str]
) -> list[str]:
    """Anchor-IDs, die nicht aus der erlaubten Menge stammen (leer = ok)."""
    return [a for a in used_anchor_ids if a not in allowed_anchor_ids]


def build_proposal(
    suggestion: DraftSuggestion,
    invocation: AgentInvocation | None,
    *,
    data_mode: str,
    safety_notes: list[str] | None = None,
) -> AIProposal:
    """AIProposal aus persistierter Suggestion + zugehöriger Invocation.

    Total (keine Raise-Pfade ausser pydantic): fehlende Invocation (z. B.
    Legacy-Reused-Pfad) fällt auf die Suggestion-Spalten zurück. provider/model
    kommen aus der Invocation — ``DraftSuggestion.model_route`` speichert den
    Provider-Wert der Route, nicht die tatsächlich bediente Kombination.
    """
    provider = (
        invocation.provider if invocation else (suggestion.model_route or "unknown")
    )
    model = invocation.model_id if invocation else (suggestion.model_id or "unknown")
    meta = (invocation.context_meta or {}) if invocation else {}
    return AIProposal(
        suggestion_text=suggestion.suggested_text,
        used_anchor_ids=list(suggestion.evidence_anchor_ids or []),
        missing_inputs=[
            MissingInputRecord(**p) for p in (suggestion.placeholders or [])
        ],
        profile_id=suggestion.profile_id,
        prompt_version=suggestion.prompt_version,
        context_hash=meta.get("context_hash"),
        model_ref=f"{provider}:{model}",
        created_at=suggestion.created_at,
        data_mode=data_mode,
        provider=provider,
        model=model,
        usage_record_id=invocation.usage_record_id if invocation else None,
        safety_notes=list(safety_notes or []),
    )
