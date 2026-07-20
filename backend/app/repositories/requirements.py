"""RequirementAssessment read model for listRequirements (run-scoped)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.requirement import OpenIssue as OpenIssueSchema
from app.contracts.requirement import RequirementAssessment as AssessmentSchema
from app.contracts.requirement import RuleEvidence
from app.db.models import HumanDecision, OpenIssue, RequirementAssessment
from app.registry import get_registry
from app.repositories import evidence as evidence_repo
from app.rules.aggregation import HUMAN_REVIEW_ISSUE_TYPES, is_guidance


def list_for_run(db: Session, run_id: str) -> list[RequirementAssessment]:
    return list(
        db.scalars(
            select(RequirementAssessment)
            .where(RequirementAssessment.run_id == run_id)
            .order_by(RequirementAssessment.created_at.asc())
        )
    )


def _issues_by_target(db: Session, run_id: str) -> dict[str, list[OpenIssue]]:
    grouped: dict[str, list[OpenIssue]] = {}
    rows = db.scalars(
        select(OpenIssue)
        .where(OpenIssue.run_id == run_id)
        .order_by(OpenIssue.created_at.asc())
    )
    for issue in rows:
        grouped.setdefault(issue.target_id, []).append(issue)
    return grouped


def _issue_to_contract(issue: OpenIssue) -> OpenIssueSchema:
    return OpenIssueSchema(
        issue_id=issue.issue_id,
        run_id=issue.run_id,
        issue_type=issue.issue_type,
        severity=issue.severity,
        description=issue.description,
        target_type=issue.target_type,
        target_id=issue.target_id,
        recommended_next_action=issue.recommended_next_action,
        status=issue.status,
        responsible_user_id=issue.responsible_user_id,
        created_at=issue.created_at,
    )


def _confirmed_assessment_ids(db: Session, run_id: str) -> set[str]:
    """Assessment-IDs mit menschlicher Bestätigung (HumanDecision confirm) —
    abgeleitet, keine zweite Wahrheitsquelle (RUN 2A Slice 1)."""
    rows = db.scalars(
        select(HumanDecision.target_id).where(
            HumanDecision.run_id == run_id,
            HumanDecision.target_type == "requirement_assessment",
            HumanDecision.action == "confirm",
        )
    )
    return set(rows)


def open_human_review_count(db: Session, run_id: str) -> int:
    """Offene menschliche Prüfungen/Bestätigungen (RUN 2A Slice 1) — die EINE
    Zählquelle für ``human_review_count``: offene OpenIssues der Review-Typen,
    deren Anforderung noch nicht menschlich bestätigt wurde (HumanDecision
    ``confirm`` auf dem Assessment). Eine Bestätigung ändert nur diese Zählung
    und ``review_status`` — nie den Compliance-Status oder das RuleResult."""
    confirmed = _confirmed_assessment_ids(db, run_id)
    confirmed_requirements = {
        a.requirement_id
        for a in list_for_run(db, run_id)
        if a.assessment_id in confirmed
    }
    issues = db.scalars(
        select(OpenIssue).where(
            OpenIssue.run_id == run_id,
            OpenIssue.status == "open",
            OpenIssue.issue_type.in_(HUMAN_REVIEW_ISSUE_TYPES),
        )
    )
    return sum(1 for i in issues if i.target_id not in confirmed_requirements)


def _review_status(
    assessment: RequirementAssessment,
    issue_rows: list[OpenIssue],
    confirmed_ids: set[str],
) -> str:
    review_issues = [
        i for i in issue_rows if i.issue_type in HUMAN_REVIEW_ISSUE_TYPES
    ]
    if not review_issues:
        return "not_required"
    if assessment.assessment_id in confirmed_ids:
        return "confirmed"
    return "required"


def to_contracts(
    db: Session, run_id: str, *, stale: bool
) -> list[AssessmentSchema]:
    issues = _issues_by_target(db, run_id)
    links = evidence_repo.links_by_assessment(db, run_id)
    all_links = [link for group in links.values() for link in group]
    link_statuses = evidence_repo.link_support_statuses(db, run_id, all_links)
    registry = get_registry()
    registry_requirements = registry.requirements
    confirmed_ids = _confirmed_assessment_ids(db, run_id)
    out: list[AssessmentSchema] = []
    for assessment in list_for_run(db, run_id):
        requirement_def = registry_requirements.get(assessment.requirement_id)
        issue_rows = issues.get(assessment.requirement_id, [])
        out.append(
            AssessmentSchema(
                assessment_id=assessment.assessment_id,
                requirement_id=assessment.requirement_id,
                title=assessment.title,
                status=assessment.status,
                basis=assessment.basis,
                reasoning=assessment.reasoning,
                # Staleness reflects current project/partner inputs vs snapshot.
                stale=stale or assessment.stale,
                evidence_links=[
                    evidence_repo.to_link_contract(
                        link,
                        support_status=link_statuses.get(link.evidence_link_id),
                        db=db,
                    )
                    for link in links.get(assessment.assessment_id, [])
                ],
                open_issues=[_issue_to_contract(i) for i in issue_rows],
                # From the registry (no DB field): the declared field scope.
                affected_field_ids=list(
                    requirement_def.affected_field_ids if requirement_def else []
                ),
                review_status=_review_status(assessment, issue_rows, confirmed_ids),
                display_mode=(
                    "guidance"
                    if requirement_def is not None and is_guidance(requirement_def)
                    else "requirement"
                ),
                rule_evidence=[
                    RuleEvidence(
                        rule_id=rule.rule_id,
                        registry_version=registry.rule_registry_version,
                        source_ref=source_ref,
                        source_title=registry.sources[source_ref].title,
                        source_url=registry.sources[source_ref].url,
                        source_path=registry.sources[source_ref].path,
                        last_verified=registry.sources[source_ref].last_verified,
                        evidence_quote=rule.description,
                    )
                    for rule_id in (
                        requirement_def.linked_rule_ids if requirement_def else []
                    )
                    if (rule := registry.rules.get(rule_id)) is not None
                    for source_ref in rule.source_refs
                ],
            )
        )
    return out
