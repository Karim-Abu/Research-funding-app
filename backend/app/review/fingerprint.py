"""Finding-Fingerprint + Display-Group-Key (R2.1).

Zwei getrennte Konzepte, bewusst nicht vermischt:

- ``compute_finding_fingerprint`` — stabile technische Identität EINES
  Findings (sha256 über Familie, Feld, normalisierten claim_core, source_id).
  Zahlen werden maskiert, damit derselbe Claim mit anderer Zahl denselben
  Fingerprint behält (Idempotenz/Dedupe auf Row-Ebene).
- ``compute_display_group_key`` — Schlüssel für die UI-Gruppierung
  gleichartiger Meldungen: ``severity_class + Meldungsfamilie (+ optional
  field_group)``. Enthält NIE den claim_core: die einzelnen Claims bleiben
  nur als Beispiele innerhalb der Gruppe sichtbar, und es landet kein
  Roh-Claim-Text in Gruppenschlüsseln (Logs/URLs).

Reines Rechenmodul: kein DB-Zugriff, kein Logging, keine Seiteneffekte.
"""
from __future__ import annotations

import hashlib
import re

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
_SEPARATOR = "\x1f"  # unit separator — kollidiert nicht mit normalisiertem Text


def _normalize(value: str | None) -> str:
    """lowercase, Whitespace kollabieren, None → ''. Für Identifier (Familie,
    field_id, source_id) — Ziffern bleiben erhalten, sonst würden z. B.
    ``src-1``/``src-2`` oder ``…MANDATORY_3_1``/``_3_2`` kollidieren."""
    if value is None:
        return ""
    return " ".join(value.lower().split())


def _normalize_claim(value: str | None) -> str:
    """Wie ``_normalize``, zusätzlich Zahlen zu ``#`` maskiert — derselbe
    Claim mit anderer Zahl ergibt denselben Fingerprint."""
    return _NUMBER_RE.sub("#", _normalize(value))


def compute_finding_fingerprint(
    rule_or_code_family: str,
    field_id: str | None,
    claim_core: str | None = None,
    source_id: str | None = None,
) -> str:
    """Stabiler sha256-Hexdigest über die normalisierten Bestandteile."""
    joined = _SEPARATOR.join(
        (
            _normalize(rule_or_code_family),
            _normalize(field_id),
            _normalize_claim(claim_core),
            _normalize(source_id),
        )
    )
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def finding_code_family(finding_code: str) -> str:
    """Meldungsfamilie eines ``finding_code`` (deterministisch, ohne IDs).

    ``draft_placeholder:INTRO.APP.ABSTRACT`` → ``draft_placeholder``;
    ``reliability:quantified:<claim>`` → ``reliability:quantified``;
    ``comment:<uuid>`` → ``comment``.
    """
    parts = finding_code.split(":")
    if parts[0] == "reliability" and len(parts) > 1:
        return ":".join(parts[:2])
    return parts[0]


# R2.3 — GENAU diese sechs Klassen, keine weiteren.
SEVERITY_CLASSES = (
    "export_blocker",
    "eligibility_blocker",
    "budget_blocker",
    "reviewer_risk",
    "evidence_risk",
    "style_risk",
)

# Deterministische Familien → Klasse. Platzhalter/Zeichenlimit/leeres
# Pflichtfeld blockieren den Export; Evidenz-/Beurteilungsgrundlagen-Findings
# sind evidence_risk; Rest fällt auf style_risk zurück.
_FAMILY_CLASS: dict[str, str] = {
    "draft_placeholder": "export_blocker",
    "draft_over_limit": "export_blocker",
    "draft_empty": "export_blocker",
    "stale_evidence_link": "evidence_risk",
    "unverified_linked_evidence": "evidence_risk",
    "missing_evidence_link": "evidence_risk",
    "requirement_needs_input": "evidence_risk",
    "stale_assessment": "evidence_risk",
    # A3-Agent-Findings (a3:<digest>) sind Evidenz-Konsistenz-Hinweise.
    "a3": "evidence_risk",
}

# Requirement-Kategorie (Registry) → Klasse für Blocker-OpenIssues.
_CATEGORY_CLASS: dict[str, str] = {
    "budget": "budget_blocker",
    "portal_quality_gate": "export_blocker",
}


def classify_severity_class(
    finding_code: str, requirement_category: str | None = None
) -> str:
    """Eine der sechs severity-Klassen für einen ``finding_code``.

    ``open_issue_blocker`` wird über die Registry-Kategorie der zugrunde
    liegenden Anforderung eingeordnet (budget → budget_blocker, sonst
    eligibility_blocker); alle ``reliability:*``-Familien sind
    evidence_risk; unbekannte Familien → style_risk (Rest-Klasse).
    """
    family = finding_code_family(finding_code)
    if family == "open_issue_blocker":
        if requirement_category in _CATEGORY_CLASS:
            return _CATEGORY_CLASS[requirement_category]
        return "eligibility_blocker"
    if family.startswith("reliability:"):
        return "evidence_risk"
    return _FAMILY_CLASS.get(family, "style_risk")


def compute_display_group_key(
    severity_class: str,
    rule_or_message_template: str,
    field_group: str | None = None,
) -> str:
    """Lesbarer Gruppenschlüssel ``severity_class|familie[|field_group]``.

    Nimmt bewusst KEINEN claim_core entgegen — gleichartige Meldungen mit
    unterschiedlichen Claims landen in derselben Gruppe.
    """
    parts = [_normalize(severity_class), _normalize(rule_or_message_template)]
    if field_group:
        parts.append(_normalize(field_group))
    return "|".join(parts)
