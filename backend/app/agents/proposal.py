"""Typisierte DraftProposal-/AIProposal-Views für A2 (Post-Gateway).

Kein Contract-Schema: der Gateway-Output bleibt ``PortalFieldDraftBundle@v1``
(eingefrorene YAML). ``DraftProposal`` ist der neutrale View; ``AIProposal``
wird ausschließlich nach einem echten Modellaufruf befüllt. Beide sind nicht
in ``SCHEMA_MODELS`` registriert.

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

from app.agents.generation import GenerationKind, MODEL_GENERATED
from app.db.models import AgentInvocation, DraftSuggestion


class MissingInputRecord(BaseModel):
    """Fehlende Angabe (spiegelt PlaceholderRecord: label + reason)."""

    model_config = ConfigDict(extra="forbid")

    label: str
    reason: str | None = None


class DraftProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestion_text: str
    used_anchor_ids: list[str] = []
    missing_inputs: list[MissingInputRecord] = []
    profile_id: str
    prompt_version: str | None = None
    context_hash: str | None = None
    generation_kind: GenerationKind | None = None
    model_ref: str | None = None
    created_at: datetime
    data_mode: str
    provider: str | None = None
    model: str | None = None
    usage_record_id: str | None = None
    safety_notes: list[str] = []
    # No-Auto-Accept im Typ selbst: jeder Wert ausser True ist invalide.
    human_review_required: Literal[True] = True


class AIProposal(DraftProposal):
    """Compatibility view emitted only after a successful real model call."""

    generation_kind: Literal["model_generated"] = "model_generated"
    model_ref: str
    provider: str
    model: str


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
) -> DraftProposal:
    """Neutralen DraftProposal-View aus Suggestion und Invocation erstellen.

    Total (keine Raise-Pfade ausser pydantic): fehlende Invocation (z. B.
    Legacy-Reused-Pfad) fällt auf die Suggestion-Spalten zurück. provider/model
    kommen aus der Invocation — ``DraftSuggestion.model_route`` speichert den
    Provider-Wert der Route, nicht die tatsächlich bediente Kombination.
    """
    meta = (invocation.context_meta or {}) if invocation else {}
    kind = suggestion.generation_kind or meta.get("generation_kind")
    real = kind == MODEL_GENERATED and bool(meta.get("model_call_attempted"))
    provider = invocation.provider if invocation is not None and real else None
    model = invocation.model_id if invocation is not None and real else None
    proposal_type = AIProposal if real else DraftProposal
    return proposal_type(
        suggestion_text=suggestion.suggested_text,
        used_anchor_ids=list(suggestion.evidence_anchor_ids or []),
        missing_inputs=[
            MissingInputRecord(**p) for p in (suggestion.placeholders or [])
        ],
        profile_id=suggestion.profile_id,
        prompt_version=suggestion.prompt_version if real else None,
        context_hash=meta.get("context_hash"),
        generation_kind=kind,
        model_ref=f"{provider}:{model}" if real else None,
        created_at=suggestion.created_at,
        data_mode=data_mode,
        provider=provider,
        model=model,
        usage_record_id=invocation.usage_record_id if invocation is not None and real else None,
        safety_notes=list(safety_notes or []),
    )
