"""Deterministic handling of untrusted public-page instructions.

This is a quarantine signal, not a correctness judgement. Matching content remains
stored as source material but is excluded from market/drafting context until a human
explicitly releases it.
"""
from __future__ import annotations

import hashlib
import re


_INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+(all\s+)?(previous|prior|system)\s+instructions?\b", re.I),
    re.compile(r"\b(reveal|print|return|exfiltrate)\b.{0,80}\b(secret|api[- ]?key|prompt|document)\b", re.I | re.S),
    re.compile(r"\b(system|developer)\s+prompt\b", re.I),
    re.compile(r"\b(call|use|invoke)\s+(the\s+)?(tool|function|browser|shell)\b", re.I),
    re.compile(r"\bupload\b.{0,80}\b(project|document|file|database)\b", re.I | re.S),
)


def scan_untrusted_text(text: str) -> tuple[str, str | None]:
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text or ""):
            return "quarantined", "prompt_injection_signal"
    return "passed", None


def similarity_hash(text: str) -> str:
    """Stable 64-bit SimHash. It only supports a possible-duplicate flag."""
    tokens = re.findall(r"\w+", (text or "").casefold(), flags=re.UNICODE)
    vector = [0] * 64
    for token in tokens:
        value = int.from_bytes(hashlib.sha256(token.encode("utf-8")).digest()[:8], "big")
        for bit in range(64):
            vector[bit] += 1 if value & (1 << bit) else -1
    result = sum(1 << bit for bit, weight in enumerate(vector) if weight >= 0)
    return f"{result:016x}"


def possible_duplicate(first: str | None, second: str | None, *, distance: int = 3) -> bool:
    if not first or not second:
        return False
    try:
        return (int(first, 16) ^ int(second, 16)).bit_count() <= distance
    except ValueError:
        return False
