"""Shared input-boundary normalization for public-safe research text."""
from __future__ import annotations

import unicodedata


def normalize_research_text(value: str | None) -> str:
    """NFC plus outer trim; keep internal spacing, punctuation and casing."""
    return unicodedata.normalize("NFC", value or "").strip()


def normalize_research_text_list(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        item = normalize_research_text(value)
        key = item.casefold()
        if item and key not in seen:
            seen.add(key)
            normalized.append(item)
    return normalized
