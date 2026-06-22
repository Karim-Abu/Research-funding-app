"""Deterministic, versioned text normalization.

Pipeline: NFKC → line endings → strip soft hyphens → conservative cross-line
dehyphenation → collapse intra-line whitespace (preserving paragraph
boundaries). Pure function of its input — same text always yields the same
output for a given NORMALIZER_VERSION.
"""
from __future__ import annotations

import re
import unicodedata

_SOFT_HYPHEN = "­"
# Lowercase letter classes (incl. common Latin-1 accented) for safe dehyphenation.
_DEHYPHEN = re.compile(r"([a-zà-öø-ÿ])-\n([a-zà-öø-ÿ])")
_INTRALINE_WS = re.compile(r"[ \t\f\v]+")
_TRAILING_WS = re.compile(r"[ \t]+\n")
_LEADING_WS = re.compile(r"\n[ \t]+")
_PARAGRAPHS = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(_SOFT_HYPHEN, "")
    # Conservative dehyphenation: only join lowercase-`-`\n-lowercase.
    text = _DEHYPHEN.sub(r"\1\2", text)
    text = _INTRALINE_WS.sub(" ", text)
    text = _TRAILING_WS.sub("\n", text)
    text = _LEADING_WS.sub("\n", text)
    text = _PARAGRAPHS.sub("\n\n", text)
    return text.strip()
