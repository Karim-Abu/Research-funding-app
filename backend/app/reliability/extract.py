"""Deterministic claim extraction (Milestone 9K, STEP 2/3).

Segment a DraftVersion's text into sentences, drop stylistic filler, and classify each
claim-like statement by type + strength, marking whether it requires evidence. Conservative:
if in doubt, ``requires_evidence=True``. No LLM, no provider. ``claim_text`` is carried only
for the internal table + authenticated UI — never for audit/logs/export.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.evidence.discovery import _spans
from app.evidence.tokenize import content_terms, normalize_for_match

# Versioned keyword lexicons (normalized, casefolded). Deliberately small + explicit.
_LEXICONS: dict[str, frozenset[str]] = {
    "market": frozenset({
        "markt", "market", "kunde", "kunden", "customer", "customers", "kundensegment",
        "wettbewerb", "wettbewerber", "competitor", "competitors", "konkurrenz",
        "nachfrage", "demand", "traction", "marktanteil", "market share", "zahlungsbereit",
        "umsatz", "revenue", "geschäftsmodell", "business model",
    }),
    "innovation": frozenset({
        "innovation", "innovativ", "neuartig", "novel", "novelty", "erstmals",
        "state of the art", "sota", "stand der technik", "differenzierung",
        "differentiation", "durchbruch", "breakthrough", "einzigartig", "unique",
        "weltweit erste", "patent",
    }),
    "technical": frozenset({
        "technisch", "technical", "prototyp", "prototype", "algorithmus", "algorithm",
        "architektur", "architecture", "verfahren", "methode", "method", "sensor",
        "modell", "genauigkeit", "accuracy", "wirkungsgrad", "leistung", "performance",
        "trl", "machbarkeit", "feasibility",
    }),
    "partner_fit": frozenset({
        "partner", "umsetzungspartner", "implementation partner", "expertise",
        "erfahrung", "track record", "kompetenz", "competence", "referenz", "reference",
        "team", "personal", "qualifikation",
    }),
    "value_creation": frozenset({
        "wertschöpfung", "value creation", "arbeitsplätze", "jobs", "standort",
        "schweiz", "volkswirtschaftlich", "economic", "nutzen", "benefit", "impact",
        "skalierung", "scaling", "wachstum", "growth",
    }),
    "budget": frozenset({
        "budget", "kosten", "cost", "chf", "eur", "usd", "finanzierung", "funding",
        "investition", "investment", "franken",
    }),
    "requirement": frozenset({
        "anforderung", "requirement", "förderfähig", "eligibility", "eligible",
        "kriterium", "criterion", "innosuisse", "vorgabe",
    }),
}
# Ordered so a sentence is classified by its first strongly-matching type.
_TYPE_ORDER = (
    "budget", "market", "innovation", "partner_fit", "value_creation", "technical",
    "requirement",
)

_STRONG_MARKERS = frozenset({
    "einzigartig", "unique", "erstmals", "weltweit", "führend", "leading", "beste",
    "best", "bewiesen", "proven", "garantiert", "guaranteed", "immer", "always",
    "erste", "first", "revolutionär", "revolutionary", "deutlich", "signifikant",
    "significantly",
})
_HEDGE_MARKERS = frozenset({
    "könnte", "koennte", "möglicherweise", "moeglicherweise", "eventuell", "vielleicht",
    "geplant", "planned", "voraussichtlich", "potenziell", "potentially", "may",
    "might", "could", "soll", "angestrebt", "ziel ist",
})
_NUMBER_RE = re.compile(r"\d")
_WORD_RE = re.compile(r"\w+", re.UNICODE)
_MIN_CLAIM_TERMS = 2


@dataclass(frozen=True)
class ExtractedClaim:
    claim_id: str
    field_id: str
    draft_id: str
    draft_version_id: str
    start_char: int
    end_char: int
    claim_text: str
    claim_type: str
    strength: str
    requires_evidence: bool
    source_text_hash: str
    extraction_method: str = "deterministic_sentence_rule"


def _source_text_hash(text: str) -> str:
    return hashlib.sha256(normalize_for_match(text).encode("utf-8")).hexdigest()


def _claim_id(run_id: str, draft_version_id: str, field_id: str, start: int, end: int,
              text_hash: str) -> str:
    key = f"{run_id}|{draft_version_id}|{field_id}|{start}|{end}|{text_hash}"
    return "clm-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def _classify_type(norm: str, terms: set[str]) -> str:
    has_number = bool(_NUMBER_RE.search(norm))
    for claim_type in _TYPE_ORDER:
        lexicon = _LEXICONS[claim_type]
        # single-token overlap OR a multi-word phrase substring match
        if terms & lexicon:
            return claim_type
        if any(" " in kw and kw in norm for kw in lexicon):
            return claim_type
    if has_number:
        return "budget" if any(c in norm for c in ("chf", "eur", "franken", "%")) else "technical"
    return "generic"


def _classify_strength(norm: str, terms: set[str]) -> str:
    if terms & _HEDGE_MARKERS or any(" " in m and m in norm for m in _HEDGE_MARKERS):
        return "weak"
    if terms & _STRONG_MARKERS or _NUMBER_RE.search(norm):
        return "strong"
    return "moderate"


def is_quantified(claim: ExtractedClaim) -> bool:
    return bool(_NUMBER_RE.search(claim.claim_text))


def extract_claims(
    *, run_id: str, draft_id: str, draft_version_id: str, field_id: str, text: str
) -> list[ExtractedClaim]:
    """Deterministic sentence-level claim extraction over ``text`` (a DraftVersion.text)."""
    claims: list[ExtractedClaim] = []
    seen_ids: set[str] = set()
    for start, end in _spans(text or ""):
        sentence = text[start:end].strip()
        if not sentence:
            continue
        terms = content_terms(sentence)
        # Stylistic filler: too few content terms to be a claim.
        if len(terms) < _MIN_CLAIM_TERMS:
            continue
        norm = normalize_for_match(sentence)
        claim_type = _classify_type(norm, terms)
        strength = _classify_strength(norm, terms)
        has_number = bool(_NUMBER_RE.search(norm))
        # Conservative: everything non-generic requires evidence; generic requires it only
        # when it makes a strong/quantified assertion. If in doubt → True.
        requires_evidence = (
            claim_type != "generic" or has_number or strength == "strong"
        )
        text_hash = _source_text_hash(sentence)
        claim_id = _claim_id(run_id, draft_version_id, field_id, start, end, text_hash)
        if claim_id in seen_ids:
            continue
        seen_ids.add(claim_id)
        claims.append(ExtractedClaim(
            claim_id=claim_id, field_id=field_id, draft_id=draft_id,
            draft_version_id=draft_version_id, start_char=start, end_char=end,
            claim_text=sentence, claim_type=claim_type, strength=strength,
            requires_evidence=requires_evidence, source_text_hash=text_hash,
        ))
    return claims
