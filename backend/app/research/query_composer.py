"""Small deterministic composer for public-safe research queries."""
from __future__ import annotations

import re

_EDGE_PUNCTUATION = ".,;:!?()[]{}\"'«»"


def compose_query(*parts: str | None) -> str:
    """Join non-empty parts while removing repeated words case-insensitively."""
    seen: set[str] = set()
    words: list[str] = []
    for part in parts:
        for word in re.sub(r"\s+", " ", part or "").strip().split(" "):
            if not word:
                continue
            key = word.strip(_EDGE_PUNCTUATION).casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            words.append(word)
    return " ".join(words)
