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
    # Milestone 9J: for confidential (D1/D2) projects the raw query never reaches the
    # provider — the caller must first obtain a firewall-sanitized, human-approved query
    # (Search Query Firewall) and pass its ``approval_id`` here. Ignored for D0.
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
