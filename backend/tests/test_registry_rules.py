"""Registry loading/validation + deterministic rule engine + aggregation."""
from __future__ import annotations

import pathlib

import pytest

from app.registry import get_registry, load_registry
from app.registry.loader import RegistryError
from app.rules.aggregation import aggregate, aggregate_status
from app.rules.engine import evaluate_rule
from app.rules.inputs import PartnerInput, RuleInputs

reg = get_registry()
RV = reg.rule_registry_version


def _impl(**kw) -> PartnerInput:
    return PartnerInput(partner_type="implementation_partner", **kw)


def _research(**kw) -> PartnerInput:
    return PartnerInput(partner_type="research_partner", **kw)


def _rule(rule_id: str):
    return reg.rules[rule_id]


def _req(requirement_id: str):
    return reg.requirements[requirement_id]


# --- registry structure + fail-closed -------------------------------------


def test_registry_loads_twelve_core_rules_and_requirements():
    assert len(reg.rules) == 12
    assert len(reg.evaluable_requirement_ids) == 12
    assert reg.requirement_registry_version == "1.0.0"
    assert reg.rule_registry_version == "1.1.0"
    # Every evaluable requirement links exactly one known core rule.
    for req in reg.evaluable_requirements():
        assert len(req.linked_rule_ids) == 1
        assert req.linked_rule_ids[0] in reg.rules
        assert req.assessment_basis in {"deterministic_rule", "semantic_assessment", "hybrid"}


def test_registry_fail_closed_on_missing_files(tmp_path, monkeypatch):
    monkeypatch.setattr("app.registry.loader._contracts_dir", lambda: tmp_path)
    with pytest.raises(RegistryError):
        load_registry()


def test_registry_fail_closed_on_corrupt_yaml(tmp_path, monkeypatch):
    (tmp_path / "requirements.yaml").write_text("not: [valid", encoding="utf-8")
    (tmp_path / "innosuisse_innovation_project_v1_1.yaml").write_text(
        "schema_version: 1.1.0\n", encoding="utf-8"
    )
    monkeypatch.setattr("app.registry.loader._contracts_dir", lambda: tmp_path)
    with pytest.raises(RegistryError):
        load_registry()


# --- engine driven by the registry test_cases (no hardcoded thresholds) ----


def _given_to_inputs(given: dict) -> RuleInputs:
    partners = []
    for p in given.get("implementation_partners", []):
        partners.append(_impl(swiss_value_creation=p.get("swiss_value_creation")))
    for p in given.get("research_partners", []):
        partners.append(
            _research(
                country=p.get("country"),
                research_partner_eligibility_status=p.get("research_eligibility_status"),
            )
        )
    kw = {}
    if "direct_total" in given:
        kw["direct_total_project_costs_excluding_overhead"] = given["direct_total"]
    if "implementation_total" in given:
        kw["implementation_total"] = given["implementation_total"]
    return RuleInputs(partners=partners, **kw)


_CASES = [
    (rule, tc)
    for rule in reg.rules.values()
    for tc in rule.test_cases
]


@pytest.mark.parametrize(
    "rule,tc", _CASES, ids=[f"{r.rule_id}:{t['id']}" for r, t in _CASES]
)
def test_registry_test_cases(rule, tc):
    out = evaluate_rule(rule, _given_to_inputs(tc["given"]), rule_version=RV)
    assert out.outcome_label == tc["expect"]


def test_all_test_cases_present():
    # Guard: the partner+budget rules ship explicit test cases we exercise.
    assert len(_CASES) >= 9


# --- deterministic engine semantics ---------------------------------------


def test_missing_input_is_needs_input_not_guessed():
    rule = _rule("INNO.PARTNER.IMPLEMENTATION.MIN1_CH")
    out = evaluate_rule(rule, RuleInputs(partners=[_impl(swiss_value_creation=None)]), rule_version=RV)
    assert out.status == "needs_input"
    assert out.outcome_label == "needs_input"


def test_max18_not_applicable_with_implementation_partner():
    rule = _rule("INNO.DURATION.MAX18_WITHOUT_IMPLEMENTATION_PARTNER")
    out = evaluate_rule(rule, RuleInputs(partners=[_impl(swiss_value_creation=True)]), rule_version=RV)
    assert out.applicable is False
    assert out.status == "not_applicable"


def test_advisory_range_outside_is_warning():
    rule = _rule("INNO.DURATION.TYPICAL_6_36")
    inputs = RuleInputs(partners=[_impl(swiss_value_creation=True)], duration_months=48)
    out = evaluate_rule(rule, inputs, rule_version=RV)
    assert out.outcome_label == "warning"
    assert out.status == "passed"  # advisory: not a formal failure


# --- aggregation (RuleOutcome -> RequirementAssessment) --------------------


def test_aggregate_hybrid_pass_is_fulfilled_with_confirmation_issue():
    """RUN 2A Slice 1 (Owner-Entscheid): ein maschinell bestandener Hybrid-Check
    ist ``fulfilled`` — die offene menschliche Bestätigung läuft als separates
    ``human_confirmation_pending``-Issue (review_status), nie als Herabstufung.
    (Ersetzt den früheren Pin ``hybrid pass ⇒ partial``.)"""
    req = _req("REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH")
    out = evaluate_rule(reg.rule_for(req), RuleInputs(partners=[_impl(swiss_value_creation=True)]), rule_version=RV)
    assert aggregate_status(req, out) == "fulfilled"
    result = aggregate(req, out)
    assert result.status == "fulfilled"
    assert result.issue is not None
    assert result.issue.issue_type == "human_confirmation_pending"
    assert result.issue.severity == "info"


def test_aggregate_blocker_fail_is_blocked():
    req = _req("REQ.INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE")
    out = evaluate_rule(reg.rule_for(req), RuleInputs(partners=[]), rule_version=RV)
    assert out.outcome_label == "failed"
    assert aggregate_status(req, out) == "blocked"


def test_aggregate_missing_is_needs_input():
    req = _req("REQ.INNO.BUDGET.CASH_MIN5")
    out = evaluate_rule(reg.rule_for(req), RuleInputs(), rule_version=RV)
    assert aggregate_status(req, out) == "needs_input"


def test_aggregate_not_applicable_omitted():
    req = _req("REQ.INNO.DURATION.MAX18_WITHOUT_IMPLEMENTATION_PARTNER")
    out = evaluate_rule(reg.rule_for(req), RuleInputs(partners=[_impl(swiss_value_creation=True)]), rule_version=RV)
    assert aggregate(req, out) is None


def test_aggregate_advisory_warning_is_partial_never_blocked():
    req = _req("REQ.INNO.DURATION.TYPICAL_6_36")
    inputs = RuleInputs(partners=[_impl(swiss_value_creation=True)], duration_months=48)
    out = evaluate_rule(reg.rule_for(req), inputs, rule_version=RV)
    assert aggregate_status(req, out) == "partial"


def test_aggregate_basis_matches_registry():
    for req in reg.evaluable_requirements():
        out = evaluate_rule(reg.rule_for(req), RuleInputs(), rule_version=RV)
        result = aggregate(req, out)
        if result is not None:
            assert result.basis == req.assessment_basis


# --- guardrail: no dynamic code execution in the rule path -----------------


def test_no_eval_or_exec_in_rule_engine_source():
    base = pathlib.Path(__file__).resolve().parents[1] / "app"
    for module_dir in ("rules", "registry"):
        for path in (base / module_dir).glob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "eval(" not in text, f"eval() in {path.name}"
            assert "exec(" not in text, f"exec() in {path.name}"
