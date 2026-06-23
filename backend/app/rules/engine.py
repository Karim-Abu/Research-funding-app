"""Rule engine: applies_when gating + deterministic dispatch + canonical status.

The engine resolves whether a rule applies (``applies_when``), dispatches to the
matching condition handler, looks up the registry ``result_mapping`` for the
returned branch, and derives the canonical RuleResult status
(``passed | failed | needs_input | not_applicable``; Domain Model). The richer
``result_mapping`` outcome label (e.g. ``warning``, ``human_decision_required``)
is preserved separately for requirement aggregation and traceability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.registry.loader import RuleDef
from app.rules.handlers import HANDLERS
from app.rules.inputs import RuleInputs

# Canonical RuleResult status (Domain_Model_v4): passed | failed | needs_input |
# not_applicable. Richer outcome labels collapse into these four.
_OUTCOME_TO_STATUS = {
    "passed": "passed",
    "failed": "failed",
    "needs_input": "needs_input",
    # advisory: the rule did not formally fail (severity warning).
    "warning": "passed",
    # a human decision is still required → not yet passed.
    "human_decision_required": "needs_input",
}


class RuleEngineError(RuntimeError):
    """Raised when a rule references an unknown condition type (registry drift)."""


@dataclass(frozen=True)
class RuleOutcome:
    rule_id: str
    requirement_id: str | None
    rule_version: str
    applicable: bool
    mapping_key: str
    outcome_label: str  # result_mapping value, or "needs_input" fallback
    status: str  # canonical: passed | failed | needs_input | not_applicable
    severity: str
    execution_mode: str
    observed: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


def _applies_when(applies_when: dict[str, Any] | None, inputs: RuleInputs) -> bool:
    if not applies_when:
        return True
    profile = applies_when.get("instrument_profile")
    if profile is not None and profile != inputs.profile_id:
        return False
    count_cond = applies_when.get("implementation_partner_count")
    if count_cond is not None:
        count = inputs.implementation_partner_count
        if isinstance(count_cond, dict):
            if "gte" in count_cond and not count >= count_cond["gte"]:
                return False
            if "lte" in count_cond and not count <= count_cond["lte"]:
                return False
            if "eq" in count_cond and count != count_cond["eq"]:
                return False
        elif count != count_cond:
            return False
    return True


def evaluate_rule(
    rule: RuleDef, inputs: RuleInputs, *, rule_version: str
) -> RuleOutcome:
    if not _applies_when(rule.applies_when, inputs):
        return RuleOutcome(
            rule_id=rule.rule_id,
            requirement_id=rule.requirement_id,
            rule_version=rule_version,
            applicable=False,
            mapping_key="not_applicable",
            outcome_label="not_applicable",
            status="not_applicable",
            severity=rule.severity,
            execution_mode=rule.execution_mode,
            observed={"applies_when": rule.applies_when},
            reason="Regel im aktuellen Projektprofil nicht anwendbar.",
        )

    handler = HANDLERS.get(rule.condition.get("type"))
    if handler is None:
        raise RuleEngineError(
            f"No handler for condition type {rule.condition.get('type')!r} "
            f"(rule {rule.rule_id})."
        )
    mapping_key, observed, reason = handler(rule, inputs)

    outcome_label = rule.result_mapping.get(mapping_key)
    if outcome_label is None:
        # A 'missing'/unknown branch with no explicit mapping → needs_input
        # (never a guessed pass/fail).
        outcome_label = "needs_input"
        status = "needs_input"
    else:
        status = _OUTCOME_TO_STATUS.get(outcome_label, "needs_input")

    return RuleOutcome(
        rule_id=rule.rule_id,
        requirement_id=rule.requirement_id,
        rule_version=rule_version,
        applicable=True,
        mapping_key=mapping_key,
        outcome_label=outcome_label,
        status=status,
        severity=rule.severity,
        execution_mode=rule.execution_mode,
        observed=observed,
        reason=reason,
    )
