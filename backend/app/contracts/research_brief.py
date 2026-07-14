"""Additive contracts for the public-safe research workspace."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

ResearchModule = Literal[
    "market_growth",
    "competition_alternatives",
    "customer_problem",
    "state_of_the_art",
    "swiss_research_partners",
]
BriefListValue = Annotated[str, Field(max_length=120)]


class ResearchBriefInput(BaseModel):
    application_domain: str = Field(max_length=120)
    technology_class: str = Field(max_length=120)
    target_customer_segments: list[BriefListValue] = Field(default_factory=list, max_length=8)
    region: str = Field(default="", max_length=80)
    competence_needs: list[BriefListValue] = Field(default_factory=list, max_length=12)
    modules: list[ResearchModule] = Field(default_factory=list, min_length=1)


class ResearchBriefView(ResearchBriefInput):
    research_brief_id: str
    version: int
    status: Literal["draft", "approved", "superseded"]
    approved_at: datetime | None = None


class ResearchBriefState(BaseModel):
    latest: ResearchBriefView | None = None
    active_approved: ResearchBriefView | None = None


class ResearchQueryView(BaseModel):
    approval_id: str
    research_brief_id: str
    module: ResearchModule
    planner_purpose: str
    query_text: str
    firewall_decision: str
    risk_label: Literal["low", "medium", "high"]
    redaction_summary: list[dict] = Field(default_factory=list)
    status: Literal["pending", "approved", "rejected", "expired", "used"]
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
    status: Literal["candidate_not_eligibility_confirmed"] = (
        "candidate_not_eligibility_confirmed"
    )


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
    retrieved_at: datetime
    relevance_reason: str
    status: Literal["candidate", "imported", "rejected", "failed"]
    execution_mode: Literal["fake_demo", "live"] | None = None
    source_document_id: str | None = None
    source_locations: list[ResearchSourceLocation] = Field(default_factory=list)
    partner_candidate: ResearchPartnerCandidateView | None = None


class ResearchWorkspace(BaseModel):
    brief: ResearchBriefState
    queries: list[ResearchQueryView]
    results: list[ResearchResultView]
    provider_mode: Literal["fake_demo", "live", "unavailable"]
