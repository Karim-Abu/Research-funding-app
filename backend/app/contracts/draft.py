"""PortalFieldDraft / DraftVersion / DraftPatch / EvidenceLinkCreate schemas —
exact openapi-v1_1.yaml shapes."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.evidence import EvidenceLink
from app.contracts.requirement import OpenIssue

DraftStatus = Literal["draft", "needs_review", "reviewed", "blocked", "stale"]
CreatedBy = Literal["agent", "user", "template", "carried_over", "import"]
# R6 Copy-Readiness (additiv): kanonische Kopierbereitschaft je Feld,
# abgeleitet in app/review/copy_readiness.py. Führt, sperrt nie.
CopyReadiness = Literal[
    "blocker", "placeholders_open", "not_reviewed", "draft", "copy_ready"
]


class DraftVersion(BaseModel):
    draft_version_id: str
    text: str
    character_count: int
    created_by: CreatedBy
    created_at: datetime
    content_hash: str
    generation_kind: Literal[
        "rule_template", "fake_demo", "model_generated"
    ] | None = None


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
    copy_readiness: CopyReadiness | None = None


class DraftPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_version_id: str
    text: str
    source_operation_id: str | None = None


class EvidenceLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor_id: str
    base_version_id: str


class FieldSuggestionRead(BaseModel):
    """Read-only Antwort von GET /runs/{id}/fields/{field}/suggestion:
    die offene (proposed) A2-Suggestion zur AKTUELLEN Basisversion — derselbe
    View wie das Redraft-Operation-Result — oder null. Additiv; die Annahme
    läuft unverändert über updateField mit source_operation_id."""

    suggestion: dict | None = None


class FieldSuggestionsRead(BaseModel):
    suggestions: list[dict] = []


class RedraftRequest(BaseModel):
    """createRedraft body (openapi RedraftRequest). Milestone 9D: request an
    advisory A2 draft suggestion for the current draft version."""

    model_config = ConfigDict(extra="forbid")

    base_version_id: str
    guidance: str | None = Field(default=None, max_length=4000)
    target_section: str | None = Field(default=None, max_length=16)
