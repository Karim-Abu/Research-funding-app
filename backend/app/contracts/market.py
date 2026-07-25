"""Market comparison response schemas (Milestone 9I-B, beta-internal).

Public-facing fields only: no provider/model names, no confidence percentages, no raw
provider payloads. Evidence is surfaced as verified quotes + (optional) linked anchor id.

This contract intentionally remains additive:
- existing fields stay stable for backward compatibility,
- new analytical views are optional and derived at read-time.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ComparisonStatus = Literal[
    "draft", "ready_for_review", "limited", "insufficient_external_evidence",
    "stale", "failed",
]
ItemCategory = Literal[
    "competitor", "alternative_solution", "substitute", "incumbent_process",
    "reference_solution", "market_size_claim", "customer_problem", "unknown",
]
CandidateType = Literal[
    "direct_competitor",
    "adjacent_solution",
    "reference_infrastructure",
    "substitute",
    "open_source_solution",
    "manual_or_internal_alternative",
]
ItemRelation = Literal["similar", "complementary", "competing", "reference", "unclear"]
ConfidenceLabel = Literal["source_backed", "needs_review", "insufficient_evidence"]
ItemStatus = Literal["proposed", "accepted", "rejected", "needs_human_review"]
CompetitionJudgmentStatus = Literal[
    "direct_equivalent_found",
    "similar_solutions_found",
    "no_direct_equivalent_in_scope",
    "insufficient_evidence",
]


class MarketPicturePoint(BaseModel):
    label: str
    value: str


class MarketPicture(BaseModel):
    """Derived market landscape (strictly not a list of candidates)."""

    size_and_growth: list[MarketPicturePoint] = []
    segments: list[MarketPicturePoint] = []
    trends: list[MarketPicturePoint] = []
    demand_indicators: list[MarketPicturePoint] = []
    swiss_relevance: list[MarketPicturePoint] = []
    gaps: list[str] = []


class EvidenceQuote(BaseModel):
    quote: str
    source_document_id: str
    source_version_id: str
    linked_evidence_anchor_id: str | None = None
    source_url: str | None = None


class SolutionLandscapeCandidate(BaseModel):
    item_id: str
    name: str
    candidate_type: CandidateType
    description: str | None = None
    target_customer_segment: str | None = None
    offering_summary: str | None = None
    strengths: str | None = None
    weaknesses: str | None = None
    differentiation_relevance: str | None = None
    relation_to_project: ItemRelation
    relevant_functions: list[str] = []
    overlaps: list[str] = []
    evidencing_differentiators: list[str] = []
    # Plausible but not yet human-confirmed differentiators (kept strictly apart
    # from evidenced ones; an unreviewed quote is open, never a confirmed claim).
    unverified_differentiators: list[str] = []
    source_document_ids: list[str] = []
    evidence_quotes: list["EvidenceQuote"] = []
    status: ItemStatus
    confidence_label: ConfidenceLabel
    support_status: str | None = None
    source_scope_ok: bool = False
    allowed_formulations: list[str] = []
    disallowed_formulations: list[str] = []


class SolutionLandscape(BaseModel):
    candidates: list[SolutionLandscapeCandidate] = []
    candidate_count_by_type: dict[CandidateType, int] = {}


class CompetitionJudgment(BaseModel):
    status: CompetitionJudgmentStatus
    rationale: str
    scope_summary: str
    relevant_candidate_count: int
    key_overlaps: list[str] = []
    evidenced_differentiators: list[str] = []
    # Differentiators that are plausible from a found passage but not yet
    # human-confirmed. Surfaced separately so the UI never presents them as proven.
    plausible_unverified_differentiators: list[str] = []
    open_evidence_gaps: list[str] = []
    allowed_formulations: list[str] = []
    disallowed_formulations: list[str] = []
    can_insert_into_application: bool = False


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
    core_problem_or_benefit: str | None = None
    relevant_functions: list[str] = []
    price_business_model: str = "nicht \u00f6ffentlich belegt"
    uncertainty: str | None = None
    relation_to_project: ItemRelation
    confidence_label: ConfidenceLabel
    status: ItemStatus
    source_document_ids: list[str] = []
    evidence_quotes: list[EvidenceQuote] = []
    external_evidence_anchor_ids: list[str] = []
    cell_evidence: dict[str, list[str]] = {}
    coverage_status: Literal["exact_quote_verified"] | None = None
    support_status: Literal["unreviewed", "supports", "partial", "does_not_support"] | None = None
    candidate_type: CandidateType | None = None
    overlaps: list[str] = []
    evidencing_differentiators: list[str] = []
    allowed_formulations: list[str] = []
    disallowed_formulations: list[str] = []


class MarketComparison(BaseModel):
    comparison_id: str
    project_id: str
    workspace_id: str
    status: ComparisonStatus
    comparison_version: int
    generation_status: str | None = None
    generation_kind: Literal["fake_demo", "model_generated", "rule_template"] | None = None
    research_brief_id: str | None = None
    research_task_ids: list[str] = []
    query_approval_ids: list[str] = []
    source_version_ids: list[str] = []
    provider: str | None = None
    model_ref: str | None = None
    prompt_version: str | None = None
    context_hash: str | None = None
    stale_reason: str | None = None
    consequences: list[str] = []
    research_gaps: list[str] = []
    warnings: list[str] = []
    item_count: int = 0
    created_at: datetime
    updated_at: datetime
    error: str | None = None


class ComparisonBasis(BaseModel):
    """The user's own project idea shown as the explicit basis of the comparison.

    ``idea`` is the confidential project description — surfaced read-time for the
    user's own understanding only, never sent to search/external tools.
    ``search_focus``/``search_aspects`` are the public-safe descriptors the market
    search actually used (from the approved research brief), so the user sees both
    their idea and what was really searched.
    """

    title: str
    idea: str
    innovation_field: str | None = None
    search_focus: str | None = None
    search_aspects: list[str] = []


class MarketComparisonView(MarketComparison):
    items: list[MarketComparisonItem] = []
    market_picture: MarketPicture | None = None
    solution_landscape: SolutionLandscape | None = None
    competition_judgment: CompetitionJudgment | None = None
    comparison_basis: ComparisonBasis | None = None
    # Read-time scope-staleness, kept strictly separate from the runtime
    # ``status``: the persisted status stays the runtime truth, while this flags
    # that the current source scope no longer matches the one this was built on.
    scope_stale: bool = False


class ItemStatusUpdate(BaseModel):
    status: ItemStatus
    support_status: Literal["unreviewed", "supports", "partial", "does_not_support"] | None = None
