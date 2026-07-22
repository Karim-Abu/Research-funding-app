"""Public web research schemas (Milestone 9I-A) — mirrors the openapi Research models.

The ``purpose`` enum is the finalized contract's competence/partner-research set; the
milestone's market/competitor purposes are deferred to M9I-B (no contract change).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ResearchPurpose = Literal[
    "partner_role_suggestion", "competence_gap_analysis", "publication_track_record"
]
SubjectType = Literal["person", "organisation", "topic"]
ResearchTaskStatus = Literal[
    "queued", "running", "succeeded", "failed", "cancelled"
]
ResearchResultStatus = Literal["candidate", "imported", "rejected"]
IdentityMatchStatus = Literal["not_applicable", "matched", "ambiguous", "unresolved"]


class ResearchTaskCreate(BaseModel):
    purpose: ResearchPurpose
    subject_type: SubjectType
    subject_name: str | None = None
    query_preview: str = Field(min_length=1)
    max_results: int = Field(ge=1, le=50)
    preferred_domains: list[str] = Field(default_factory=list)
    # Contract: const true — the user explicitly confirms a public professional purpose.
    user_confirms_public_professional_purpose: Literal[True]
    internal_public_confirmation_id: str | None = None
    competence_needs: list[str] = Field(default_factory=list)
    requested_partner_roles: list[str] = Field(default_factory=list)
    # Normal product use requires a firewall-approved query linked to an approved public
    # research brief for D0/D1/D2. ``query_preview`` is never trusted as the execution
    # query; the server loads the sanitized text by this approval id.
    approval_id: str | None = None


class ResearchTask(BaseModel):
    task_id: str
    project_id: str
    operation_id: str | None = None
    status: ResearchTaskStatus
    purpose: str
    created_at: datetime
    completed_at: datetime | None = None
    result_count: int = 0
    error: str | None = None


class ProfessionalEvidence(BaseModel):
    professional_evidence_id: str
    evidence_type: Literal[
        "institutional_profile", "publication", "public_project",
        "professional_competence", "track_record",
    ]
    subject_name: str
    organisation: str | None = None
    claim: str
    source_url: str
    source_title: str
    accessed_at: datetime
    source_id: str | None = None


class PartnerRoleSuggestion(BaseModel):
    suggestion_id: str
    role_name: str
    competence_gap: str
    suggested_subject_name: str | None = None
    suggested_organisation: str | None = None
    professional_evidence_ids: list[str] = Field(default_factory=list)
    status: Literal["suggested", "accepted", "rejected"]
    human_review_required: bool = True


class ResearchResult(BaseModel):
    result_id: str
    task_id: str
    source_url: str
    title: str
    snippet: str | None = None
    accessed_at: datetime
    status: ResearchResultStatus
    professional_evidence_type: str | None = None
    professional_evidence: list[ProfessionalEvidence] = Field(default_factory=list)
    partner_role_suggestions: list[PartnerRoleSuggestion] = Field(default_factory=list)
    identity_match_status: IdentityMatchStatus = "not_applicable"


class ExternalAnchorCreate(BaseModel):
    fragment_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class ExternalAnchorPassageView(BaseModel):
    """Bounded, exact public-source passage offered for explicit human review."""

    result_id: str
    source_id: str
    source_version_id: str
    fragment_id: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    public_domain: str
    page_title: str
    excerpt: str = Field(min_length=1, max_length=300)
    quote_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    safety_status: str
    content_review_status: str


class ExternalAnchorView(BaseModel):
    anchor_id: str
    project_id: str
    workspace_id: str
    research_task_id: str
    source_id: str
    source_version_id: str
    fragment_id: str
    scope: Literal["external"] = "external"
    verification_status: Literal["exact_verified"] = "exact_verified"


class ResearchHandoffSource(BaseModel):
    source_id: str
    source_version_id: str
    research_task_id: str
    approval_id: str
    content_review_status: str
    content_safety_status: str
    stale: bool = False
    stale_reason: str | None = None


class ResearchHandoffView(BaseModel):
    project_id: str
    workspace_id: str
    research_brief_id: str | None = None
    research_run_ids: list[str] = Field(default_factory=list)
    research_task_ids: list[str] = Field(default_factory=list)
    approval_ids: list[str] = Field(default_factory=list)
    current_source_version_ids: list[str] = Field(default_factory=list)
    external_evidence_anchor_ids: list[str] = Field(default_factory=list)
    current_market_comparison_id: str | None = None
    market_comparison_status: str | None = None
    market_comparison_stale_reason: str | None = None
    sources: list[ResearchHandoffSource] = Field(default_factory=list)
