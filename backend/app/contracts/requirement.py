"""RequirementAssessment + OpenIssue schemas — exact openapi-v1_1.yaml shapes."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

RequirementStatus = Literal["fulfilled", "partial", "open", "needs_input", "blocked"]
AssessmentBasis = Literal[
    "deterministic_rule", "semantic_assessment", "hybrid", "human_override"
]
IssueSeverity = Literal["blocker", "warning", "info"]
IssueStatus = Literal["open", "resolved", "overridden", "dismissed"]


class OpenIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_id: str
    run_id: str
    issue_type: str
    severity: IssueSeverity
    description: str
    target_type: str
    target_id: str
    recommended_next_action: str
    status: IssueStatus
    responsible_user_id: str | None = None
    created_at: datetime


class RequirementAssessment(BaseModel):
    assessment_id: str
    requirement_id: str
    title: str | None = None
    status: RequirementStatus
    basis: AssessmentBasis
    reasoning: str
    stale: bool
    # M4 produces no evidence links (no extraction/anchoring).
    evidence_links: list[dict] = []
    open_issues: list[OpenIssue] = []
