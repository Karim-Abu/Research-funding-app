"""R2.6 — entity-spezifische Regel-Meldungen aus dem Owner-approvten Katalog.

Zweig-Semantik bleibt unverändert (missing benennt die fehlende Angabe, rät
nie pass/fail); nur die Texte kommen aus docs/repair/message-catalog.md.
"""
from __future__ import annotations

from pathlib import Path

from app.registry import get_registry
from app.rules.engine import evaluate_rule
from app.rules.inputs import PartnerInput, RuleInputs

_IMPL_RULE = "INNO.PARTNER.IMPLEMENTATION.MIN1_CH"
_RESEARCH_RULE = "INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE"
_FINANCIAL_RULE = "INNO.PARTNER.INDEPENDENCE.FINANCIAL_20"

_ALTTEXT = "Kein passender Partner vorhanden"


def _partner(**overrides) -> PartnerInput:
    base = dict(
        partner_type="implementation_partner",
        country="CH",
        swiss_value_creation=True,
        research_partner_eligibility_status=None,
        personnel_independence_status=None,
        financial_independence_status=None,
    )
    base.update(overrides)
    return PartnerInput(**base)


def _inputs(partners: list[PartnerInput]) -> RuleInputs:
    return RuleInputs(
        profile_id="innosuisse_innovation_project_with_implementation_partner",
        partners=partners,
    )


def _evaluate(rule_id: str, partners: list[PartnerInput]):
    rule = get_registry().rules[rule_id]
    return evaluate_rule(rule, _inputs(partners), rule_version="test")


class TestImplementationPartnerMessages:
    def test_false_branch_uses_catalog_text(self) -> None:
        outcome = _evaluate(_IMPL_RULE, [])
        assert outcome.mapping_key == "false"
        assert outcome.reason == "Kein Umsetzungspartner mit Schweiz-Bezug erfasst."

    def test_missing_branch_names_the_missing_input(self) -> None:
        outcome = _evaluate(
            _IMPL_RULE, [_partner(swiss_value_creation=None)]
        )
        assert outcome.mapping_key == "missing"
        assert "Umsetzungspartner" in outcome.reason
        assert "Prüfung nicht abschliessend" in outcome.reason
        # missing rät nie pass/fail (Zweig-Semantik unverändert).
        assert outcome.status == "needs_input"

    def test_true_branch_uses_catalog_text(self) -> None:
        outcome = _evaluate(_IMPL_RULE, [_partner()])
        assert outcome.mapping_key == "true"
        assert outcome.reason == "Umsetzungspartner mit Schweiz-Bezug erfasst."


class TestResearchPartnerMessages:
    def test_false_branch_uses_catalog_text(self) -> None:
        outcome = _evaluate(_RESEARCH_RULE, [])
        assert outcome.mapping_key == "false"
        assert outcome.reason == (
            "Kein beitragsberechtigter Schweizer Forschungspartner erfasst."
        )

    def test_missing_branch_names_eligibility(self) -> None:
        outcome = _evaluate(
            _RESEARCH_RULE,
            [
                _partner(
                    partner_type="research_partner",
                    research_partner_eligibility_status="needs_verification",
                )
            ],
        )
        assert outcome.mapping_key == "missing"
        assert "Beitragsberechtigung" in outcome.reason

    def test_true_branch_uses_catalog_text(self) -> None:
        outcome = _evaluate(
            _RESEARCH_RULE,
            [
                _partner(
                    partner_type="research_partner",
                    research_partner_eligibility_status="eligible",
                )
            ],
        )
        assert outcome.mapping_key == "true"
        assert outcome.reason == (
            "Beitragsberechtigter Schweizer Forschungspartner erfasst."
        )


class TestFinancialIndependenceMessages:
    def test_missing_needs_human_review_text(self) -> None:
        outcome = _evaluate(_FINANCIAL_RULE, [_partner()])
        assert outcome.mapping_key == "missing"
        assert outcome.reason == (
            "Finanzielle Unabhängigkeit benötigt menschliche Prüfung."
        )
        assert outcome.status == "needs_input"

    def test_confirmed_uses_catalog_text(self) -> None:
        outcome = _evaluate(
            _FINANCIAL_RULE,
            [_partner(financial_independence_status="confirmed")],
        )
        assert outcome.mapping_key == "below_threshold_and_confirmed"
        assert outcome.reason == (
            "Finanzielle Unabhängigkeit bestätigt; Beteiligungen unter der Schwelle."
        )


class TestAlttextRemoved:
    def test_alttext_not_in_active_rule_sources(self) -> None:
        """grep-Test: der generische Alttext existiert nicht mehr im Regelcode."""
        rules_dir = Path(__file__).resolve().parents[1] / "app" / "rules"
        for path in rules_dir.glob("*.py"):
            content = path.read_text(encoding="utf-8")
            assert _ALTTEXT not in content, f"Alttext noch in {path.name}"

    def test_alttext_not_in_rule_outputs(self) -> None:
        for rule_id in (_IMPL_RULE, _RESEARCH_RULE):
            outcome = _evaluate(rule_id, [])
            assert _ALTTEXT not in outcome.reason
