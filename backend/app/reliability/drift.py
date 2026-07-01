"""Semantic-drift detector (Milestone 9K, STEP 7).

Deterministic, sentence-level co-occurrence scan of draft (and, when available, persisted
A2/A3) text against the versioned drift patterns. Field-scoped findings (advisory warnings).
"""
from __future__ import annotations

from app.evidence.discovery import _spans
from app.evidence.tokenize import normalize_for_match
from app.reliability.gate import ReliabilityFindingSpec
from app.reliability.glossary import DRIFT_PATTERNS


def detect_drift(*, field_id: str, text: str) -> list[ReliabilityFindingSpec]:
    specs: list[ReliabilityFindingSpec] = []
    if not text:
        return specs
    seen: set[str] = set()
    # Sentence-level so an anchor and drift term must appear close together.
    sentences = [text[s:e] for s, e in _spans(text)] or [text]
    for sentence in sentences:
        norm = normalize_for_match(sentence)
        for code, description, anchors, drift_terms in DRIFT_PATTERNS:
            if code in seen:
                continue
            if any(a in norm for a in anchors) and any(d in norm for d in drift_terms):
                seen.add(code)
                specs.append(ReliabilityFindingSpec(
                    finding_code=f"reliability:drift:{code}:{field_id}",
                    severity="warning", description=description, field_id=field_id,
                    target_type="portal_field_draft", target_id=field_id,
                ))
    return specs
