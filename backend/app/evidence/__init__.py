"""Deterministic evidence baseline (Milestone 5).

Three clearly separated concepts, all deterministic and LLM-free:
  1. candidate discovery  — "which passages might be relevant?" (lexical)
  2. quote verification    — "does this exact quote exist in this frozen source?"
  3. target association    — "which requirement was this candidate generated for?"

Verification never claims relevance or sufficiency — only technical source
existence at an exact position in the frozen normalized source version.
"""
from app.evidence.discovery import (
    RETRIEVAL_ALGORITHM_VERSION,
    CandidateSpec,
    discover_candidates,
)
from app.evidence.verification import VerificationOutcome, verify_candidate

__all__ = [
    "RETRIEVAL_ALGORITHM_VERSION",
    "CandidateSpec",
    "discover_candidates",
    "VerificationOutcome",
    "verify_candidate",
]
