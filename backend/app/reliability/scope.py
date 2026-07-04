"""Reliability source-scope hashing (Milestone 9K, corr 2/11).

The reliability ``source_scope_hash`` binds a pass to the inputs it evaluated: the current
draft versions, the evidence links/anchors, the frozen source versions, the MarketComparison
version (if any) and the **pre-existing** review signals (deterministic / A3 / human findings).
It deliberately **excludes** this pass's own ``M9K.reliability_assurance`` findings so a pass
never immediately staleifies its own summary. When any scoped input later changes, the hash
changes and the summary is stale.
"""
from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisRun,
    EvidenceAnchor,
    EvidenceLink,
    MarketComparison,
    PortalFieldDraft,
    ReviewFinding,
    RunSourceSnapshot,
)
from app.reliability import RELIABILITY_PROFILE_ID


def compute_reliability_scope_hash(db: Session, run: AnalysisRun) -> str:
    parts: list[str] = [f"run:{run.run_id}"]

    for draft in db.scalars(
        select(PortalFieldDraft)
        .where(PortalFieldDraft.run_id == run.run_id)
        .order_by(PortalFieldDraft.field_id.asc())
    ):
        parts.append(f"draft:{draft.field_id}:{draft.current_version_id}")

    for link in db.scalars(
        select(EvidenceLink)
        .where(EvidenceLink.run_id == run.run_id)
        .order_by(EvidenceLink.evidence_link_id.asc())
    ):
        parts.append(f"link:{link.evidence_link_id}:{link.anchor_id}:{link.status}")

    for anchor in db.scalars(
        select(EvidenceAnchor)
        .where(EvidenceAnchor.run_id == run.run_id)
        .order_by(EvidenceAnchor.anchor_id.asc())
    ):
        parts.append(f"anchor:{anchor.anchor_id}:{anchor.quote_hash}:{anchor.verification_status}")

    for snap in db.scalars(
        select(RunSourceSnapshot)
        .where(RunSourceSnapshot.run_id == run.run_id)
        .order_by(RunSourceSnapshot.source_version_id.asc())
    ):
        parts.append(f"src:{snap.source_version_id}")

    # Pre-existing review signals only — NEVER this pass's own M9K findings (corr 11).
    for finding in db.scalars(
        select(ReviewFinding)
        .where(
            ReviewFinding.run_id == run.run_id,
            ReviewFinding.profile_id != RELIABILITY_PROFILE_ID,
        )
        .order_by(ReviewFinding.finding_id.asc())
    ):
        parts.append(f"finding:{finding.finding_id}:{finding.status}")

    comparison = db.scalar(
        select(MarketComparison)
        .where(MarketComparison.project_id == run.project_id)
        .order_by(MarketComparison.created_at.desc())
    )
    if comparison is not None:
        parts.append(f"market:{comparison.comparison_id}:{comparison.comparison_version}")

    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
