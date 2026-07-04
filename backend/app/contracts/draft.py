"""PortalFieldDraft / DraftVersion / DraftPatch / EvidenceLinkCreate schemas —
exact openapi-v1_1.yaml shapes."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.evidence import EvidenceLink
from app.contracts.requirement import OpenIssue

DraftStatus = Literal["draft", "needs_review", "reviewed", "blocked", "stale"]
CreatedBy = Literal["agent", "user", "template", "carried_over"]


class DraftVersion(BaseModel):
    draft_version_id: str
    text: str
    character_count: int
    created_by: CreatedBy
    created_at: datetime
    content_hash: str


class PortalFieldDraft(BaseModel):
    draft_id: str
    field_id: str
    field_name: str
    status: DraftStatus
    current_version: DraftVersion
    character_count: int
    character_limit: int | None = None
    open_issue_count: int = 0
    evidence_links: list[EvidenceLink] = []
    open_issues: list[OpenIssue] = []


class DraftPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_version_id: str
    text: str
    source_operation_id: str | None = None


class EvidenceLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor_id: str
    base_version_id: str


class RedraftRequest(BaseModel):
    """createRedraft body (openapi RedraftRequest). Milestone 9D: request an
    advisory A2 draft suggestion for the current draft version."""

    model_config = ConfigDict(extra="forbid")

    base_version_id: str
    guidance: str | None = Field(default=None, max_length=4000)
