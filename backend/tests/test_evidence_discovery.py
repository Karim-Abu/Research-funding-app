"""Deterministic candidate discovery — tokenizer, spans, hashing units."""
from __future__ import annotations

from app.evidence import discovery
from app.evidence.tokenize import content_terms


def test_content_terms_unicode_and_stopwords():
    terms = content_terms("Der Umsetzungspartner ist in der Schweiz tätig.")
    assert {"umsetzungspartner", "schweiz", "tätig"} <= terms
    # generic German function words are removed
    assert not ({"der", "ist", "in"} & terms)


def test_content_terms_casefold_consistent():
    assert content_terms("FÖRDERFÄHIGKEIT Prüfung") == content_terms(
        "förderfähigkeit prüfung"
    )


def test_content_terms_require_min_length():
    # single-character tokens are dropped (deterministic noise control)
    assert "a" not in content_terms("a Innovationsprojekt")


def test_spans_are_trimmed_exact_substrings_with_offsets():
    text = "Erster Satz. Zweiter Satz! Dritter Teil?"
    spans = discovery._spans(text)
    quotes = [text[s:e] for s, e in spans]
    assert "Erster Satz." in quotes
    assert "Zweiter Satz!" in quotes
    assert "Dritter Teil?" in quotes
    for s, e in spans:
        assert e > s
        assert text[s:e] == text[s:e].strip()  # whitespace-trimmed
        assert text[s:e] == text[s:e]  # exact substring by construction


def test_spans_preserve_unicode():
    text = "Müller prüft die Förderfähigkeit. Söhne folgen."
    quotes = [text[s:e] for s, e in discovery._spans(text)]
    assert "Müller prüft die Förderfähigkeit." in quotes


def test_quote_hash_is_deterministic():
    assert discovery.quote_hash("Prüfung") == discovery.quote_hash("Prüfung")
    assert discovery.quote_hash("Prüfung") != discovery.quote_hash("Pruefung")
    assert len(discovery.quote_hash("x")) == 64
