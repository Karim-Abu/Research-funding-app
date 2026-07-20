"""Deterministic exact-quote verification (Milestone 5) = verify_evidence_quote.

Verifies that a candidate's exact normalized quote exists at its expected
position in the frozen normalized SourceVersion. Position-anchored (never a
global first-match, so identical recurring quotes are disambiguated), version-
and normalizer-locked. Only an exact_normalized candidate whose quote matches at
the expected offsets becomes ``exact_verified``. fuzzy/semantic/manual can never
become exact_verified; ``human_verified`` is never produced in M5.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisRun,
    EvidenceCandidate,
    RunSourceSnapshot,
    SourceFragment,
    SourceVersion,
)
from app.evidence.eligibility import validate_requirement_quote
from app.evidence.scope_policy import candidate_in_application_scope


@dataclass(frozen=True)
class VerificationOutcome:
    # unverified | exact_verified | rejected  (human_verified never produced)
    verification_status: str
    match_type: str  # exact_normalized | fuzzy | semantic | manual
    start_offset: int | None
    end_offset: int | None
    reason: str


def _run_normalizer_version(run: AnalysisRun) -> str | None:
    return (run.snapshot_versions or {}).get("normalizer_version")


def verify_candidate(
    db: Session, run: AnalysisRun, candidate: EvidenceCandidate
) -> VerificationOutcome:
    match_type = candidate.match_type
    # Only exact_normalized candidates are ever eligible for exact_verified.
    if match_type != "exact_normalized":
        return VerificationOutcome(
            "unverified", match_type, None, None, "non_exact_match_type"
        )

    allowed, scope_reason = candidate_in_application_scope(
        db,
        run,
        source_id=candidate.source_id,
        source_version_id=candidate.source_version_id,
    )
    if not allowed:
        return VerificationOutcome(
            "rejected",
            match_type,
            None,
            None,
            scope_reason or "application_scope_invalid",
        )

    # The source version must belong to this run's immutable snapshot.
    in_scope = db.scalar(
        select(RunSourceSnapshot.id).where(
            RunSourceSnapshot.run_id == run.run_id,
            RunSourceSnapshot.source_version_id == candidate.source_version_id,
        )
    )
    if in_scope is None:
        return VerificationOutcome(
            "rejected", match_type, None, None, "out_of_run_snapshot"
        )

    version = db.get(SourceVersion, candidate.source_version_id)
    fragment = db.get(SourceFragment, candidate.fragment_id)
    if version is None or fragment is None or version.normalized_text is None:
        return VerificationOutcome("rejected", match_type, None, None, "missing_source")
    if fragment.source_version_id != version.source_version_id:
        return VerificationOutcome(
            "rejected", match_type, None, None, "fragment_version_mismatch"
        )

    # Normalizer version lock.
    run_norm = _run_normalizer_version(run)
    if run_norm is not None and version.normalizer_version != run_norm:
        return VerificationOutcome(
            "rejected", match_type, None, None, "normalizer_version_mismatch"
        )

    # Validate the quote at its expected absolute position.
    start = fragment.start_offset + candidate.span_start_in_fragment
    end = fragment.start_offset + candidate.span_end_in_fragment
    text = version.normalized_text
    if not 0 <= start <= end <= len(text):
        return VerificationOutcome("unverified", match_type, None, None, "invalid_offsets")
    if text[start:end] != candidate.proposed_quote:
        return VerificationOutcome(
            "unverified", match_type, None, None, "quote_not_at_position"
        )

    eligibility_reason = validate_requirement_quote(
        candidate.target_requirement_id, candidate.proposed_quote
    )
    if eligibility_reason is not None:
        return VerificationOutcome(
            "rejected", match_type, start, end, eligibility_reason
        )

    return VerificationOutcome(
        "exact_verified", "exact_normalized", start, end, "exact_position_match"
    )
