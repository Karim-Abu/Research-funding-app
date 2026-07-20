"""Deterministic lexical candidate discovery (Milestone 5, version below).

Generates EvidenceCandidate specs from active user-facing RequirementDefinitions
and the frozen SourceFragments of the run snapshot — using only exact,
case-insensitive, Unicode-aware token overlap. No embeddings, no network, no
model-generated keywords, no domain synonyms. Output is fully deterministic and
stably ordered. A candidate quote is an exact span copied from the normalized
source text, with its exact position recorded.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisRun,
    SourceDocument,
    SourceFragment,
    SourceVersion,
)
from app.evidence.scope_policy import application_source
from app.evidence.tokenize import content_terms
from app.registry import get_registry

RETRIEVAL_ALGORITHM_VERSION = "evidence-lexical-1"
DEFAULT_MAX_CANDIDATES_PER_REQUIREMENT = 3

# Deterministic sentence/paragraph boundaries (no NLP model).
_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass(frozen=True)
class CandidateSpec:
    target_requirement_id: str
    fragment_id: str
    source_version_id: str
    source_id: str
    source_name: str
    source_type: str
    page: int | None
    section: str | None
    proposed_quote: str
    quote_hash: str
    span_start_in_fragment: int
    span_end_in_fragment: int
    retrieval_score: float


def quote_hash(quote: str) -> str:
    return hashlib.sha256(quote.encode("utf-8")).hexdigest()


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _spans(text: str) -> list[tuple[int, int]]:
    """(start, end) spans of sentences/paragraphs, offsets into `text`,
    whitespace-trimmed so each quote is an exact clean substring."""
    spans: list[tuple[int, int]] = []
    pos = 0
    for match in _BOUNDARY_RE.finditer(text):
        start, end = _trim(text, pos, match.start())
        if end > start:
            spans.append((start, end))
        pos = match.end()
    start, end = _trim(text, pos, len(text))
    if end > start:
        spans.append((start, end))
    return spans


def _ordered_sources(
    db: Session, run: AnalysisRun
) -> list[tuple[SourceVersion, SourceDocument | None]]:
    """Frozen sources of the run snapshot in explicit canonical order:
    (SourceVersion.created_at, source_id) — computed in code, never DB order."""
    primary = application_source(db, run)
    return [primary] if primary is not None else []


def discover_candidates(
    db: Session,
    run: AnalysisRun,
    *,
    max_per_requirement: int = DEFAULT_MAX_CANDIDATES_PER_REQUIREMENT,
) -> list[CandidateSpec]:
    registry = get_registry()
    requirements = registry.evaluable_requirements()
    sources = _ordered_sources(db, run)

    # Extract spans once, in canonical order, tagged with a stable source index.
    spans: list[dict] = []
    for source_index, (version, document) in enumerate(sources):
        fragments = list(
            db.scalars(
                select(SourceFragment).where(
                    SourceFragment.source_version_id == version.source_version_id
                )
            )
        )
        fragments.sort(key=lambda f: f.ordinal)
        for fragment in fragments:
            ftext = fragment.normalized_text
            for start, end in _spans(ftext):
                quote = ftext[start:end]
                spans.append(
                    {
                        "source_index": source_index,
                        "version": version,
                        "document": document,
                        "fragment": fragment,
                        "start": start,
                        "end": end,
                        "quote": quote,
                        "terms": content_terms(quote),
                    }
                )

    candidates: list[CandidateSpec] = []
    for requirement in requirements:
        req_terms = content_terms(f"{requirement.title} {requirement.description}")
        if not req_terms:
            continue
        scored: list[tuple] = []
        for span in spans:
            overlap = req_terms & span["terms"]
            if not overlap:
                continue  # require >= 1 non-stopword token overlap
            scored.append(
                (
                    float(len(overlap)),
                    span["source_index"],
                    span["fragment"].ordinal,
                    span["start"],
                    span,
                )
            )
        # Rank: score desc, then canonical (source_index, ordinal, span start).
        scored.sort(key=lambda r: (-r[0], r[1], r[2], r[3]))
        seen: set[str] = set()
        taken = 0
        for score, _si, _ord, _start, span in scored:
            quote = span["quote"]
            qhash = quote_hash(quote)
            if qhash in seen:
                continue
            seen.add(qhash)
            document = span["document"]
            version = span["version"]
            fragment = span["fragment"]
            candidates.append(
                CandidateSpec(
                    target_requirement_id=requirement.requirement_id,
                    fragment_id=fragment.fragment_id,
                    source_version_id=version.source_version_id,
                    source_id=(
                        document.source_id if document else version.source_document_id
                    ),
                    source_name=document.name if document else "",
                    source_type=document.type if document else "txt",
                    page=fragment.page,
                    section=fragment.section,
                    proposed_quote=quote,
                    quote_hash=qhash,
                    span_start_in_fragment=span["start"],
                    span_end_in_fragment=span["end"],
                    retrieval_score=score,
                )
            )
            taken += 1
            if taken >= max_per_requirement:
                break
    return candidates
