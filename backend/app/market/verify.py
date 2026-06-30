"""Standalone deterministic quote verification for market comparison (Milestone 9I-B).

Reuses the M5 exact-match discipline (``quote_hash`` + exact substring/position match
against the frozen normalized SourceVersion text) WITHOUT the run-scoped
``verify_candidate`` (which requires a RunSourceSnapshot). Produces a verified-quote
reference for a comparison item; it never creates EvidenceAnchors and only LINKS a
pre-existing anchor that already covers the exact same source/version/span/quote.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EvidenceAnchor, SourceFragment, SourceVersion
from app.evidence.discovery import quote_hash

VERIFICATION_METHOD = "deterministic_position_match"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def verify_quote(
    db: Session,
    *,
    fragment: SourceFragment,
    source_document_id: str,
    quote: str,
) -> dict | None:
    """Return a verified_quote_ref dict if ``quote`` occurs EXACTLY in the fragment's
    frozen normalized text, else None (the item is then not source-backed). Snippets and
    provider payloads are never accepted here — only imported, normalized source text."""
    candidate = (quote or "").strip()
    if not candidate:
        return None
    ftext = fragment.normalized_text or ""
    local = ftext.find(candidate)
    if local < 0:
        return None  # not an exact match → not evidence

    version = db.get(SourceVersion, fragment.source_version_id)
    if version is None or version.normalized_text is None:
        return None
    # Offsets relative to the SourceVersion normalized text (anchor coordinate system).
    start = fragment.start_offset + local
    end = start + len(candidate)
    if not 0 <= start <= end <= len(version.normalized_text):
        return None
    if version.normalized_text[start:end] != candidate:
        return None  # position guard (defensive)

    qhash = quote_hash(candidate)
    ref = {
        "source_document_id": source_document_id,
        "source_version_id": fragment.source_version_id,
        "fragment_id": fragment.fragment_id,
        "quote": candidate,
        "start_char": start,
        "end_char": end,
        "quote_hash": qhash,
        "normalizer_version": version.normalizer_version,
        "verification_method": VERIFICATION_METHOD,
        "verified_at": _now_iso(),
        "linked_evidence_anchor_id": _existing_anchor_id(
            db, fragment.source_version_id, start, end, qhash
        ),
    }
    return ref


def _existing_anchor_id(
    db: Session, source_version_id: str, start: int, end: int, qhash: str
) -> str | None:
    """Link an EvidenceAnchor ONLY if one already covers the exact same span+quote
    (created earlier by a deterministic analysis run). Never creates one."""
    return db.scalar(
        select(EvidenceAnchor.anchor_id).where(
            EvidenceAnchor.source_version_id == source_version_id,
            EvidenceAnchor.start_offset == start,
            EvidenceAnchor.end_offset == end,
            EvidenceAnchor.quote_hash == qhash,
            EvidenceAnchor.verification_status == "exact_verified",
        )
    )
