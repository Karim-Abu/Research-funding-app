"""EvidenceAnchor + EvidenceLink schemas — exact openapi-v1_1.yaml shapes."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

VerificationStatus = Literal[
    "unverified", "exact_verified", "human_verified", "rejected"
]
# R6 Evidence-Statusleiter (additiv): Coverage ≠ Correctness. Abgeleitet in
# app/review/evidence_status.py — nie persistiert, nie vom Client gesetzt.
SupportStatus = Literal[
    "not_required",
    "evidence_missing",
    "location_found",
    "supports_partially",
    "supports_strongly",
    "conflict_or_uncertain",
    "human_review_required",
]
MatchType = Literal["exact_normalized", "fuzzy", "semantic", "manual"]
SourceType = Literal["pdf", "docx", "txt", "url"]
LinkTargetType = Literal[
    "requirement_assessment",
    "draft_version",
    "draft_claim",
    "review_finding",
    "extracted_fact",
]
LinkStatus = Literal["active", "stale", "removed"]


class EvidenceAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor_id: str
    source_version_id: str
    fragment_id: str
    quote: str
    verification_status: VerificationStatus
    source_id: str
    source_name: str
    source_type: SourceType
    normalizer_version: str
    page: int | None = None
    section: str | None = None
    match_type: MatchType | None = None
    human_checked_by: str | None = None
    human_checked_at: datetime | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    match_score: float | None = None
    coverage: float | None = None
    source_accessed_at: datetime | None = None
    support_status: SupportStatus | None = None
    scope: Literal["application", "external", "drafting_context"] = "application"
    rejection_reason_code: str | None = None
    rejection_text_de: str | None = None


class EvidenceLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_link_id: str
    anchor_id: str
    target_type: LinkTargetType
    target_id: str
    status: LinkStatus
    created_at: datetime
    claim_id: str | None = None
    claim_text: str | None = None
    support_status: SupportStatus | None = None
    run_id: str
    source_id: str | None = None
    source_version_id: str | None = None
    fragment_id: str | None = None
    scope: Literal["application", "external", "drafting_context"] = "application"
