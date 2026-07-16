"""Market comparison response schemas (Milestone 9I-B, beta-internal).

Public-facing fields only: no provider/model names, no confidence percentages, no raw
provider payloads. Evidence is surfaced as verified quotes + (optional) linked anchor id.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ComparisonStatus = Literal["draft", "ready_for_review", "stale", "failed"]
ItemCategory = Literal[
    "competitor", "alternative_solution", "substitute", "incumbent_process",
    "reference_solution", "market_size_claim", "customer_problem", "unknown",
]
ItemRelation = Literal["similar", "complementary", "competing", "reference", "unclear"]
ConfidenceLabel = Literal["source_backed", "needs_review", "insufficient_evidence"]
ItemStatus = Literal["proposed", "accepted", "rejected", "needs_human_review"]


class EvidenceQuote(BaseModel):
    quote: str
    source_document_id: str
    source_version_id: str
    linked_evidence_anchor_id: str | None = None
    source_url: str | None = None


class MarketComparisonItem(BaseModel):
    item_id: str
    name: str
    category: ItemCategory
    description: str | None = None
    target_customer_segment: str | None = None
    offering_summary: str | None = None
    strengths: str | None = None
    weaknesses: str | None = None
    differentiation_relevance: str | None = None
    solution_type: str | None = None
    centralization: Literal["centralized", "decentralized", "hybrid", "unclear"] = "unclear"
    data_access_model: str | None = None
    swiss_relevance: str | None = None
    relation_to_project: ItemRelation
    confidence_label: ConfidenceLabel
    status: ItemStatus
    source_document_ids: list[str] = []
    evidence_quotes: list[EvidenceQuote] = []
    coverage_status: Literal["exact_quote_verified"] | None = None
    support_status: Literal["unreviewed", "supports", "partial", "does_not_support"] | None = None


class MarketComparison(BaseModel):
    comparison_id: str
    project_id: str
    status: ComparisonStatus
    comparison_version: int
    generation_status: str | None = None
    generation_kind: Literal["fake_demo", "model_generated", "rule_template"] | None = None
    research_gaps: list[str] = []
    warnings: list[str] = []
    item_count: int = 0
    created_at: datetime
    updated_at: datetime
    error: str | None = None


class MarketComparisonView(MarketComparison):
    items: list[MarketComparisonItem] = []


class ItemStatusUpdate(BaseModel):
    status: ItemStatus
    support_status: Literal["unreviewed", "supports", "partial", "does_not_support"] | None = None
