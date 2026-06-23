"""Aggregate a rule outcome into a RequirementAssessment + derive OpenIssues.

Conservative, contract-faithful mapping (RequirementAssessment.status enum:
fulfilled | partial | open | needs_input | blocked; basis = the requirement's
registry ``assessment_basis``). Missing inputs → needs_input; an applicable
blocker rule that fails → blocked; a hybrid rule that passes at machine level but
still needs human confirmation → partial; a semantic/human-gate requirement that
cannot be resolved deterministically → open; a non-applicable rule is omitted
(persisted only as a not_applicable RuleResult). No confidence percentages.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.registry.loader import RequirementDef
from app.rules.engine import RuleOutcome


@dataclass(frozen=True)
class IssueSpec:
    issue_type: str
    severity: str  # blocker | warning | info
    description: str
    recommended_next_action: str


@dataclass(frozen=True)
class AssessmentResult:
    requirement_id: str
    title: str
    status: str  # fulfilled | partial | open | needs_input | blocked
    basis: str
    reasoning: str
    issue: IssueSpec | None


def aggregate_status(requirement: RequirementDef, outcome: RuleOutcome) -> str | None:
    """Return the RequirementAssessment status, or None to omit the requirement
    (rule not applicable)."""
    if outcome.status == "not_applicable":
        return None
    label = outcome.outcome_label
    if outcome.status == "needs_input" or label == "needs_input":
        return "needs_input"
    if label == "human_decision_required":
        return "open"
    if outcome.status == "failed":
        return "blocked" if requirement.severity == "blocker" else "open"
    if label == "warning":
        return "partial"
    # outcome passed
    if requirement.assessment_basis == "deterministic_rule":
        return "fulfilled"
    if requirement.assessment_basis == "hybrid":
        # Machine-level pass; human confirmation of the evidence still required.
        return "partial"
    # semantic_assessment passed — M4 performs no semantic assessment.
    return "open"


def _issue_for(
    requirement: RequirementDef, status: str, reasoning: str
) -> IssueSpec | None:
    if status == "fulfilled":
        return None
    if status == "blocked":
        return IssueSpec(
            issue_type="requirement_blocked",
            severity="blocker",
            description=reasoning,
            recommended_next_action=(
                "Beheben Sie die blockierende Fördervoraussetzung "
                f"«{requirement.title}»."
            ),
        )
    if status == "needs_input":
        return IssueSpec(
            issue_type="missing_input",
            severity="warning",
            description=reasoning,
            recommended_next_action=(
                "Ergänzen Sie die fehlenden Angaben für "
                f"«{requirement.title}»."
            ),
        )
    if status == "open":
        return IssueSpec(
            issue_type="requires_human_review",
            severity="blocker" if requirement.severity == "blocker" else "warning",
            description=reasoning,
            recommended_next_action=(
                f"Lassen Sie «{requirement.title}» fachlich prüfen."
            ),
        )
    # partial — machine pre-check ok, human confirmation pending.
    return IssueSpec(
        issue_type="human_confirmation_pending",
        severity="info",
        description=reasoning,
        recommended_next_action=(
            "Bestätigen Sie die maschinelle Vorprüfung für "
            f"«{requirement.title}»."
        ),
    )


def aggregate(
    requirement: RequirementDef, outcome: RuleOutcome
) -> AssessmentResult | None:
    status = aggregate_status(requirement, outcome)
    if status is None:
        return None
    reasoning = outcome.reason or requirement.title
    return AssessmentResult(
        requirement_id=requirement.requirement_id,
        title=requirement.title,
        status=status,
        basis=requirement.assessment_basis,
        reasoning=reasoning,
        issue=_issue_for(requirement, status, reasoning),
    )
