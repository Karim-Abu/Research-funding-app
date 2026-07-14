"""Claim lineage mapping (Milestone 9K, STEP 3/4).

For a DraftClaim, gather in-run provenance (A1 facts, EvidenceAnchors via active
EvidenceLinks, EvidenceCandidates, SourceFragments, the A2 DraftSuggestion, source-backed
MarketComparison items, A3 findings) and compute a ``lineage_status`` + an evidence
``sufficiency_status`` (STEP 4). An anchor's mere existence is never enough — the claim
terms must plausibly connect to the evidence quote, and ``exact_verified`` never
auto-implies support.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisRun,
    DraftVersion,
    EvidenceAnchor,
    EvidenceCandidate,
    EvidenceLink,
    ExtractedFact,
    MarketComparison,
    MarketComparisonItem,
    PortalFieldDraft,
    ReviewFinding,
)
from app.evidence.tokenize import content_terms, is_trivial_quote
from app.reliability import RELIABILITY_PROFILE_ID
from app.reliability.extract import ExtractedClaim, is_quantified
from app.reliability import sufficiency as suff

A3_PROFILE_ID = "A3.evidence_consistency"
_UNCONFIRMED_FACT_STATUSES = {"proposed", "conflicted", "missing"}


@dataclass
class LineageResult:
    lineage_status: str
    sufficiency_status: str
    provenance: dict
    matched_terms: list[str]
    reason: str
    supported: bool = False
    proposed_fact_as_certain: bool = False
    market_backed: bool = False
    a3_flagged_field: bool = False
    agent_authored: bool = False


def _empty_provenance() -> dict:
    return {
        "extracted_fact_ids": [], "evidence_anchor_ids": [], "evidence_candidate_ids": [],
        "source_fragment_ids": [], "draft_suggestion_id": None, "market_item_ids": [],
        "a3_finding_ids": [],
    }


def build_lineage(
    db: Session, run: AnalysisRun, claim: ExtractedClaim
) -> LineageResult:
    claim_terms = content_terms(claim.claim_text)
    quantified = is_quantified(claim)
    provenance = _empty_provenance()
    prov_fields = provenance  # alias
    outcomes: list[suff.SufficiencyOutcome] = []
    conflict = False

    # --- field-linked EvidenceAnchors (via active EvidenceLinks to the draft version) ---
    draft = db.scalar(
        select(PortalFieldDraft).where(
            PortalFieldDraft.run_id == run.run_id,
            PortalFieldDraft.field_id == claim.field_id,
        )
    )
    version = db.get(DraftVersion, draft.current_version_id) if draft and draft.current_version_id else None
    agent_authored = bool(version and version.created_by == "agent")

    anchor_ids: list[str] = []
    if version is not None:
        links = db.scalars(
            select(EvidenceLink).where(
                EvidenceLink.run_id == run.run_id,
                EvidenceLink.target_type == "draft_version",
                EvidenceLink.target_id == version.draft_version_id,
                EvidenceLink.status == "active",
            )
        )
        anchor_ids = [link.anchor_id for link in links]

    has_field_anchor = False
    for anchor in _anchors(db, run, anchor_ids):
        # Teil C4 — triviale Kurz-Zitate («Overhead», «18/26») tragen keinen
        # Kontext: sie zählen weder als Coverage noch als Claim-Stützung.
        if is_trivial_quote(anchor.quote or ""):
            continue
        has_field_anchor = True
        # Coverage: the anchor is LINKED to the field regardless of whether it supports the
        # claim (coverage is presence; sufficiency below is correctness).
        prov_fields["evidence_anchor_ids"].append(anchor.anchor_id)
        if anchor.fragment_id:
            prov_fields["source_fragment_ids"].append(anchor.fragment_id)
        outcomes.append(suff.check_support(
            claim_text=claim.claim_text, claim_type=claim.claim_type,
            quantified=quantified, quote=anchor.quote,
        ))
        if suff.has_number_conflict(claim.claim_text, anchor.quote):
            conflict = True

    # --- A1 ExtractedFacts overlapping the claim (note proposed/unconfirmed) ---
    proposed_fact_as_certain = False
    for fact in db.scalars(select(ExtractedFact).where(ExtractedFact.run_id == run.run_id)):
        overlap = claim_terms & content_terms(fact.original_statement or "")
        if len(overlap) >= 2:
            prov_fields["extracted_fact_ids"].append(fact.fact_id)
            for frag_id in (fact.source_fragment_ids or []):
                if frag_id not in prov_fields["source_fragment_ids"]:
                    prov_fields["source_fragment_ids"].append(frag_id)
            if fact.status in _UNCONFIRMED_FACT_STATUSES and claim.strength != "weak":
                proposed_fact_as_certain = True

    # --- EvidenceCandidates (advisory, indirect) ---
    for cand in db.scalars(select(EvidenceCandidate).where(EvidenceCandidate.run_id == run.run_id)):
        if len(claim_terms & content_terms(cand.proposed_quote or "")) >= 2:
            prov_fields["evidence_candidate_ids"].append(cand.candidate_id)

    # --- A2 DraftSuggestion (agent authorship) ---
    if agent_authored and version is not None:
        sugg = db.scalar(_suggestion_query(run, version))
        if sugg is not None:
            prov_fields["draft_suggestion_id"] = sugg.suggestion_id

    # --- source-backed MarketComparison items for market claims ---
    market_backed = False
    if claim.claim_type == "market":
        for item, quote in _market_quotes(db, run):
            if len(claim_terms & content_terms(item.name + " " + (item.description or ""))) >= 1:
                prov_fields["market_item_ids"].append(item.item_id)
            outcome = suff.check_support(
                claim_text=claim.claim_text, claim_type=claim.claim_type,
                quantified=quantified, quote=quote,
            )
            if outcome.status in (suff.SUPPORTS, suff.WEAKLY):
                outcomes.append(outcome)
                market_backed = True

    # --- A3 findings on this field (advisory signal only) ---
    a3_findings = db.scalars(
        select(ReviewFinding).where(
            ReviewFinding.run_id == run.run_id,
            ReviewFinding.source == "agent",
            ReviewFinding.profile_id == A3_PROFILE_ID,
            ReviewFinding.field_id == claim.field_id,
            ReviewFinding.status == "open",
        )
    )
    prov_fields["a3_finding_ids"] = [f.finding_id for f in a3_findings]

    # --- decide sufficiency + lineage status ---
    best = suff.best_support(outcomes)
    has_any_evidence = bool(
        prov_fields["evidence_anchor_ids"] or prov_fields["extracted_fact_ids"]
        or prov_fields["evidence_candidate_ids"] or prov_fields["market_item_ids"]
    )
    supported = best.status == suff.SUPPORTS

    if conflict:
        lineage_status = "conflicting_evidence"
    elif supported:
        lineage_status = "direct_evidence"
    elif has_field_anchor:
        # A field anchor exists but does not (fully) support the claim → field-level only.
        lineage_status = "weak_evidence"
    elif has_any_evidence:
        lineage_status = "indirect_evidence"
    else:
        lineage_status = "no_evidence"

    return LineageResult(
        lineage_status=lineage_status,
        sufficiency_status=best.status,
        provenance=provenance,
        matched_terms=best.matched_terms,
        reason=best.reason,
        supported=supported,
        proposed_fact_as_certain=proposed_fact_as_certain,
        market_backed=market_backed,
        a3_flagged_field=bool(prov_fields["a3_finding_ids"]),
        agent_authored=agent_authored,
    )


def _anchors(db: Session, run: AnalysisRun, anchor_ids: list[str]):
    if not anchor_ids:
        return []
    return list(
        db.scalars(
            select(EvidenceAnchor).where(
                EvidenceAnchor.run_id == run.run_id,
                EvidenceAnchor.anchor_id.in_(anchor_ids),
            )
        )
    )


def _suggestion_query(run: AnalysisRun, version: DraftVersion):
    from app.db.models import DraftSuggestion

    return (
        select(DraftSuggestion)
        .where(
            DraftSuggestion.run_id == run.run_id,
            DraftSuggestion.accepted_draft_version_id == version.draft_version_id,
        )
        .limit(1)
    )


def _market_quotes(db: Session, run: AnalysisRun):
    """(item, verified_quote_text) pairs from source-backed MarketComparison items for the
    run's project. Only ``source_backed`` items with verified refs count as support."""
    comparison = db.scalar(
        select(MarketComparison).where(MarketComparison.project_id == run.project_id)
        .order_by(MarketComparison.created_at.desc())
    )
    if comparison is None:
        return []
    pairs: list[tuple[MarketComparisonItem, str]] = []
    items = db.scalars(
        select(MarketComparisonItem).where(
            MarketComparisonItem.comparison_id == comparison.comparison_id,
            MarketComparisonItem.confidence_label == "source_backed",
        )
    )
    for item in items:
        for ref in (item.verified_quote_refs or []):
            quote = ref.get("quote") if isinstance(ref, dict) else None
            if quote:
                pairs.append((item, quote))
    return pairs
