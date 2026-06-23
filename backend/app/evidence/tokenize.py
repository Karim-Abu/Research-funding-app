"""Deterministic Unicode-aware tokenization + versioned stopwords (M5).

Purely mechanical: NFKC + casefold + Unicode word tokens, minus a small,
explicit, *versioned* list of generic German and English function words. No
domain synonyms, no stemming, no LLM. Used for both requirement search-term
derivation and source-span scoring so the two sides match consistently.
"""
from __future__ import annotations

import re
import unicodedata

TOKENIZER_VERSION = "evidence-tokenizer-1"

# Generic German function words (articles, pronouns, prepositions, conjunctions,
# auxiliaries). Deliberately small and explicit — NOT domain vocabulary.
_GERMAN_STOPWORDS = frozenset(
    {
        "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "eines",
        "einem", "einen", "und", "oder", "aber", "sondern", "auch", "sowie", "bzw",
        "ist", "sind", "war", "waren", "wird", "werden", "wurde", "wurden", "sein",
        "seine", "seiner", "haben", "hat", "hatte", "muss", "müssen", "kann",
        "können", "soll", "sollen", "darf", "im", "in", "an", "auf", "aus", "bei",
        "mit", "nach", "von", "vor", "zu", "zur", "zum", "über", "unter", "durch",
        "für", "gegen", "ohne", "um", "als", "wie", "bis", "je", "nicht", "kein",
        "keine", "keiner", "nur", "mehr", "sehr", "schon", "noch", "dann", "also",
        "dass", "weil", "wenn", "damit", "ihr", "ihre", "ihrer", "dieser", "diese",
        "dieses", "diesem", "diesen", "welche", "welcher", "welches", "am", "beim",
        "vom", "ins", "es", "sie", "er", "wir", "man", "den", "dem",
    }
)
# Generic English function words.
_ENGLISH_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "for",
        "with", "by", "from", "as", "is", "are", "was", "were", "be", "been",
        "being", "this", "that", "these", "those", "it", "its", "they", "their",
        "which", "who", "whom", "not", "no", "only", "also", "more", "very",
        "such", "than", "then", "so", "if", "when", "because", "must", "may",
        "can", "should", "shall", "will", "would",
    }
)
STOPWORDS = _GERMAN_STOPWORDS | _ENGLISH_STOPWORDS

_WORD_RE = re.compile(r"\w+", re.UNICODE)
_MIN_TOKEN_LEN = 2


def normalize_for_match(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def tokens(text: str) -> list[str]:
    """Ordered Unicode word tokens (NFKC + casefold). Deterministic."""
    return _WORD_RE.findall(normalize_for_match(text))


def content_terms(text: str) -> set[str]:
    """Distinct non-stopword tokens of length >= 2 — the matchable vocabulary."""
    return {t for t in tokens(text) if len(t) >= _MIN_TOKEN_LEN and t not in STOPWORDS}
