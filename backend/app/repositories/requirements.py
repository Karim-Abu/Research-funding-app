"""RequirementAssessment read model for listRequirements (run-scoped)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.requirement import OpenIssue as OpenIssueSchema
from app.contracts.requirement import RequirementAssessment as AssessmentSchema
from app.db.models import OpenIssue, RequirementAssessment
from app.registry import get_registry
from app.repositories import evidence as evidence_repo


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


def to_contracts(
    db: Session, run_id: str, *, stale: bool
) -> list[AssessmentSchema]:
    issues = _issues_by_target(db, run_id)
    links = evidence_repo.links_by_assessment(db, run_id)
    registry_requirements = get_registry().requirements
    out: list[AssessmentSchema] = []
    for assessment in list_for_run(db, run_id):
        requirement_def = registry_requirements.get(assessment.requirement_id)
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
                    evidence_repo.to_link_contract(link)
                    for link in links.get(assessment.assessment_id, [])
                ],
                open_issues=[
                    _issue_to_contract(i)
                    for i in issues.get(assessment.requirement_id, [])
                ],
                # From the registry (no DB field): the declared field scope.
                affected_field_ids=list(
                    requirement_def.affected_field_ids if requirement_def else []
                ),
            )
        )
    return out
