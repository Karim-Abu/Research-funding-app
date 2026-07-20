"""RequirementAssessment + OpenIssue schemas — exact openapi-v1_1.yaml shapes."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.contracts.evidence import EvidenceLink

RequirementStatus = Literal["fulfilled",
                            "partial", "open", "needs_input", "blocked"]
AssessmentBasis = Literal[
    "deterministic_rule", "semantic_assessment", "hybrid", "human_override"
]
IssueSeverity = Literal["blocker", "warning", "info"]
IssueStatus = Literal["open", "resolved", "overridden", "dismissed"]
# RUN 2A Slice 1 (additiv, abgeleitet — keine zweite Wahrheitsquelle):
# review_status aus OpenIssues (human_confirmation_pending/requires_human_review)
# + HumanDecisions (action=confirm auf requirement_assessment); display_mode aus
# der Registry (severity == "info" ⇒ Guidance/«Hinweis», zählt in keiner Quote).
ReviewStatus = Literal["not_required", "required", "confirmed"]
DisplayMode = Literal["requirement", "guidance"]


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
    # Populated in M5 from the deterministic evidence baseline (anchor links).
    evidence_links: list[EvidenceLink] = []
    open_issues: list[OpenIssue] = []
    # Additive (Slice 4, E4-A): registry-declared portal fields this requirement
    # affects — enables the direct field↔requirement join in the editor.
    affected_field_ids: list[str] = []
    # Additive (RUN 2A Slice 1): offene/bestätigte menschliche Prüfung als
    # SEPARATE Dimension — ändert den Compliance-``status`` nie.
    review_status: ReviewStatus = "not_required"
    # Additive (RUN 2A Slice 1): Guidance-Hinweise werden getrennt angezeigt
    # und zählen in keiner Erfüllungsquote/keinem Filter.
    display_mode: DisplayMode = "requirement"
