"""Typed, deterministic eligibility checks for application evidence."""
from __future__ import annotations

import re

from app.registry import get_registry

_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")
_PERCENT_RE = re.compile(r"(?:%|prozent)", re.IGNORECASE)
_DURATION_RE = re.compile(
    r"(?:\b\d+\s*(?:monat|monate|monaten|jahr|jahre|jahren)\b|"
    r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b|"
    r"keine\s+(?:formale\s+)?(?:maximale\s+)?projektdauer)",
    re.IGNORECASE,
)
_ORG_RE = re.compile(
    r"\b(?:ag|gmbh|sa|sàrl|ltd|universität|university|hochschule|"
    r"fachhochschule|institut|institution|eth|epfl)\b",
    re.IGNORECASE,
)

REJECTION_TEXT_DE = {
    "evidence_numeric_value_missing": "Die Fundstelle enthält keinen prüfbaren Zahlenwert.",
    "evidence_unit_missing": "Zum Zahlenwert fehlt die erforderliche Einheit.",
    "evidence_operator_missing": "Der erforderliche Vergleichsoperator ist nicht belegt.",
    "evidence_denominator_missing": "Die Bezugsgrösse des Zahlenwerts ist nicht eindeutig.",
    "evidence_duration_missing": "Die Fundstelle enthält weder ein belastbares Datum noch eine Dauer.",
    "evidence_organization_not_concrete": "Die Fundstelle nennt keine konkrete Organisation.",
    "evidence_research_role_mismatch": "Die genannte Organisation ist nicht eindeutig als Forschungspartner belegt.",
    "evidence_implementation_role_mismatch": "Die genannte Organisation ist nicht eindeutig als Umsetzungspartner belegt.",
    "generated_or_review_content": "Erzeugte Texte und Reviews sind keine Antragsbelege.",
    "application_source_not_primary": "Die Fundstelle stammt nicht aus dem primären Antrag.",
    "primary_application_version_mismatch": "Die Fundstelle stammt nicht aus der eingefrorenen Antragsversion.",
}


def rejection_text_de(reason_code: str) -> str:
    return REJECTION_TEXT_DE.get(
        reason_code,
        "Diese Fundstelle ist für die fachliche Anforderung nicht geeignet.",
    )


def validate_requirement_quote(
    requirement_id: str, quote: str
) -> str | None:
    registry = get_registry()
    requirement = registry.requirements.get(requirement_id)
    if requirement is None or not requirement.linked_rule_ids:
        return None
    rule = registry.rules.get(requirement.linked_rule_ids[0])
    if rule is None:
        return None
    text = quote.casefold()
    condition_type = str(rule.condition.get("type", ""))

    if rule.rule_id.startswith("INNO.DURATION."):
        if not _DURATION_RE.search(quote):
            return "evidence_duration_missing"
        return None

    if condition_type in {"range_percent", "min_percent", "max_exclusive_percent"}:
        if not _NUMBER_RE.search(quote):
            return "evidence_numeric_value_missing"
        if not _PERCENT_RE.search(quote):
            return "evidence_unit_missing"
        if condition_type == "range_percent" and not re.search(
            r"(?:\bzwischen\b|\bbis\b|[-–])", text
        ):
            return "evidence_operator_missing"
        if condition_type == "min_percent" and not re.search(
            r"(?:mindestens|minimum|>=|≥)", text
        ):
            return "evidence_operator_missing"
        if condition_type == "max_exclusive_percent" and not re.search(
            r"(?:weniger als|unter|<)", text
        ):
            return "evidence_operator_missing"
        if not re.search(
            r"(?:kosten|gesamt|anteil|beteiligung|unterstützung|beitrag)", text
        ):
            return "evidence_denominator_missing"
        return None

    if condition_type == "exists" and "PARTNER" in rule.rule_id:
        if not _ORG_RE.search(quote):
            return "evidence_organization_not_concrete"
        if ".RESEARCH." in rule.rule_id and not re.search(
            r"(?:forschungspartner|research partner|forschungsinstitution)", text
        ):
            return "evidence_research_role_mismatch"
        if ".IMPLEMENTATION." in rule.rule_id and not re.search(
            r"(?:umsetzungspartner|implementation partner)", text
        ):
            return "evidence_implementation_role_mismatch"
    return None
