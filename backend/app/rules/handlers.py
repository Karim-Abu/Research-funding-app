"""Deterministic condition handlers — one per rule ``condition.type``.

Each handler is a pure function ``(rule, inputs) -> (mapping_key, observed,
reason)``. The returned ``mapping_key`` is a key of the rule's registry
``result_mapping`` (the condition branch that holds); the engine looks up the
outcome label there. Handlers never decide pass/fail labels themselves, never
use ``eval``/``exec``, and return a dedicated "missing"/unknown branch when a
required input is absent (never a guessed pass/fail). All thresholds/ranges are
read from the registry ``condition`` — nothing is hardcoded.
"""
from __future__ import annotations

from typing import Any

from app.registry.loader import RuleDef
from app.rules.inputs import PartnerInput, RuleInputs
from app.rules.messages import rule_message

Handled = tuple[str, dict[str, Any], str]

# Values that mean "not yet determined" rather than a concrete answer.
_UNKNOWN_PARTNER_VALUES = {None, "needs_verification"}


def _where_field(partner: PartnerInput, key: str) -> Any:
    # The rule registry uses ``research_eligibility_status``; the Partner schema
    # field is ``research_partner_eligibility_status``.
    if key == "research_eligibility_status":
        return partner.research_partner_eligibility_status
    return getattr(partner, key, None)


def _match_partner(partner: PartnerInput, where: dict[str, Any]) -> str:
    """Return 'match' | 'unknown' | 'no' for a partner against a where-clause."""
    contradicted = False
    unknown = False
    for key, expected in where.items():
        actual = _where_field(partner, key)
        if actual in _UNKNOWN_PARTNER_VALUES:
            unknown = True
            continue
        if actual != expected:
            contradicted = True
    if contradicted:
        return "no"
    return "unknown" if unknown else "match"


def h_exists(rule: RuleDef, inputs: RuleInputs) -> Handled:
    entity = rule.condition.get("entity")
    where = rule.condition.get("where", {}) or {}
    if entity == "implementation_partner":
        candidates = inputs.implementation_partners
    elif entity == "research_partner":
        candidates = inputs.research_partners
    else:
        candidates = inputs.partners
    matched = unknown = 0
    for partner in candidates:
        state = _match_partner(partner, where)
        if state == "match":
            matched += 1
        elif state == "unknown":
            unknown += 1
    observed = {
        "entity": entity,
        "candidates": len(candidates),
        "matched": matched,
        "unknown": unknown,
    }
    # R2.6 — entity-spezifische Katalogtexte (message-catalog.md); die
    # Zweig-Entscheidung (true/missing/false) bleibt unverändert.
    if matched:
        return "true", observed, rule_message(
            rule.rule_id, "true", f"{matched} passende(r) Partner vorhanden."
        )
    if unknown:
        return "missing", observed, rule_message(
            rule.rule_id, "missing",
            "Partnerangaben unvollständig — Prüfung nicht abschliessend.",
        )
    return "false", observed, rule_message(
        rule.rule_id, "false", "Kein passender Partner erfasst."
    )


def h_human_reviewed_questionnaire(rule: RuleDef, inputs: RuleInputs) -> Handled:
    statuses = [p.personnel_independence_status for p in inputs.partners]
    observed = {"personnel_independence_statuses": statuses}
    if not statuses:
        return "potential_conflict", observed, "Keine Partnerangaben zur personellen Unabhängigkeit."
    if all(s == "confirmed" for s in statuses):
        return "clear", observed, "Alle Partner bestätigen die personelle Unabhängigkeit."
    # exception / needs_input / null → human review required (never auto-fail).
    return (
        "potential_conflict",
        observed,
        "Personelle Unabhängigkeit nicht abschliessend bestätigt — menschliche Prüfung nötig.",
    )


def h_max_exclusive_percent(rule: RuleDef, inputs: RuleInputs) -> Handled:
    threshold = rule.condition.get("threshold")
    fields = rule.condition.get("fields", []) or []
    statuses = [p.financial_independence_status for p in inputs.partners]
    values: list[float] = []
    for partner in inputs.partners:
        for fname in fields:
            value = getattr(partner, fname, None)
            if value is not None:
                values.append(value)
    observed = {
        "threshold": threshold,
        "financial_independence_statuses": statuses,
        "percent_values": values,
    }
    # R2.6 — Katalogtexte je Zweig; Zweig-Semantik unverändert.
    if values:
        if any(v >= threshold for v in values):
            return "at_or_above_threshold", observed, rule_message(
                rule.rule_id, "at_or_above_threshold",
                f"Beteiligung ≥ {threshold} %.",
            )
        return "below_threshold_and_confirmed", observed, rule_message(
            rule.rule_id, "below_threshold_and_confirmed",
            f"Alle Beteiligungen < {threshold} %.",
        )
    if not statuses:
        return "missing", observed, rule_message(
            rule.rule_id, "missing",
            "Keine Angaben zur finanziellen Unabhängigkeit.",
        )
    if all(s == "confirmed" for s in statuses):
        return "below_threshold_and_confirmed", observed, rule_message(
            rule.rule_id, "below_threshold_and_confirmed",
            "Finanzielle Unabhängigkeit bestätigt.",
        )
    return "missing", observed, rule_message(
        rule.rule_id, "missing",
        "Finanzielle Unabhängigkeit nicht bestätigt — Angaben nötig.",
    )


def h_range_percent(rule: RuleDef, inputs: RuleInputs) -> Handled:
    numerator = inputs.implementation_numerator
    denominator = inputs.direct_total_project_costs_excluding_overhead
    minimum = rule.condition.get("min")
    maximum = rule.condition.get("max")
    observed = {
        "numerator": numerator,
        "denominator": denominator,
        "min": minimum,
        "max": maximum,
    }
    if numerator is None or denominator in (None, 0):
        return "missing", observed, "Budgetangaben für die Anteilsberechnung fehlen."
    percent = numerator / denominator * 100
    observed["percent"] = round(percent, 2)
    if minimum <= percent <= maximum:
        return "in_range", observed, f"Umsetzungsanteil {percent:.0f}% liegt in {minimum}–{maximum}%."
    key = (
        "out_of_range_with_claimed_exception"
        if inputs.budget_exception_basis
        else "out_of_range_without_exception"
    )
    return key, observed, f"Umsetzungsanteil {percent:.0f}% ausserhalb {minimum}–{maximum}%."


def h_min_percent(rule: RuleDef, inputs: RuleInputs) -> Handled:
    numerator = inputs.cash_contribution
    denominator = inputs.direct_total_project_costs_excluding_overhead
    minimum = rule.condition.get("min")
    observed = {"numerator": numerator, "denominator": denominator, "min": minimum}
    if numerator is None or denominator in (None, 0):
        return "missing", observed, "Budgetangaben für den Barbeitrag fehlen."
    percent = numerator / denominator * 100
    observed["percent"] = round(percent, 2)
    if percent >= minimum:
        return "at_or_above_min", observed, f"Barbeitrag {percent:.0f}% ≥ {minimum}%."
    key = (
        "below_with_claimed_exception"
        if inputs.budget_exception_basis
        else "below_without_exception"
    )
    return key, observed, f"Barbeitrag {percent:.0f}% < {minimum}%."


def h_no_upper_threshold(rule: RuleDef, inputs: RuleInputs) -> Handled:
    mapping = rule.result_mapping
    if "any_positive_value" in mapping:
        value = inputs.duration_months
        ok = value is not None and value > 0
        positive_key = "any_positive_value"
    else:  # any_nonnegative_value (financial cap)
        value = inputs.total_requested_funding
        ok = value is not None and value >= 0
        positive_key = "any_nonnegative_value"
    observed = {"value": value}
    if ok:
        return positive_key, observed, "Keine formale Obergrenze; Angabe vorhanden."
    return "missing", observed, "Angabe fehlt — keine Bewertung möglich."


def h_advisory_range(rule: RuleDef, inputs: RuleInputs) -> Handled:
    value = inputs.duration_months
    minimum = rule.condition.get("min")
    maximum = rule.condition.get("max")
    observed = {"value": value, "min": minimum, "max": maximum}
    if value is None:
        return "missing", observed, "Projektdauer nicht angegeben."
    if minimum <= value <= maximum:
        return "in_range", observed, f"Dauer {value} Monate im üblichen Bereich {minimum}–{maximum}."
    return "outside_range", observed, f"Dauer {value} Monate ausserhalb {minimum}–{maximum} (Hinweis)."


def h_max_value(rule: RuleDef, inputs: RuleInputs) -> Handled:
    value = inputs.duration_months
    maximum = rule.condition.get("max")
    observed = {"value": value, "max": maximum}
    if value is None:
        return "missing", observed, "Projektdauer nicht angegeben."
    if value <= maximum:
        return "at_or_below_max", observed, f"Dauer {value} ≤ {maximum} Monate."
    key = (
        "above_with_claimed_exception"
        if inputs.duration_exception
        else "above_without_exception"
    )
    return key, observed, f"Dauer {value} > {maximum} Monate."


def h_aggregate_submission_gate(rule: RuleDef, inputs: RuleInputs) -> Handled:
    observed = {"portal_fields_complete": inputs.portal_fields_complete}
    # Portal-field drafts are out of M4 scope, so submission completeness cannot
    # be determined deterministically yet.
    return (
        "unclear",
        observed,
        "Vollständigkeit des Gesuchs noch nicht prüfbar (Portalfelder ausstehend).",
    )


def h_conditional_human_gate(rule: RuleDef, inputs: RuleInputs) -> Handled:
    answer = inputs.sanction_answer
    observed = {
        "sanction_answer": answer,
        "human_decision_present": inputs.human_decision_present,
    }
    if answer is None:
        return "missing", observed, "Angabe zur wissenschaftlichen Integrität fehlt."
    if answer is False:
        return (
            "no",
            observed,
            "Keine Sanktion wegen Verletzung der wissenschaftlichen Integrität "
            "angegeben — keine zusätzliche menschliche Prüfung nötig.",
        )
    if inputs.human_decision_present:
        return "yes_reviewed", observed, "Sanktion angegeben — menschliche Entscheidung erforderlich."
    return "yes_unreviewed", observed, "Sanktion angegeben, noch nicht geprüft."


HANDLERS = {
    "exists": h_exists,
    "human_reviewed_questionnaire": h_human_reviewed_questionnaire,
    "max_exclusive_percent": h_max_exclusive_percent,
    "range_percent": h_range_percent,
    "min_percent": h_min_percent,
    "no_upper_threshold": h_no_upper_threshold,
    "advisory_range": h_advisory_range,
    "max_value": h_max_value,
    "aggregate_submission_gate": h_aggregate_submission_gate,
    "conditional_human_gate": h_conditional_human_gate,
}
