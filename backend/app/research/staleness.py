"""Single staleness propagation path for versioned public sources."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    EvidenceAnchor, EvidenceLink, MarketComparison, ResearchResult, SourceVersion,
)


def mark_source_dependents_stale(
    db: Session, *, source_id: str, reason: str
) -> None:
    version_ids = set(db.scalars(select(SourceVersion.source_version_id).where(
        SourceVersion.source_document_id == source_id
    )))
    if version_ids:
        for comparison in db.scalars(select(MarketComparison)):
            if version_ids.intersection(comparison.source_version_ids or []):
                comparison.status = "stale"
                comparison.stale_reason = reason
        anchor_ids = list(db.scalars(select(EvidenceAnchor.anchor_id).where(
            EvidenceAnchor.source_version_id.in_(version_ids),
            EvidenceAnchor.scope == "external",
        )))
        if anchor_ids:
            for link in db.scalars(select(EvidenceLink).where(
                EvidenceLink.anchor_id.in_(anchor_ids), EvidenceLink.status == "active"
            )):
                link.status = "stale"
    for result in db.scalars(select(ResearchResult).where(
        ResearchResult.source_document_id == source_id,
        ResearchResult.eligibility_status == "verified_against_official_source",
    )):
        result.eligibility_status = "stale"
