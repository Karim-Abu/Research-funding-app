"""Additive contracts for the public-safe research workspace."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from app.research.text_normalization import (
    normalize_research_text,
    normalize_research_text_list,
)

ResearchModule = Literal[
    "market_growth",
    "competition_alternatives",
    "customer_problem",
    "state_of_the_art",
    "swiss_research_partners",
]
BriefListValue = Annotated[str, Field(max_length=120)]


class ResearchBriefInput(BaseModel):
    research_goal: str = Field(default="", max_length=500)
    search_tags: list[BriefListValue] = Field(default_factory=list, max_length=12)
    application_domain: str = Field(default="", max_length=120)
    technology_class: str = Field(default="", max_length=120)
    target_customer_segments: list[BriefListValue] = Field(default_factory=list, max_length=8)
    region: str = Field(default="", max_length=80)
    competence_needs: list[BriefListValue] = Field(default_factory=list, max_length=12)
    modules: list[ResearchModule] = Field(default_factory=list, min_length=1)

    @model_validator(mode="before")
    @classmethod
    def normalize_text_boundaries(cls, value):
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        for field_name in (
            "research_goal", "application_domain", "technology_class", "region",
        ):
            normalized[field_name] = normalize_research_text(
                normalized.get(field_name, "")
            )
        for field_name in (
            "search_tags", "target_customer_segments", "competence_needs",
        ):
            normalized[field_name] = normalize_research_text_list(
                normalized.get(field_name, [])
            )
        return normalized


class ResearchBriefView(ResearchBriefInput):
    research_brief_id: str
    version: int
    status: Literal["draft", "approved", "superseded"]
    approved_at: datetime | None = None


class ResearchBriefState(BaseModel):
    latest: ResearchBriefView | None = None
    active_approved: ResearchBriefView | None = None


class ResearchQueryView(BaseModel):
    approval_id: str | None = None
    research_brief_id: str
    module: ResearchModule
    planner_purpose: str
    query_text: str
    firewall_decision: str
    risk_score: int = Field(ge=0, le=10)
    risk_label: Literal["low", "medium", "high"]
    redaction_summary: list[dict] = Field(default_factory=list)
    status: Literal["pending", "approved", "rejected", "expired", "used", "blocked"]
    task_id: str | None = None
    task_status: str | None = None
    execution_mode: Literal["fake_demo", "live"] | None = None


class ResearchQueryPlan(BaseModel):
    brief: ResearchBriefView
    queries: list[ResearchQueryView]
    provider_mode: Literal["fake_demo", "live", "unavailable"]


class ResearchQueryEdit(BaseModel):
    module: ResearchModule
    planner_purpose: str
    query_text: str = Field(min_length=1, max_length=240)
    supersedes_approval_id: str | None = None


class ResearchRunRequest(BaseModel):
    approval_ids: list[str] = Field(min_length=1, max_length=20)


class ResearchRunResponse(BaseModel):
    task_ids: list[str]
    result_count: int
    execution_mode: Literal["fake_demo", "live", "unavailable"]


class ResearchSourceLocation(BaseModel):
    source_id: str
    source_version_id: str
    page: int | None = None
    section: str | None = None
    excerpt: str


class ResearchPartnerCandidateView(BaseModel):
    organization_or_group: str
    location: str | None = None
    location_status: Literal["verified", "unverified"] = "unverified"
    expertise_keywords: list[str] = Field(default_factory=list)
    possible_project_role: str
    why_potentially_relevant: str
    evidence_url: str
    status: Literal[
        "eligibility_verified", "likely_eligible", "needs_human_check"
    ] = "needs_human_check"
    competence_gap: str | None = None
    track_record_links: list[str] = Field(default_factory=list)
    eligibility_reference_date: str | None = None


class ResearchResultView(BaseModel):
    result_id: str
    task_id: str
    module: ResearchModule | None = None
    planner_purpose: str | None = None
    title: str
    source_url: str
    final_url: str | None = None
    domain: str
    snippet: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    source_category: str | None = None
    source_quality: str = "unassessed"
    freshness_label: str = "unbekannt"
    potential_sections: list[str] = Field(default_factory=list)
    coverage_status: str = "not_checked"
    support_status: str = "not_checked"
    content_review_status: str = "unreviewed"
    retrieved_at: datetime
    relevance_reason: str
    status: Literal["candidate", "imported", "rejected", "failed"]
    execution_mode: Literal["fake_demo", "live"] | None = None
    source_document_id: str | None = None
    source_locations: list[ResearchSourceLocation] = Field(default_factory=list)
    partner_candidate: ResearchPartnerCandidateView | None = None


class ResearchResultReviewInput(BaseModel):
    decision: Literal["supports", "partially_supports", "does_not_support"]


class ResearchResultReviewView(BaseModel):
    result_id: str
    status: Literal["imported", "rejected"]
    content_review_status: str
    support_status: str


class ResearchWorkspace(BaseModel):
    brief: ResearchBriefState
    queries: list[ResearchQueryView]
    results: list[ResearchResultView]
    provider_mode: Literal["fake_demo", "live", "unavailable"]
