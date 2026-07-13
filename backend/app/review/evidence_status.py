"""Evidence-Statusleiter (R6) — deterministische Ableitung der 7-stufigen
Support-Skala aus bestehenden persistierten Zuständen. Keine neue Persistenz.

Kernaussage der Leiter: Coverage ≠ Correctness. Eine exakt gefundene
Textstelle (``exact_verified``) ist NUR ``location_found`` — fachliche
Stützung (``supports_*``) entsteht ausschliesslich aus der Reliability-
Bewertung (ClaimLineage), nie aus dem Fundstellen-Abgleich allein.

Stufen (Reihenfolge = zunehmende Stützung, Aggregation ist vorsichtig-zuerst):
    not_required            Kein Beleg erforderlich
    evidence_missing        Beleg fehlt
    location_found          Textstelle gefunden — fachliche Prüfung offen
    supports_partially      Teilweise gestützt
    supports_strongly       Stark gestützt
    conflict_or_uncertain   Widersprüchlich/unklar
    human_review_required   Menschliche Prüfung erforderlich

Unbekannte Eingabewerte fallen fail-closed auf ``human_review_required``.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

SUPPORT_STATUSES = (
    "not_required",
    "evidence_missing",
    "location_found",
    "supports_partially",
    "supports_strongly",
    "conflict_or_uncertain",
    "human_review_required",
)

# Aggregation: der vorsichtigste Status gewinnt (Index 0 = am vorsichtigsten).
_CAUTION_ORDER = (
    "conflict_or_uncertain",
    "human_review_required",
    "evidence_missing",
    "location_found",
    "supports_partially",
    "supports_strongly",
    "not_required",
)


def derive_anchor_support_status(
    verification_status: str,
    lineage_status: str | None = None,
    sufficiency_status: str | None = None,
) -> str:
    """Support-Status eines einzelnen Ankers (ggf. mit Reliability-Urteil).

    ``verification_status`` ist der technische Fundstellen-Abgleich
    (EvidenceAnchor); ``lineage_status``/``sufficiency_status`` sind das
    deterministische Reliability-Urteil (ClaimLineage), sofern vorhanden.
    """
    if verification_status == "rejected":
        return "conflict_or_uncertain"
    if verification_status == "unverified":
        return "human_review_required"
    if verification_status not in ("exact_verified", "human_verified"):
        return "human_review_required"  # fail-closed bei unbekanntem Wert

    # Fundstelle bestätigt, aber (noch) kein Reliability-Urteil: Coverage only.
    if lineage_status is None and sufficiency_status is None:
        return "location_found"

    if "needs_human_review" in (lineage_status, sufficiency_status):
        return "human_review_required"
    if (
        lineage_status == "conflicting_evidence"
        or sufficiency_status == "does_not_support_claim"
    ):
        return "conflict_or_uncertain"
    if sufficiency_status == "supports_claim":
        return (
            "supports_strongly"
            if lineage_status == "direct_evidence"
            else "supports_partially"
        )
    if sufficiency_status == "weakly_supports_claim" or lineage_status in (
        "indirect_evidence",
        "weak_evidence",
    ):
        return "supports_partially"
    if (
        lineage_status in ("no_evidence", None)
        and sufficiency_status == "insufficient_evidence"
    ):
        return "location_found"
    return "human_review_required"  # fail-closed bei unbekannter Kombination


def most_cautious(statuses: list[str]) -> str:
    """Vorsichtigster Status einer nichtleeren Liste (Aggregationsregel).
    Unbekannte Werte werden fail-closed als ``human_review_required`` gewertet."""
    normalized = [
        status if status in _CAUTION_ORDER else "human_review_required"
        for status in statuses
    ]
    return min(normalized, key=_CAUTION_ORDER.index)


def aggregate_field_support_status(
    evidence_requirement: str, anchor_statuses: list[str]
) -> str:
    """Feld-Aggregat: Registry-Anforderung + Status der aktiven Anker."""
    if not anchor_statuses:
        if evidence_requirement in ("required", "conditional"):
            return "evidence_missing"
        return "not_required"
    return most_cautious(anchor_statuses)


# --- DB-Helfer (read-only) ---------------------------------------------------


def lineage_by_anchor(db: Session, run_id: str) -> dict[str, list[tuple[str, str]]]:
    """Anker → Reliability-Urteile des Runs (aus ClaimLineage.provenance)."""
    from app.db.models import ClaimLineage

    result: dict[str, list[tuple[str, str]]] = {}
    rows = db.scalars(select(ClaimLineage).where(ClaimLineage.run_id == run_id))
    for lineage in rows:
        anchor_ids = (lineage.provenance or {}).get("evidence_anchor_ids") or []
        for anchor_id in anchor_ids:
            result.setdefault(anchor_id, []).append(
                (lineage.lineage_status, lineage.sufficiency_status)
            )
    return result


def support_status_for_anchor(
    verification_status: str, judgments: list[tuple[str, str]] | None
) -> str:
    """Anker-Status über alle Claims, die ihn referenzieren (vorsichtig-zuerst)."""
    if not judgments:
        return derive_anchor_support_status(verification_status)
    return most_cautious(
        [
            derive_anchor_support_status(verification_status, lineage, sufficiency)
            for lineage, sufficiency in judgments
        ]
    )
