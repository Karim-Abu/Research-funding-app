"""Independent RUN 3C claim extraction and deterministic grounding checks."""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field


_SENTENCE_RE = re.compile(r"[^.!?\n]+(?:[.!?]|$)", re.UNICODE)
_NUMBER_RE = re.compile(
    r"(?<![\w.])(?:CHF|EUR|USD)\s*\d+(?:[.,]\d+)?(?:\s*(?:Mio\.?|Mrd\.?))?(?!\w)|"
    r"(?<![\w.])TRL\s*\d+(?!\w)|"
    r"(?<![\w.])\d{1,2}[./-]\d{1,2}[./-](?:19|20)\d{2}(?!\w)|"
    r"(?<![\w.])\d{1,2}\.\s*(?:Januar|Februar|M(?:ae|ä)rz|April|Mai|Juni|"
    r"Juli|August|September|Oktober|November|Dezember)\s+(?:19|20)\d{2}(?!\w)|"
    r"(?<![\w.])(?:19|20)\d{2}(?!\w)|"
    r"(?<![\w.])\d+(?:[.,]\d+)?\s*(?:%|Prozent|CHF|EUR|USD|Mio\.?|Mrd\.?|"
    r"Monate?|Jahre?|Tage?|Stunden?|FTE)(?!\w)",
    re.IGNORECASE | re.UNICODE,
)
_ORG_RE = re.compile(
    r"\b(?:[A-ZÄÖÜ][\wÄÖÜäöüß&.-]+(?:\s+|\s*&\s*)){0,4}"
    r"[A-ZÄÖÜ][\wÄÖÜäöüß&.-]+\s+(?:AG|GmbH|SA|Sàrl|Inc\.?|Ltd\.?|Universität|"
    r"Hochschule|Institut)\b",
    re.UNICODE,
)
_NAMED_PRODUCT_RE = re.compile(
    r"\b(?:Produkt|Plattform|Software|Loesung|Lösung|Technologie)\s+"
    r"([A-ZÄÖÜ][\wÄÖÜäöüß&.-]+(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß&.-]+){0,3})",
    re.UNICODE,
)
_ACRONYM_ENTITY_RE = re.compile(
    r"\b(?:[A-ZÄÖÜ]{2,8}(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß.-]+){0,2}|"
    r"[A-ZÄÖÜ][a-zäöüß]+[A-ZÄÖÜ][\wÄÖÜäöüß-]*)\b",
    re.UNICODE,
)
_ENTITY_STOPWORDS = frozenset({
    "CHF", "EUR", "USD", "FTE", "TRL", "DACH", "B2B", "AG", "SA", "GmbH",
    "Sàrl", "Inc", "Ltd", "KI", "AI",
})
_SPECIFIC_ASSERTION_RE = re.compile(
    r"\b(?:Marktvolumen|Marktanteil|Wachstumsrate|patentiert|zertifiziert|"
    r"gesetzlich vorgeschrieben|gemäss (?:dem|der)|Stand der Technik ist|"
    r"weltweit führend|einzig(?:e|artig)|klinisch belegt)\b",
    re.IGNORECASE | re.UNICODE,
)


def normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


@dataclass(frozen=True, slots=True)
class ExtractedClaim:
    sentence: str
    claim_type: str
    value: str


@dataclass(slots=True)
class GroundingResult:
    claims: list[ExtractedClaim] = field(default_factory=list)
    unsupported_critical: list[ExtractedClaim] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    anchor_ids_by_claim: dict[str, list[str]] = field(default_factory=dict)


def extract_concrete_claims(text: str) -> list[ExtractedClaim]:
    """Extract concrete claims without relying on a provider-supplied claim map."""
    claims: list[ExtractedClaim] = []
    seen: set[tuple[str, str]] = set()
    for match in _SENTENCE_RE.finditer(text or ""):
        sentence = match.group(0).strip()
        if not sentence:
            continue
        for value in _NUMBER_RE.findall(sentence):
            key = ("number", normalize(value))
            if key not in seen:
                claims.append(ExtractedClaim(sentence, "number", value.strip()))
                seen.add(key)
        for value in _ORG_RE.findall(sentence):
            value = re.sub(r"^(?:Der|Die|Das|The)\s+", "", value).strip()
            key = ("organization", normalize(value))
            if key not in seen:
                claims.append(ExtractedClaim(sentence, "organization", value.strip()))
                seen.add(key)
        for value in _NAMED_PRODUCT_RE.findall(sentence):
            key = ("product", normalize(value))
            if key not in seen:
                claims.append(ExtractedClaim(sentence, "product", value.strip()))
                seen.add(key)
        for value in _ACRONYM_ENTITY_RE.findall(sentence):
            if value in _ENTITY_STOPWORDS or ("product", normalize(value)) in seen:
                continue
            key = ("organization", normalize(value))
            if key not in seen:
                claims.append(ExtractedClaim(sentence, "organization", value.strip()))
                seen.add(key)
        if _SPECIFIC_ASSERTION_RE.search(sentence):
            key = ("external_fact", normalize(sentence))
            if key not in seen:
                claims.append(ExtractedClaim(sentence, "external_fact", sentence))
                seen.add(key)
    return claims


def validate_grounding(
    suggestion_text: str,
    *,
    original_text: str,
    structured_project_data: dict,
    anchors: list[dict],
) -> GroundingResult:
    """Ground each independently extracted concrete claim.

    A value already present in applicant text or frozen structured input is
    allowed.  Otherwise it must occur in one of the selected anchor quotes.
    The function never treats snippets, provider declarations or review text
    as grounding material.
    """
    result = GroundingResult(claims=extract_concrete_claims(suggestion_text))
    applicant_corpus = normalize(
        f"{original_text}\n{json.dumps(structured_project_data, ensure_ascii=False, sort_keys=True)}"
    )
    anchor_corpus = {
        str(anchor["anchor_id"]): normalize(str(anchor.get("quote") or ""))
        for anchor in anchors
    }
    for claim in result.claims:
        needle = normalize(claim.value)
        if needle and needle in applicant_corpus:
            result.anchor_ids_by_claim[claim.value] = []
            continue
        matching = sorted(
            anchor_id for anchor_id, corpus in anchor_corpus.items()
            if needle and needle in corpus
        )
        if matching:
            result.anchor_ids_by_claim[claim.value] = matching
            continue
        result.unsupported_critical.append(claim)
    if result.unsupported_critical:
        result.warnings.append("unsupported_concrete_claim")
    return result
