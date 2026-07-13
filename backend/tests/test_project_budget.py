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


# --- (5b) Budget-Vorprüfung (read-only, run-unabhängig) -----------------------


def _patch_budget(client, csrf, project_id, **overrides):
    payload = {**BUDGET_PATCH, "budget_exception_basis": None, **overrides}
    res = client.patch(
        f"/api/v1/projects/{project_id}", json=payload,
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200, res.text


def _precheck(client, project_id):
    res = client.get(f"/api/v1/projects/{project_id}/budget/precheck")
    assert res.status_code == 200, res.text
    return res.json()


def _check_by_rule(body, rule_id):
    return next(c for c in body["checks"] if c["rule_id"] == rule_id)


class TestBudgetPrecheck:
    def test_fulfilled_figures_and_registry_condition(self, client):
        csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
        project_id = create_project(client, csrf)
        _patch_budget(client, csrf, project_id)

        body = _precheck(client, project_id)
        figures = body["figures"]
        # Identität Own + Cash = Umsetzungspartnerbeitrag, Anteile aus dem
        # Rule-Kern (observed.percent-Rechnung).
        assert figures["implementation_contribution_chf"] == 50000
        assert figures["implementation_share_percent"] == 50.0
        assert figures["cash_share_percent"] == 5.0
        assert figures["funding_share_percent"] == 50.0
        assert figures["exception_claimed"] is False

        share = _check_by_rule(body, "INNO.BUDGET.IMPLEMENTATION_SHARE_40_60")
        cash = _check_by_rule(body, "INNO.BUDGET.CASH_MIN5")
        assert share["status"] == "fulfilled" and cash["status"] == "fulfilled"
        # Schwellen kommen 1:1 aus der Registry — keine Zweit-Hardcodierung.
        assert share["condition"] == RANGE_RULE.condition
        assert cash["condition"] == CASH_RULE.condition
        assert share["rule_version"] == RV
        assert share["title"] and "REQ." not in share["title"]

    def test_exact_thresholds_from_contract(self, client):
        csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
        project_id = create_project(client, csrf)
        # Grenzen exakt an den Registry-Schwellen (40/60 inkl., 5 inkl.).
        cases = [
            ({"implementation_own_contribution": 34990, "cash_contribution": 5000}, "blocker"),   # 39.99 %
            ({"implementation_own_contribution": 35000, "cash_contribution": 5000}, "fulfilled"), # 40 %
            ({"implementation_own_contribution": 55000, "cash_contribution": 5000}, "fulfilled"), # 60 %
            ({"implementation_own_contribution": 55010, "cash_contribution": 5000}, "blocker"),   # 60.01 %
        ]
        for overrides, expected in cases:
            _patch_budget(client, csrf, project_id, **overrides)
            share = _check_by_rule(
                _precheck(client, project_id),
                "INNO.BUDGET.IMPLEMENTATION_SHARE_40_60",
            )
            assert share["status"] == expected, (overrides, share)

        for cash_value, expected in ((4990, "blocker"), (5000, "fulfilled")):
            _patch_budget(
                client, csrf, project_id,
                implementation_own_contribution=45000, cash_contribution=cash_value,
            )
            cash = _check_by_rule(
                _precheck(client, project_id), "INNO.BUDGET.CASH_MIN5"
            )
            assert cash["status"] == expected, (cash_value, cash)

    def test_exception_yields_review_not_acceptance(self, client):
        csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
        project_id = create_project(client, csrf)
        _patch_budget(
            client, csrf, project_id,
            implementation_own_contribution=60000, cash_contribution=5000,
            budget_exception_basis="Start-up-Ausnahme gemäss Vereinbarung",
        )
        body = _precheck(client, project_id)
        share = _check_by_rule(body, "INNO.BUDGET.IMPLEMENTATION_SHARE_40_60")
        # Ausnahme geltend gemacht → menschliche Prüfung, nie auto-akzeptiert.
        assert share["status"] == "review"
        assert body["figures"]["exception_claimed"] is True

    def test_missing_and_zero_denominator_yield_missing(self, client):
        csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
        project_id = create_project(client, csrf)

        # Ohne jede Budget-Angabe: alles «Angabe fehlt», keine Falschurteile.
        body = _precheck(client, project_id)
        assert all(c["status"] == "missing" for c in body["checks"])
        figures = body["figures"]
        assert figures["implementation_share_percent"] is None
        assert figures["cash_share_percent"] is None
        assert figures["funding_share_percent"] is None

        # 0-Nenner ebenso.
        _patch_budget(
            client, csrf, project_id,
            direct_total_project_costs_excluding_overhead=0,
        )
        body = _precheck(client, project_id)
        assert all(c["status"] == "missing" for c in body["checks"])
        assert body["figures"]["implementation_share_percent"] is None

    def test_parity_with_run_rule_results(self, client):
        """Derselbe Datensatz → Precheck und Run-Auswertung liefern dieselben
        Regel-Ausgänge (kein zweiter Rechenweg)."""
        csrf, project_id, run_id = setup_completed_run(client, title="Precheck Parity")
        _patch_budget(client, csrf, project_id)
        body = _precheck(client, project_id)

        db = SessionLocal()
        try:
            snapshot = db.get(RunProjectSnapshot, run_id)
            project_dict = dict(snapshot.project_json)
            # Gleiche Eingaben wie im Precheck (der Lauf oben fror leere
            # Budgetwerte ein — für die Parität denselben Stand herstellen).
            project_dict.update(
                {k: v for k, v in BUDGET_PATCH.items() if k != "budget_exception_basis"}
            )
            project_dict["budget_exception_basis"] = None
            inputs = inputs_from_snapshot(
                profile_id=project_dict.get("funding_instrument_profile_id"),
                partner_dicts=list(snapshot.partners_json),
                project_dict=project_dict,
            )
        finally:
            db.close()
        for rule in (RANGE_RULE, CASH_RULE):
            outcome = evaluate_rule(rule, inputs, rule_version=RV)
            check = _check_by_rule(body, rule.rule_id)
            assert check["observed"] == outcome.observed
            assert check["reason"] == outcome.reason

    def test_precheck_persists_nothing(self, client):
        from sqlalchemy import func, select

        from app.db.models import AuditEvent, OpenIssue, RuleResult

        def _counts():
            db = SessionLocal()
            try:
                return (
                    db.scalar(select(func.count()).select_from(RuleResult)),
                    db.scalar(select(func.count()).select_from(OpenIssue)),
                    db.scalar(select(func.count()).select_from(AuditEvent)),
                )
            finally:
                db.close()

        csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
        project_id = create_project(client, csrf)
        _patch_budget(client, csrf, project_id)

        before = _counts()
        _precheck(client, project_id)
        # Reine Leseableitung: kein RuleResult, kein OpenIssue, kein Audit.
        assert _counts() == before

    def test_precheck_workspace_isolation(self, client):
        from tests.conftest import OUTSIDER_EMAIL, OUTSIDER_PASSWORD

        csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
        project_id = create_project(client, csrf)
        login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
        res = client.get(f"/api/v1/projects/{project_id}/budget/precheck")
        assert res.status_code == 404


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
