"""Scope-bound reliability approval gating (Milestone 9K, corr 3/13).

A reliability blocker governs approval **only** when its target claim belongs to the
current, non-stale RunQualitySummary (i.e. the draft has not changed since the pass). A
stale summary contributes a non-blocking ``reliability_stale`` note instead, and a run that
never ran a reliability pass is unaffected. Imported by the review layer via lazy imports to
avoid an import cycle.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalysisRun, DraftClaim, ReviewFinding, RunQualitySummary
from app.reliability import RELIABILITY_PROFILE_ID
from app.reliability.scope import compute_reliability_scope_hash


def latest_summary(db: Session, run: AnalysisRun) -> RunQualitySummary | None:
    return db.scalar(
        select(RunQualitySummary)
        .where(RunQualitySummary.run_id == run.run_id)
        .order_by(RunQualitySummary.generated_at.desc())
    )


def current_summary(db: Session, run: AnalysisRun) -> RunQualitySummary | None:
    """The latest summary iff it is marked ``current`` AND its scope hash still matches the
    run's inputs now (draft unchanged since the pass)."""
    summary = latest_summary(db, run)
    if summary is None or summary.status != "current":
        return None
    if summary.source_scope_hash != compute_reliability_scope_hash(db, run):
        return None
    return summary


def is_stale(db: Session, run: AnalysisRun) -> bool:
    """A pass ran but its summary no longer reflects the current inputs."""
    return latest_summary(db, run) is not None and current_summary(db, run) is None


def reliability_blocker_reasons(
    db: Session, run: AnalysisRun, field_ids: set[str] | None = None
) -> list[str]:
    """Approval-blocking reasons from OPEN reliability blocker findings whose target claim
    belongs to the current non-stale summary (corr 13). Empty when no current summary."""
    summary = current_summary(db, run)
    if summary is None:
        return []
    reasons: list[str] = []
    findings = db.scalars(
        select(ReviewFinding).where(
            ReviewFinding.run_id == run.run_id,
            ReviewFinding.source == "agent",
            ReviewFinding.profile_id == RELIABILITY_PROFILE_ID,
            ReviewFinding.severity == "blocker",
            ReviewFinding.status == "open",
            ReviewFinding.target_type == "draft_claim",
        )
    )
    for finding in findings:
        claim = db.get(DraftClaim, finding.target_id)
        if claim is None or claim.source_scope_hash != summary.source_scope_hash:
            continue
        if field_ids is not None and claim.field_id not in field_ids:
            continue
        reasons.append(f"reliability_blocker:{finding.target_id}")
    return reasons


def has_reliability_blocker(db: Session, run: AnalysisRun) -> bool:
    return bool(reliability_blocker_reasons(db, run))
