"""Structured, deterministic inputs for the rule engine.

Built from the immutable run snapshot of project + partner data. Only structured
fields are used — never raw source text. Fields that M4 does not yet capture
(budget figures, duration, portal fields, scientific-integrity answers) stay
``None`` so the corresponding rules resolve to ``needs_input`` honestly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.registry.loader import EXPECTED_PROFILE_ID


@dataclass(frozen=True)
class PartnerInput:
    partner_type: str | None = None
    country: str | None = None
    swiss_value_creation: bool | None = None
    research_partner_eligibility_status: str | None = None
    personnel_independence_status: str | None = None
    financial_independence_status: str | None = None
    # Percent fields are not captured by the Partner schema in M4 (kept for
    # completeness / future structured evidence); always None today.
    ownership_percent: float | None = None
    financial_support_percent: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PartnerInput":
        return cls(
            partner_type=data.get("partner_type"),
            country=data.get("country"),
            swiss_value_creation=data.get("swiss_value_creation"),
            research_partner_eligibility_status=data.get(
                "research_partner_eligibility_status"
            ),
            personnel_independence_status=data.get("personnel_independence_status"),
            financial_independence_status=data.get("financial_independence_status"),
            ownership_percent=data.get("ownership_percent"),
            financial_support_percent=data.get("financial_support_percent"),
        )


@dataclass(frozen=True)
class RuleInputs:
    profile_id: str = EXPECTED_PROFILE_ID
    partners: list[PartnerInput] = field(default_factory=list)

    # Budget (not captured in M4 → None → needs_input).
    direct_total_project_costs_excluding_overhead: float | None = None
    implementation_own_contribution: float | None = None
    cash_contribution: float | None = None
    # Convenience aggregate used by the registry test cases.
    implementation_total: float | None = None
    total_requested_funding: float | None = None
    budget_exception_basis: str | None = None

    # Duration (not captured in M4 → None).
    duration_months: int | None = None
    duration_exception: str | None = None

    # Submission / scientific integrity (not captured in M4 → None).
    sanction_answer: bool | None = None
    sanction_comment: str | None = None
    human_decision_present: bool = False
    portal_fields_complete: bool | None = None

    @property
    def implementation_partners(self) -> list[PartnerInput]:
        return [p for p in self.partners if p.partner_type == "implementation_partner"]

    @property
    def research_partners(self) -> list[PartnerInput]:
        return [p for p in self.partners if p.partner_type == "research_partner"]

    @property
    def implementation_partner_count(self) -> int:
        return len(self.implementation_partners)

    @property
    def implementation_numerator(self) -> float | None:
        """Implementation-partner contribution = own contribution + cash; falls
        back to the aggregate ``implementation_total`` when the parts are not
        captured separately."""
        own = self.implementation_own_contribution
        cash = self.cash_contribution
        if own is not None or cash is not None:
            return (own or 0.0) + (cash or 0.0)
        return self.implementation_total


def inputs_from_snapshot(
    *, profile_id: str | None, partner_dicts: list[dict[str, Any]]
) -> RuleInputs:
    """Build engine inputs from the frozen project + partner snapshot."""
    return RuleInputs(
        profile_id=profile_id or EXPECTED_PROFILE_ID,
        partners=[PartnerInput.from_dict(p) for p in partner_dicts],
    )
