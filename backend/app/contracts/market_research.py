"""Market research API schemas (RESEARCH.1b).

Reuses the existing public web-research vertical end to end (Search Query Firewall →
ResearchExecutor → Fake/Firecrawl provider); these DTOs only expose the RESEARCH.1a
planner/runner/candidate view over HTTP. No new frozen contract, no new public purpose.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ProviderMode = Literal["fake", "firecrawl_live", "unavailable"]


class MarketTopicDto(BaseModel):
    application_domain: str
    technology_area: str
    target_customers: str
    region: str | None = None


class MarketTopicInput(BaseModel):
    application_domain: str | None = None
    technology_area: str | None = None
    target_customers: str | None = None
    region: str | None = None


class QueryCandidateDto(BaseModel):
    query_text: str
    purpose: str
    public_safe: bool
    approval_required: bool
    blocked_reason: str | None = None
    # R8 Freigabepflicht: pending Freigabe je Query; der Nutzer entscheidet über die
    # bestehenden /search-query-approvals/{id}/approve|reject-Endpoints.
    approval_id: str | None = None
    # Additiv (Freigabe 2026-07-23): persistierter Freigabe-Status der Query
    # ("pending"/"approved"/"rejected"/"expired"/"used"/"blocked"). Der Plan liefert
    # beim Re-Plan auch bereits entschiedene Queries — ohne Status rendert die UI
    # sie fälschlich als offen und ein erneutes Freigeben endet im 409.
    status: str | None = None


class MarketQueryPreviewInput(BaseModel):
    """Bearbeitete Query erneut prüfen (R8): Firewall + neue pending Freigabe."""

    query_text: str
    purpose: str | None = None


class MarketResearchPlanResponse(BaseModel):
    topic: MarketTopicDto
    queries: list[QueryCandidateDto]
    provider_mode: ProviderMode


class MarketResearchRunRequest(MarketTopicDto):
    """Run-Payload (R8): nur freigegebene Queries werden ausgeführt."""

    approval_ids: list[str] = []


class MarketCandidateDto(BaseModel):
    result_id: str
    purpose: str
    candidate_type: str
    title: str
    source_url: str
    snippet: str | None = None
    confidence: Literal["low", "medium"]
    status: str
    human_review_required: bool


class MarketResearchRunResponse(BaseModel):
    task_ids: list[str]
    result_count: int
    tool_invocation_count: int
    credits_used: float
    candidates: list[MarketCandidateDto]
    blocked_queries: int
    provider: str | None = None
