"""Canonical character count (Milestone 6).

The single source of truth for character counting, shared in spirit with the
frontend (`[...text].length`). Counts Unicode code points — Python ``len(str)``
counts code points, matching the JS code-point iterator for all characters
(including astral). Never trims or rewrites text.
"""
from __future__ import annotations


def char_count(text: str) -> int:
    return len(text)


def within_limit(text: str, character_limit: int | None) -> bool:
    """True when the text satisfies the contract character limit (null = unlimited)."""
    if character_limit is None:
        return True
    return char_count(text) <= character_limit
