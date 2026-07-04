"""No-raw-logging helpers (Milestone 9J).

The system must never persist or log a raw D1/D2 web-research query (or the concrete
partner/project/budget terms a firewall removed). Recording already writes only hashes +
category metadata; these helpers are the defensive backstop + the test oracle:

  * ``assert_no_raw_query`` — fail-fast in dev/test if a raw query or sensitive term
    leaked into a detail payload; in production it degrades to a safe no-op (never breaks
    a request over a logging concern).
  * ``safe_detail`` — build an audit/control detail that carries only a hash + category
    metadata, never the raw text.
"""
from __future__ import annotations

import json

from app.config.settings import get_settings

# Terms shorter than this are ignored to avoid false positives on common substrings.
_MIN_TERM_LEN = 4


def serialize_detail(detail: object) -> str:
    if detail is None:
        return ""
    if isinstance(detail, str):
        return detail
    try:
        return json.dumps(detail, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(detail)


def detail_contains(detail: object, terms: object) -> bool:
    """True if any non-trivial term appears (case-insensitively) in the serialized detail.

    ``terms`` may be a string or an iterable of strings.
    """
    haystack = serialize_detail(detail).casefold()
    if not haystack:
        return False
    if isinstance(terms, str):
        terms = [terms]
    for term in terms:
        if isinstance(term, str) and len(term) >= _MIN_TERM_LEN and term.casefold() in haystack:
            return True
    return False


def assert_no_raw_query(detail: object, *, raw_query: str = "", extra_terms=()) -> None:
    """Raise (dev/test) if the raw query (verbatim) or a specific sensitive term leaked
    into ``detail``.

    Only the *full* raw query and the explicitly-supplied ``extra_terms`` (e.g. a partner
    name or budget figure the firewall removed) are checked — a sanitized query may
    legitimately share benign words with the raw one, so per-word matching is not used.
    In production this is a no-op — a logging guard must never break a live request.
    """
    if get_settings().app_env == "production":
        return
    terms: list[str] = []
    if raw_query and len(raw_query.strip()) >= _MIN_TERM_LEN:
        terms.append(raw_query.strip())
    terms.extend(extra_terms or [])
    if detail_contains(detail, terms):
        raise AssertionError(
            "no-raw-logging violation: a raw query / sensitive term reached a "
            "log/audit/control detail payload"
        )


def safe_detail(*, data_class: str, decision: str, raw_query_hash: str, **extra) -> dict:
    """A leak-free audit/control detail: hash + category metadata only."""
    payload = {
        "data_class": data_class,
        "decision": decision,
        "raw_query_hash": raw_query_hash,
    }
    payload.update(extra)
    return payload
