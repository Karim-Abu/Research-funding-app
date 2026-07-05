"""Structured, deterministic inputs for the rule engine.

Built from the immutable run snapshot of project + partner data. Only structured
fields are used — never raw source text. Budget figures and duration come from
the frozen project snapshot (Slice 1); fields that are still not captured
(portal fields, scientific-integrity answers) stay ``None`` so the
corresponding rules resolve to ``needs_input`` honestly.
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

    # Budget — mapped from the frozen project snapshot; None → needs_input.
    direct_total_project_costs_excluding_overhead: float | None = None
    implementation_own_contribution: float | None = None
    cash_contribution: float | None = None
    # Convenience aggregate used by the registry test cases.
    implementation_total: float | None = None
    total_requested_funding: float | None = None
    budget_exception_basis: str | None = None

    # Duration — mapped from the frozen project snapshot; None → needs_input.
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
        """Implementation-partner contribution = own contribution + cash — only
        when BOTH parts are captured (a partial sum would turn incomplete data
        into a definitive verdict; missing parts must yield ``needs_input``).
        Falls back to the aggregate ``implementation_total`` otherwise."""
        own = self.implementation_own_contribution
        cash = self.cash_contribution
        if own is not None and cash is not None:
            return own + cash
        return self.implementation_total


def _clean_basis(value: Any) -> str | None:
    """Exception basis is only meaningful as non-empty text (whitespace-only
    must not claim an exception)."""
    if not isinstance(value, str):
        return None
    return value.strip() or None


def inputs_from_snapshot(
    *,
    profile_id: str | None,
    partner_dicts: list[dict[str, Any]],
    project_dict: dict[str, Any] | None = None,
) -> RuleInputs:
    """Build engine inputs from the frozen project + partner snapshot. Budget
    and duration come from ``project_dict`` (Slice 1); absent values stay None
    so the budget rules resolve to ``needs_input``."""
    project = project_dict or {}
    return RuleInputs(
        profile_id=profile_id or EXPECTED_PROFILE_ID,
        partners=[PartnerInput.from_dict(p) for p in partner_dicts],
        direct_total_project_costs_excluding_overhead=project.get(
            "direct_total_project_costs_excluding_overhead"
        ),
        implementation_own_contribution=project.get(
            "implementation_own_contribution"
        ),
        cash_contribution=project.get("cash_contribution"),
        total_requested_funding=project.get("total_requested_funding"),
        budget_exception_basis=_clean_basis(project.get("budget_exception_basis")),
        duration_months=project.get("duration_months"),
    )
