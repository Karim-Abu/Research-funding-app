"""Source scope + deterministic pre-filter for the market comparison (Milestone 9I-B).

Selects ONLY imported public sources (M9I-A: type=url, origin=public_source,
sensitivity=public) and deterministically pre-filters their SourceFragments to the
market-signal-bearing passages BEFORE any model call. Reuses the M5 deterministic
tokenizer; no embeddings, no network, no model-generated keywords, no search snippets.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    ResearchResult,
    ResearchTask,
    SourceDocument,
    SourceFragment,
    SourceVersion,
)
from app.evidence.tokenize import content_terms

# Versioned, explicit market-signal vocabulary (German + English). Deliberately small
# and generic — NOT domain synonyms, NOT company names. Used only to PRE-FILTER which
# already-imported public passages are worth structuring; it never invents content.
# market-signal-2 (R8): + Marktgrössen-/Wachstums- und Kundenproblem-Signale für die
# neuen Kategorien market_size_claim / customer_problem.
MARKET_SIGNAL_VERSION = "market-signal-2"
MARKET_SIGNAL_TERMS = frozenset(
    {
        # English
        "competitor", "competitors", "competition", "alternative", "alternatives",
        "solution", "solutions", "platform", "platforms", "product", "products",
        "market", "customers", "customer", "segment", "vendor", "vendors", "provider",
        "providers", "compared", "comparison", "unlike", "versus", "incumbent",
        "substitute", "offering", "differentiation", "competing", "rival", "rivals",
        "growth", "revenue", "demand", "problem", "problems", "pain", "need", "needs",
        "challenge", "challenges",
        # German
        "konkurrent", "konkurrenten", "konkurrenz", "wettbewerb", "wettbewerber",
        "alternative", "alternativen", "lösung", "lösungen", "plattform", "produkt",
        "produkte", "markt", "kunden", "kunde", "kundensegment", "anbieter", "anbietern",
        "vergleich", "verglichen", "unterschied", "differenzierung", "mitbewerber",
        "marktteilnehmer", "ersatz", "angebot",
        "marktgrösse", "marktgroesse", "marktvolumen", "wachstum", "umsatz", "nachfrage",
        "problem", "probleme", "bedarf", "herausforderung", "herausforderungen",
    }
)


@dataclass(frozen=True)
class FragmentCandidate:
    fragment_id: str
    source_version_id: str
    source_document_id: str
    source_name: str
    text: str
    signal_score: int


def imported_public_sources(
    db: Session, project_id: str, workspace_id: str
) -> list[SourceDocument]:
    """Live, fully processed and positively reviewed public research sources."""
    docs = db.scalars(
        select(SourceDocument)
        .join(
            ResearchResult,
            ResearchResult.source_document_id == SourceDocument.source_id,
        )
        .join(
            ResearchTask,
            ResearchTask.research_task_id == ResearchResult.research_task_id,
        )
        .join(
            SourceVersion,
            SourceVersion.source_version_id == SourceDocument.current_source_version_id,
        )
        .where(
            SourceDocument.project_id == project_id,
            SourceDocument.workspace_id == workspace_id,
            SourceDocument.type == "url",
            SourceDocument.status == "processed",
            SourceVersion.processing_status == "processed",
            SourceVersion.content_review_status == "reviewed",
            SourceVersion.content_safety_status.in_(("passed", "human_released")),
            ResearchResult.status == "imported",
            ResearchResult.content_review_status == "reviewed",
            ResearchResult.support_status.in_(("supports", "partially_supports")),
            ResearchTask.execution_mode == "live",
        )
    ).unique().all()
    result: list[SourceDocument] = []
    for doc in docs:
        dc = doc.data_classification or {}
        if dc.get("origin") != "public_source" or dc.get("sensitivity") != "public":
            continue
        result.append(doc)
    # Deterministic order: (created_at, source_id).
    result.sort(key=lambda d: (d.created_at, d.source_id))
    return result


def prefilter_fragments(
    db: Session,
    sources: list[SourceDocument],
    *,
    max_fragments: int = 40,
    char_budget: int = 24000,
    require_market_signal: bool = True,
) -> list[FragmentCandidate]:
    """Market-signal-bearing fragments from the imported public sources, deterministically
    ordered (source order, then fragment ordinal) and budget-limited."""
    candidates: list[FragmentCandidate] = []
    used = 0
    for doc in sources:
        version_id = doc.current_source_version_id
        if not version_id:
            continue
        version = db.get(SourceVersion, version_id)
        if version is None:
            continue
        fragments = list(
            db.scalars(
                select(SourceFragment).where(
                    SourceFragment.source_version_id == version_id
                )
            )
        )
        fragments.sort(key=lambda f: f.ordinal)
        # The source title/heading also contributes signal terms.
        title_terms = content_terms(doc.name or "")
        for frag in fragments:
            terms = content_terms(frag.normalized_text) | title_terms
            score = len(terms & MARKET_SIGNAL_TERMS)
            if score == 0 and require_market_signal:
                continue
            if score == 0:
                score = 1
            text = frag.normalized_text
            if used + len(text) > char_budget:
                continue
            candidates.append(
                FragmentCandidate(
                    fragment_id=frag.fragment_id,
                    source_version_id=version_id,
                    source_document_id=doc.source_id,
                    source_name=doc.name or "",
                    text=text,
                    signal_score=score,
                )
            )
            used += len(text)
            if len(candidates) >= max_fragments:
                return candidates
    return candidates


def source_scope_hash(sources: list[SourceDocument]) -> str:
    """Stable hash of the imported-source scope for staleness detection."""
    parts = sorted(
        f"{d.source_id}:{d.current_source_version_id}" for d in sources
    )
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def provenance(db: Session, sources: list[SourceDocument]) -> dict:
    """Allow-listed, versioned lineage for a comparison; never includes snippets."""
    source_ids = [document.source_id for document in sources]
    if not source_ids:
        return {
            "research_task_ids": [], "query_approval_ids": [],
            "research_brief_id": None, "source_version_ids": [],
        }
    rows = list(db.execute(
        select(ResearchResult, ResearchTask)
        .join(ResearchTask, ResearchTask.research_task_id == ResearchResult.research_task_id)
        .where(
            ResearchResult.source_document_id.in_(source_ids),
            ResearchResult.status == "imported",
        )
    ).all())
    tasks = sorted({task.research_task_id for _result, task in rows})
    approvals = sorted({task.firewall_approval_id for _result, task in rows if task.firewall_approval_id})
    briefs = sorted({task.research_brief_id for _result, task in rows if task.research_brief_id})
    return {
        "research_task_ids": tasks,
        "query_approval_ids": approvals,
        "research_brief_id": briefs[0] if len(briefs) == 1 else None,
        "source_version_ids": sorted({
            document.current_source_version_id for document in sources
            if document.current_source_version_id
        }),
    }
