"""Deterministic, read-time market judgment (no persistence, no new endpoints).

This module is the single source of truth for the three analytical views layered
on top of a persisted comparison: the market picture (Marktbild), the solution
landscape (Lösungslandschaft) and the overall competition judgment (Gesamturteil).

Hard rules encoded here:
- Market statistics (market_size_claim / customer_problem) are never solution
  candidates — they belong to the market picture only.
- An exact source quote (confidence_label == "source_backed") is evidence that a
  passage exists, NOT a confirmed claim. A differentiator counts as *evidenced*
  only after human confirmation (support_status == "supports").
- ``not_checked`` / ``unreviewed`` is treated as open/uncertain, never as
  "not present" or "not supported".
- No global-nonexistence, uniqueness, no-competition, patent/FTO or percentage
  statements are ever produced; the fixed disallowed set below is always present.
"""
from __future__ import annotations

from app.contracts.market import (
    CandidateType,
    CompetitionJudgment,
    MarketComparison as MarketComparisonContract,
    MarketComparisonItem as ItemContract,
    MarketPicture,
    MarketPicturePoint,
    SolutionLandscape,
    SolutionLandscapeCandidate,
)

# Legacy item category -> analytical candidate type. Market/customer-problem/
# unknown deliberately map to None (they are market picture, not candidates).
_CANDIDATE_TYPE_MAP: dict[str, CandidateType] = {
    "competitor": "direct_competitor",
    "alternative_solution": "adjacent_solution",
    "reference_solution": "reference_infrastructure",
    "incumbent_process": "manual_or_internal_alternative",
    "substitute": "substitute",
}
_OPEN_SOURCE_HINTS = ("open source", "open-source", "quelloffen", "github", "gitlab")

# A direct competitor is only called a functional equivalent when it verifiably
# overlaps on at least this many project-relevant functions. Documented, tunable.
_DIRECT_EQUIVALENT_MIN_OVERLAPS = 2

# Fixed overclaim guard. Always returned, in every judgment status, so the UI can
# both block insertion of these and show the user what must never be claimed.
DISALLOWED_FORMULATIONS: list[str] = [
    "Es existiert keine solche Lösung.",
    "Unsere Lösung ist weltweit einzigartig.",
    "Es gibt keine Konkurrenz.",
    "Es gibt keine vergleichbaren Anbieter.",
    "Diese Kombination ist patentierbar.",
    "Freedom to Operate ist gegeben.",
    "Belegt durch eine lückenhafte Quelle.",
]

_SCOPE_PREFIX = "Im definierten Suchumfang"
_NO_EQUIVALENT_STATEMENT = (
    f"{_SCOPE_PREFIX} wurden keine öffentlich dokumentierten Lösungen identifiziert, "
    "welche sämtliche untersuchten Funktionen in derselben Kombination anbieten. "
    "Einzelne Kernfunktionen werden jedoch bereits von bestehenden Lösungen abgedeckt."
)


def candidate_type_for(item: ItemContract) -> CandidateType | None:
    mapped = _CANDIDATE_TYPE_MAP.get(item.category)
    if mapped is None:
        return None
    haystack = f"{item.name} {item.offering_summary or ''} {item.description or ''}".lower()
    if any(hint in haystack for hint in _OPEN_SOURCE_HINTS):
        return "open_source_solution"
    return mapped


def overlaps_for(item: ItemContract) -> list[str]:
    """Project-relevant functions the candidate covers (from verified extraction)."""
    seen: list[str] = []
    for function in item.relevant_functions or []:
        cleaned = (function or "").strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _sentences(text: str | None) -> list[str]:
    if not text:
        return []
    parts = [p.strip() for p in text.replace("\n", " ").split(".")]
    return [p if p.endswith((".", "!", "?")) else f"{p}." for p in parts if len(p) > 3]


def split_differentiators(item: ItemContract) -> tuple[list[str], list[str]]:
    """Return (evidenced, plausible_but_unverified) differentiators.

    Evidenced requires a verified quote AND human confirmation (supports).
    Unreviewed/partial stays plausible-but-unverified; does_not_support is dropped
    (never surfaced as a differentiator).
    """
    if item.support_status == "does_not_support":
        return [], []
    sentences = _sentences(item.differentiation_relevance)
    if not sentences:
        return [], []
    evidenced = item.confidence_label == "source_backed" and item.support_status == "supports"
    return (sentences, []) if evidenced else ([], sentences)


def _is_solution_candidate(item: ItemContract) -> bool:
    return candidate_type_for(item) is not None


def build_market_picture(
    items: list[ItemContract], comparison: MarketComparisonContract
) -> MarketPicture:
    def _points(category: str) -> list[MarketPicturePoint]:
        out: list[MarketPicturePoint] = []
        seen: set[str] = set()
        for item in items:
            if item.category != category or item.confidence_label != "source_backed":
                continue
            if item.name in seen:
                continue
            seen.add(item.name)
            out.append(MarketPicturePoint(
                label=item.name,
                value=item.description or "Aus öffentlicher Quelle (zu prüfen).",
            ))
        return out

    segments: list[MarketPicturePoint] = []
    seen_segments: set[str] = set()
    swiss: list[MarketPicturePoint] = []
    seen_swiss: set[str] = set()
    for item in items:
        if item.confidence_label != "source_backed" or not _is_solution_candidate(item):
            continue
        segment = (item.target_customer_segment or "").strip()
        if segment and segment.lower() not in seen_segments:
            seen_segments.add(segment.lower())
            segments.append(MarketPicturePoint(label=item.name, value=segment))
        relevance = (item.swiss_relevance or "").strip()
        if relevance and relevance.lower() not in seen_swiss:
            seen_swiss.add(relevance.lower())
            swiss.append(MarketPicturePoint(label=item.name, value=relevance))

    size = _points("market_size_claim")
    problems = _points("customer_problem")
    return MarketPicture(
        size_and_growth=size,
        segments=segments,
        trends=[],
        demand_indicators=size + problems,
        swiss_relevance=swiss,
        gaps=list(comparison.research_gaps or []),
    )


def build_solution_landscape(
    items: list[ItemContract], *, scope_ok: bool
) -> SolutionLandscape:
    candidates: list[SolutionLandscapeCandidate] = []
    counts: dict[CandidateType, int] = {}
    for item in items:
        ctype = candidate_type_for(item)
        if ctype is None:
            continue
        counts[ctype] = counts.get(ctype, 0) + 1
        evidenced, unverified = split_differentiators(item)
        candidates.append(SolutionLandscapeCandidate(
            item_id=item.item_id,
            name=item.name,
            candidate_type=ctype,
            description=item.description,
            target_customer_segment=item.target_customer_segment,
            offering_summary=item.offering_summary,
            strengths=item.strengths,
            weaknesses=item.weaknesses,
            differentiation_relevance=item.differentiation_relevance,
            relation_to_project=item.relation_to_project,
            relevant_functions=list(item.relevant_functions or []),
            overlaps=overlaps_for(item),
            evidencing_differentiators=evidenced,
            unverified_differentiators=unverified,
            source_document_ids=list(item.source_document_ids or []),
            evidence_quotes=list(item.evidence_quotes or []),
            status=item.status,
            confidence_label=item.confidence_label,
            support_status=item.support_status,
            source_scope_ok=scope_ok,
            allowed_formulations=allowed_item_formulations(item),
            disallowed_formulations=list(DISALLOWED_FORMULATIONS),
        ))
    return SolutionLandscape(candidates=candidates, candidate_count_by_type=counts)


def allowed_item_formulations(item: ItemContract) -> list[str]:
    """Only scope-qualified, evidence-backed differentiator sentences (may be empty)."""
    evidenced, _ = split_differentiators(item)
    return [f"{_SCOPE_PREFIX}: Belegte Differenzierung gegenüber {item.name}: {s}" for s in evidenced]


def _is_evidenced_candidate(candidate: SolutionLandscapeCandidate) -> bool:
    return candidate.confidence_label == "source_backed"


def build_competition_judgment(
    comparison: MarketComparisonContract,
    items: list[ItemContract],
    landscape: SolutionLandscape,
    *,
    scope_stale: bool,
) -> CompetitionJudgment:
    candidates = landscape.candidates
    evidenced_candidates = [c for c in candidates if _is_evidenced_candidate(c)]
    relevant_candidate_count = len(candidates)

    key_overlaps: list[str] = []
    for candidate in evidenced_candidates:
        for overlap in candidate.overlaps:
            if overlap not in key_overlaps:
                key_overlaps.append(overlap)

    evidenced_diffs: list[str] = []
    plausible_diffs: list[str] = []
    for candidate in candidates:
        evidenced_diffs.extend(candidate.evidencing_differentiators)
        plausible_diffs.extend(candidate.unverified_differentiators)

    open_gaps: list[str] = list(comparison.research_gaps or [])
    for candidate in candidates:
        if candidate.confidence_label == "source_backed" and candidate.support_status != "supports":
            open_gaps.append(
                f"{candidate.name}: Textstelle gefunden, inhaltlich noch nicht bestätigt."
            )
        elif candidate.confidence_label != "source_backed":
            open_gaps.append(f"{candidate.name}: noch nicht ausreichend belegt.")

    source_count = len(comparison.source_version_ids or [])
    scope_summary = (
        f"{_SCOPE_PREFIX}: {source_count} geprüfte öffentliche "
        f"{'Quelle' if source_count == 1 else 'Quellen'}, "
        f"{relevant_candidate_count} untersuchte Lösungskandidaten."
    )

    runtime_insufficient = comparison.status in (
        "draft", "limited", "insufficient_external_evidence", "failed"
    )
    direct = next(
        (
            c for c in evidenced_candidates
            if c.candidate_type == "direct_competitor"
            and c.relation_to_project in ("competing", "similar")
            and len(c.overlaps) >= _DIRECT_EQUIVALENT_MIN_OVERLAPS
        ),
        None,
    )
    similar = next(
        (
            c for c in evidenced_candidates
            if c.candidate_type in ("direct_competitor", "adjacent_solution") and c.overlaps
        ),
        None,
    )

    if runtime_insufficient or not evidenced_candidates:
        status = "insufficient_evidence"
        rationale = (
            "Die geprüfte Quellenlage reicht für eine belastbare Wettbewerbsaussage "
            "noch nicht aus."
        )
        allowed: list[str] = []
    elif direct is not None:
        status = "direct_equivalent_found"
        rationale = (
            f"{_SCOPE_PREFIX} wurde mit {direct.name} eine funktional weitgehend "
            "vergleichbare Lösung identifiziert."
        )
        allowed = [rationale]
    elif similar is not None:
        status = "similar_solutions_found"
        names = ", ".join(dict.fromkeys(c.name for c in evidenced_candidates if c.overlaps))
        rationale = (
            f"{_SCOPE_PREFIX} existieren ähnliche oder angrenzende Lösungen "
            f"({names}); eine vollständige Gleichwertigkeit wurde nicht belegt."
        )
        allowed = [rationale]
    else:
        status = "no_direct_equivalent_in_scope"
        rationale = _NO_EQUIVALENT_STATEMENT
        allowed = [_NO_EQUIVALENT_STATEMENT]

    if status != "insufficient_evidence":
        allowed.extend(evidenced_diffs)

    can_insert = status != "insufficient_evidence" and bool(allowed) and not scope_stale
    if scope_stale:
        open_gaps.insert(0, "Der Suchraum hat sich geändert — bitte den Vergleich neu erstellen.")

    return CompetitionJudgment(
        status=status,
        rationale=rationale,
        scope_summary=scope_summary,
        relevant_candidate_count=relevant_candidate_count,
        key_overlaps=key_overlaps,
        evidenced_differentiators=evidenced_diffs,
        plausible_unverified_differentiators=plausible_diffs,
        open_evidence_gaps=open_gaps,
        allowed_formulations=allowed,
        disallowed_formulations=list(DISALLOWED_FORMULATIONS),
        can_insert_into_application=can_insert,
    )
