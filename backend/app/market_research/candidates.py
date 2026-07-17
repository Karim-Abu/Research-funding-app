"""MarketCandidate view over ResearchResult (RESEARCH.1a).

A MarketCandidate is a **candidate**, never a fact and never evidence: a snippet does
not become an EvidenceAnchor here, and no market number (TAM/SAM/SOM) is asserted. The
view derives ``candidate_type``/``confidence`` deterministically from the originating
query purpose + provider rank; ``human_review_required`` is always True. No new DB model —
``ResearchResult`` carries the persistent state.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.db.models import ResearchResult

# Fine query purpose (planner) → MarketCandidate type.
_CANDIDATE_TYPE = {
    "market_size": "market_size_candidate",
    "competitors_alternatives": "competitor_or_alternative",
    "regulatory_demand_drivers": "market_driver_candidate",
    "customer_pain": "customer_segment",
    "state_of_the_art": "state_of_the_art_candidate",
    "go_to_market_channels": "go_to_market_signal",
    "pricing_willingness_to_pay": "pricing_signal",
}


@dataclass(frozen=True)
class MarketCandidate:
    result_id: str
    research_task_id: str
    purpose: str
    title: str
    source_url: str
    final_url: str | None
    snippet: str | None
    provider_rank: int | None
    status: str
    source_document_id: str | None
    candidate_type: str
    confidence: str  # low | medium (never high in the MVP)
    human_review_required: bool


def _confidence(result: ResearchResult) -> str:
    # MVP: never "high" (a snippet is not evidence). Rank-1 candidates are "medium",
    # everything else "low"; non-candidate states stay "low".
    if result.status == "candidate" and result.provider_rank == 1:
        return "medium"
    return "low"


def to_market_candidate(result: ResearchResult, *, query_purpose: str) -> MarketCandidate:
    return MarketCandidate(
        result_id=result.result_id,
        research_task_id=result.research_task_id,
        purpose=query_purpose,
        title=result.title,
        source_url=result.source_url,
        final_url=result.final_url,
        snippet=result.snippet,
        provider_rank=result.provider_rank,
        status=result.status,
        source_document_id=result.source_document_id,
        candidate_type=_CANDIDATE_TYPE.get(query_purpose, "market_signal"),
        confidence=_confidence(result),
        human_review_required=True,
    )


def to_market_candidates(
    purpose_by_task_id: dict[str, str], results: list[ResearchResult]
) -> list[MarketCandidate]:
    """Map ResearchResults to MarketCandidates using each result's task→query purpose."""
    return [
        to_market_candidate(r, query_purpose=purpose_by_task_id.get(r.research_task_id, ""))
        for r in results
    ]
