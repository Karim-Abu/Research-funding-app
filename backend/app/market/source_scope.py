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

from app.db.models import SourceDocument, SourceFragment, SourceVersion
from app.evidence.tokenize import content_terms

# Versioned, explicit market-signal vocabulary (German + English). Deliberately small
# and generic — NOT domain synonyms, NOT company names. Used only to PRE-FILTER which
# already-imported public passages are worth structuring; it never invents content.
MARKET_SIGNAL_VERSION = "market-signal-1"
MARKET_SIGNAL_TERMS = frozenset(
    {
        # English
        "competitor", "competitors", "competition", "alternative", "alternatives",
        "solution", "solutions", "platform", "platforms", "product", "products",
        "market", "customers", "customer", "segment", "vendor", "vendors", "provider",
        "providers", "compared", "comparison", "unlike", "versus", "incumbent",
        "substitute", "offering", "differentiation", "competing", "rival", "rivals",
        # German
        "konkurrent", "konkurrenten", "konkurrenz", "wettbewerb", "wettbewerber",
        "alternative", "alternativen", "lösung", "lösungen", "plattform", "produkt",
        "produkte", "markt", "kunden", "kunde", "kundensegment", "anbieter", "anbietern",
        "vergleich", "verglichen", "unterschied", "differenzierung", "mitbewerber",
        "marktteilnehmer", "ersatz", "angebot",
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
    """Processed, web-imported public sources for the project (M9I-A import path)."""
    docs = db.scalars(
        select(SourceDocument).where(
            SourceDocument.project_id == project_id,
            SourceDocument.workspace_id == workspace_id,
            SourceDocument.type == "url",
            SourceDocument.status == "processed",
        )
    ).all()
    result: list[SourceDocument] = []
    for doc in docs:
        dc = doc.data_classification or {}
        if dc.get("origin") == "public_source" and dc.get("sensitivity") == "public":
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
            if score == 0:
                continue
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
