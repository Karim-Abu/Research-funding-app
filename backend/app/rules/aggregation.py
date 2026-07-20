"""Aggregate a rule outcome into a RequirementAssessment + derive OpenIssues.

Conservative, contract-faithful mapping (RequirementAssessment.status enum:
fulfilled | partial | open | needs_input | blocked; basis = the requirement's
registry ``assessment_basis``). Missing inputs → needs_input; an applicable
blocker rule that fails → blocked; a semantic/human-gate requirement that
cannot be resolved deterministically → open; a non-applicable rule is omitted
(persisted only as a not_applicable RuleResult). No confidence percentages.

RUN 2A Slice 1 (Owner-Entscheide, 2026-07-19):

* **Compliance ≠ Human Review.** Ein maschinell bestandener Hybrid-Check ist
  ``fulfilled`` — die noch offene menschliche Bestätigung ist eine SEPARATE
  Dimension (OpenIssue ``human_confirmation_pending`` → abgeleiteter
  ``review_status`` im Contract) und stuft die Compliance nie herab.
* **Guidance zählt nirgends.** Informationsregeln (Registry-Signatur:
  ``severity == "info"``, z. B. «Keine formale finanzielle Obergrenze») gehen
  in keine Erfüllungsquote, erscheinen nie als offen/blocker, erzeugen nie
  Issues und werden in der UI nur als «Hinweis» gezeigt (``display_mode``).
  Fehlen die Angaben für einen Guidance-Hinweis, wird er weggelassen statt als
  ``needs_input`` gezählt.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.registry.loader import RequirementDef
from app.rules.engine import RuleOutcome

# Registry-Signatur für Informations-/Guidance-Anforderungen (vorhandenes
# Feld, bewusst KEINE zweite Registry und kein neues Schema).
GUIDANCE_SEVERITY = "info"

# Issue-Typen, die eine offene menschliche Prüfung/Bestätigung repräsentieren —
# die EINE Quelle für ``human_review_count`` und ``review_status``.
HUMAN_REVIEW_ISSUE_TYPES = ("human_confirmation_pending", "requires_human_review")


def is_guidance(requirement: RequirementDef) -> bool:
    return requirement.severity == GUIDANCE_SEVERITY


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
    (rule not applicable, or guidance without confirmable data)."""
    if outcome.status == "not_applicable":
        return None
    label = outcome.outcome_label
    if is_guidance(requirement):
        # Guidance: nur bestätigende Anzeige («Hinweis»). Ohne auswertbare
        # Angaben wird der Hinweis weggelassen — nie needs_input/open.
        if outcome.status == "passed" and label not in ("needs_input", "warning"):
            return "fulfilled"
        return None
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
        # Owner-Entscheid RUN 2A: maschinell bestanden bleibt fulfilled; die
        # menschliche Bestätigung läuft als separates Issue (siehe _issue_for),
        # nie als Herabstufung auf «Teilweise erfüllt».
        return "fulfilled"
    # semantic_assessment passed — M4 performs no semantic assessment.
    return "open"


def _issue_for(
    requirement: RequirementDef, status: str, reasoning: str
) -> IssueSpec | None:
    if is_guidance(requirement):
        # Guidance erzeugt nie Issues (keine Blocker-/Warning-/Info-Zählung).
        return None
    if status == "fulfilled":
        if requirement.assessment_basis == "hybrid":
            # Compliance erfüllt — die offene menschliche Bestätigung ist eine
            # eigene Dimension (review_status), kein Compliance-Abzug.
            return IssueSpec(
                issue_type="human_confirmation_pending",
                severity="info",
                description=reasoning,
                recommended_next_action=(
                    "Bestätigen Sie die maschinelle Vorprüfung für "
                    f"«{requirement.title}»."
                ),
            )
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
    # partial — advisory outside range (z. B. übliche Projektdauer) or an
    # explicitly partial content assessment; human confirmation pending.
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
