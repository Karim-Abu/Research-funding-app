"""Slice 1: structured budget inputs feed the deterministic budget rules.

Covers the snapshot→RuleInputs mapping, the 40-60% share and 5%-cash handlers
with real inputs, the PATCH roundtrip and budget-driven snapshot staleness.
Handlers and registry stay untouched — synthetic data only.
"""
from __future__ import annotations

import uuid

from app.db.models import RunProjectSnapshot
from app.db.session import SessionLocal
from app.registry import get_registry
from app.rules.engine import evaluate_rule
from app.rules.handlers import h_min_percent, h_range_percent
from app.rules.inputs import inputs_from_snapshot
from app.runs import project_snapshot
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, create_project, login, unsafe_headers
from tests.review_helpers import setup_completed_run

reg = get_registry()
RV = reg.rule_registry_version
RANGE_RULE = reg.rules["INNO.BUDGET.IMPLEMENTATION_SHARE_40_60"]
CASH_RULE = reg.rules["INNO.BUDGET.CASH_MIN5"]

BUDGET_PATCH = {
    "direct_total_project_costs_excluding_overhead": 100000,
    "implementation_own_contribution": 45000,
    "cash_contribution": 5000,
    "total_requested_funding": 50000,
    "budget_exception_basis": "Start-up-Ausnahme",
    "duration_months": 24,
}


def _inputs(**project):
    return inputs_from_snapshot(
        profile_id=None, partner_dicts=[], project_dict=project or None
    )


# --- (1)+(4) snapshot → RuleInputs mapping ----------------------------------


def test_inputs_from_snapshot_maps_budget_fields():
    inputs = _inputs(
        direct_total_project_costs_excluding_overhead=100000.0,
        implementation_own_contribution=45000.0,
        cash_contribution=5000.0,
        total_requested_funding=50000.0,
        budget_exception_basis="Ausnahme X",
        duration_months=24,
    )
    assert inputs.direct_total_project_costs_excluding_overhead == 100000.0
    assert inputs.implementation_own_contribution == 45000.0
    assert inputs.cash_contribution == 5000.0
    assert inputs.total_requested_funding == 50000.0
    assert inputs.budget_exception_basis == "Ausnahme X"
    assert inputs.duration_months == 24
    assert inputs.implementation_numerator == 50000.0


def test_inputs_without_project_dict_stay_none():
    inputs = inputs_from_snapshot(profile_id=None, partner_dicts=[])
    assert inputs.direct_total_project_costs_excluding_overhead is None
    assert inputs.cash_contribution is None
    assert inputs.budget_exception_basis is None
    assert inputs.duration_months is None
    assert inputs.implementation_numerator is None


def test_whitespace_exception_basis_becomes_none():
    assert _inputs(budget_exception_basis="   ").budget_exception_basis is None


def test_partial_own_or_cash_yields_no_numerator():
    # A partial sum must not turn incomplete data into a verdict → missing.
    only_own = _inputs(
        direct_total_project_costs_excluding_overhead=100000.0,
        implementation_own_contribution=45000.0,
    )
    assert only_own.implementation_numerator is None
    key, _, _ = h_range_percent(RANGE_RULE, only_own)
    assert key == "missing"


def test_zero_denominator_is_missing_not_crash():
    inputs = _inputs(
        direct_total_project_costs_excluding_overhead=0.0,
        implementation_own_contribution=40000.0,
        cash_contribution=10000.0,
    )
    key, _, _ = h_range_percent(RANGE_RULE, inputs)
    assert key == "missing"
    key, _, _ = h_min_percent(CASH_RULE, inputs)
    assert key == "missing"


# --- (2) 40-60% share --------------------------------------------------------


def _share_inputs(own: float, cash: float, basis: str | None = None):
    return _inputs(
        direct_total_project_costs_excluding_overhead=100000.0,
        implementation_own_contribution=own,
        cash_contribution=cash,
        budget_exception_basis=basis,
    )


def test_range_percent_35_is_out_of_range_without_exception():
    key, observed, _ = h_range_percent(RANGE_RULE, _share_inputs(30000, 5000))
    assert key == "out_of_range_without_exception"
    assert observed["percent"] == 35.0
    out = evaluate_rule(RANGE_RULE, _share_inputs(30000, 5000), rule_version=RV)
    assert out.outcome_label == "failed"


def test_range_percent_50_is_in_range():
    key, observed, _ = h_range_percent(RANGE_RULE, _share_inputs(45000, 5000))
    assert key == "in_range"
    assert observed["percent"] == 50.0
    out = evaluate_rule(RANGE_RULE, _share_inputs(45000, 5000), rule_version=RV)
    assert out.outcome_label == "passed"


def test_range_percent_65_with_exception_is_claimed_exception():
    key, _, _ = h_range_percent(
        RANGE_RULE, _share_inputs(60000, 5000, basis="Gesetzliche Ausnahme")
    )
    assert key == "out_of_range_with_claimed_exception"
    out = evaluate_rule(
        RANGE_RULE,
        _share_inputs(60000, 5000, basis="Gesetzliche Ausnahme"),
        rule_version=RV,
    )
    assert out.outcome_label == "needs_input"  # human review, never auto-pass


# --- (3) 5% cash -------------------------------------------------------------


def _cash_inputs(cash: float):
    return _inputs(
        direct_total_project_costs_excluding_overhead=100000.0,
        cash_contribution=cash,
    )


def test_min_percent_3_is_below_without_exception():
    key, _, _ = h_min_percent(CASH_RULE, _cash_inputs(3000))
    assert key == "below_without_exception"


def test_min_percent_5_and_6_are_at_or_above_min():
    for cash in (5000, 6000):
        key, _, _ = h_min_percent(CASH_RULE, _cash_inputs(cash))
        assert key == "at_or_above_min"


# --- (5) PATCH roundtrip -----------------------------------------------------


def _mut(csrf):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = uuid.uuid4().hex
    return headers


def test_budget_patch_roundtrip(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)

    res = client.patch(
        f"/api/v1/projects/{project_id}", json=BUDGET_PATCH, headers=unsafe_headers(csrf)
    )
    assert res.status_code == 200, res.text
    body = res.json()
    for field, value in BUDGET_PATCH.items():
        assert body[field] == value

    fetched = client.get(f"/api/v1/projects/{project_id}").json()
    for field, value in BUDGET_PATCH.items():
        assert fetched[field] == value


def test_budget_patch_rejects_invalid_duration(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    res = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"duration_months": 0},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 422


# --- (6) snapshot staleness on budget edit -----------------------------------


def test_budget_edit_makes_run_snapshot_stale(client):
    csrf, project_id, run_id = setup_completed_run(client, title="Budget Staleness")

    db = SessionLocal()
    try:
        snapshot = db.get(RunProjectSnapshot, run_id)
        assert snapshot is not None
        assert project_snapshot.is_stale(db, snapshot) is False
    finally:
        db.close()

    res = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"cash_contribution": 12000},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200, res.text

    db = SessionLocal()
    try:
        snapshot = db.get(RunProjectSnapshot, run_id)
        assert project_snapshot.is_stale(db, snapshot) is True
    finally:
        db.close()
