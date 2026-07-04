"""Deterministic evidence-sufficiency check (Milestone 9K, STEP 4).

Answers "does THIS evidence quote support THIS claim under defined criteria?" — a separate
question from "does an anchor exist?" (coverage). This is an **evidence sufficiency check**,
never a semantic proof: a supporting result means the source *appears to support the claim
under the defined lexical/quantitative criteria*, not that it is "verified as true". An
``exact_verified`` anchor NEVER auto-implies ``supports_claim``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.evidence.tokenize import content_terms, normalize_for_match
from app.reliability.extract import _LEXICONS

# Claim types that demand type-specific supporting terms in the evidence quote.
_TYPE_REQUIRED_TERMS = {
    "market": _LEXICONS["market"],
    "innovation": _LEXICONS["innovation"],
    "partner_fit": _LEXICONS["partner_fit"],
}
_NUMBER_TOKEN_RE = re.compile(r"\d[\d.,]*")

SUPPORTS = "supports_claim"
WEAKLY = "weakly_supports_claim"
DOES_NOT = "does_not_support_claim"
INSUFFICIENT = "insufficient_evidence"
NEEDS_REVIEW = "needs_human_review"

# Rank for choosing the strongest sufficiency across several evidence quotes.
_RANK = {DOES_NOT: 0, NEEDS_REVIEW: 1, INSUFFICIENT: 2, WEAKLY: 3, SUPPORTS: 4}


@dataclass(frozen=True)
class SufficiencyOutcome:
    status: str
    matched_terms: list[str]
    reason: str


def _numbers(text: str) -> set[str]:
    return {m.group(0).replace(",", ".").rstrip(".") for m in _NUMBER_TOKEN_RE.finditer(text)}


def _type_terms_present(claim_type: str, quote_terms: set[str], quote_norm: str) -> bool:
    lexicon = _TYPE_REQUIRED_TERMS.get(claim_type)
    if lexicon is None:
        return True  # no extra type requirement (technical/value/budget/requirement/generic)
    if quote_terms & lexicon:
        return True
    return any(" " in kw and kw in quote_norm for kw in lexicon)


def check_support(
    *, claim_text: str, claim_type: str, quantified: bool, quote: str
) -> SufficiencyOutcome:
    """Deterministic sufficiency of a single evidence ``quote`` for a claim. The caller has
    already ensured the quote exists verbatim, belongs to the same run/project, and targets
    the field — this only checks whether it *appears to support the claim under criteria*."""
    claim_terms = content_terms(claim_text)
    quote_terms = content_terms(quote)
    quote_norm = normalize_for_match(quote)
    matched = sorted(claim_terms & quote_terms)

    if not matched:
        return SufficiencyOutcome(DOES_NOT, [], "no_key_term_overlap")

    if quantified:
        # A quantified claim needs a matching number/measurable term in the evidence.
        if not (_numbers(claim_text) & _numbers(quote)):
            return SufficiencyOutcome(
                INSUFFICIENT, matched, "quantified_claim_no_matching_number"
            )

    type_ok = _type_terms_present(claim_type, quote_terms, quote_norm)
    if len(matched) >= 2 and type_ok:
        return SufficiencyOutcome(SUPPORTS, matched, "key_terms_and_type_terms_present")
    if not type_ok:
        # e.g. a market claim whose evidence has no market/customer/competitor terms.
        return SufficiencyOutcome(INSUFFICIENT, matched, "missing_type_specific_terms")
    # Some overlap but too generic to count as claim-specific support.
    return SufficiencyOutcome(WEAKLY, matched, "generic_partial_overlap")


def best_support(outcomes: list[SufficiencyOutcome]) -> SufficiencyOutcome:
    """The strongest sufficiency across several evidence quotes (empty → insufficient)."""
    if not outcomes:
        return SufficiencyOutcome(INSUFFICIENT, [], "no_evidence_quotes")
    return max(outcomes, key=lambda o: _RANK.get(o.status, 0))


def has_number_conflict(claim_text: str, quote: str) -> bool:
    """True when both carry numbers but none match — a contradiction signal for lineage."""
    cn, qn = _numbers(claim_text), _numbers(quote)
    return bool(cn) and bool(qn) and not (cn & qn)
