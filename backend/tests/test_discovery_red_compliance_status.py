"""Regressionstests (promoted aus DISCOVERY-RED #4, RUN 2A Slice 1).

Mandat A2 / Owner-Entscheid: «Eine offene menschliche Prüfung darf ein
deterministisch erfülltes Gate nicht auf ‹teilweise erfüllt› herabstufen» —
52 % im Band 40–60 % und exakt 5 % Barbeitrag sind ``fulfilled``; die offene
Bestätigung ist eine separate Dimension (``human_confirmation_pending`` →
``review_status``).

Historie: bis RUN 2A mappte ``app/rules/aggregation.py`` einen Hybrid-Pass auf
``partial`` (gepinnt im früheren ``test_aggregate_hybrid_pass_is_partial``).
Diese Tests waren ``xfail(strict=True)`` und wurden mit dem Fix promoted.
"""
from __future__ import annotations


def _outcome_and_req(requirement_id: str, project_dict: dict):
    from app.registry import get_registry
    from app.rules.engine import evaluate_rule
    from app.rules.inputs import inputs_from_snapshot

    reg = get_registry()
    req = reg.requirements[requirement_id]
    inputs = inputs_from_snapshot(
        profile_id=None, partner_dicts=[], project_dict=project_dict
    )
    out = evaluate_rule(
        reg.rule_for(req), inputs, rule_version=reg.rule_registry_version
    )
    return req, out


def test_hybrid_pass_share_52_percent_stays_fulfilled():
    from app.rules.aggregation import aggregate, aggregate_status

    req, out = _outcome_and_req(
        "REQ.INNO.BUDGET.IMPLEMENTATION_SHARE_40_60",
        {
            "direct_total_project_costs_excluding_overhead": 100000.0,
            "implementation_own_contribution": 47000.0,
            "cash_contribution": 5000.0,
        },
    )
    assert out.outcome_label == "passed"  # 52 % liegt im Band — Regel besteht.
    assert aggregate_status(req, out) == "fulfilled"
    result = aggregate(req, out)
    assert result.status == "fulfilled"
    # Die menschliche Bestätigung bleibt als separates Issue sichtbar.
    assert result.issue is not None
    assert result.issue.issue_type == "human_confirmation_pending"
    assert result.issue.severity == "info"


def test_hybrid_pass_cash_exactly_5_percent_stays_fulfilled():
    from app.rules.aggregation import aggregate, aggregate_status

    req, out = _outcome_and_req(
        "REQ.INNO.BUDGET.CASH_MIN5",
        {
            "direct_total_project_costs_excluding_overhead": 100000.0,
            "implementation_own_contribution": 45000.0,
            "cash_contribution": 5000.0,
        },
    )
    assert out.outcome_label == "passed"  # exakt 5 % ist inklusiv — Regel besteht.
    assert aggregate_status(req, out) == "fulfilled"
    result = aggregate(req, out)
    assert result.status == "fulfilled"
    assert result.issue is not None
    assert result.issue.issue_type == "human_confirmation_pending"
