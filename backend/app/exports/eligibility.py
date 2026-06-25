"""Export draft-marking eligibility (Milestone 8).

Determines ``draft_marked`` deterministically at createExport. Only a *current,
valid, run-scope* ReviewApproval over the unchanged review state yields a
non-draft export. Everything else (no/stale/field-only approval, recheck
required, force_draft) is draft-marked. Blockers never prevent a draft export.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import AnalysisRun, ReviewApproval
from app.review import package as review_package


@dataclass(frozen=True)
class DraftDecision:
    draft_marked: bool
    approval: ReviewApproval | None  # the valid run-scope approval, only when non-draft
    scope_hash: str
    review_package_version: str
    reasons: tuple[str, ...]


def evaluate_draft_marked(
    db: Session, run: AnalysisRun, force_draft: bool
) -> DraftDecision:
    scope_hash = review_package.compute_scope_hash(db, run)
    version = review_package.package_version(scope_hash)
    approval = review_package.latest_run_approval(db, run)

    reasons: list[str] = []
    if force_draft:
        reasons.append("force_draft")
    if run.status != "completed":
        reasons.append("run_not_completed")
    if run.recheck_required:
        reasons.append("recheck_required")
    if approval is None:
        reasons.append("no_run_scope_approval")
    else:
        if approval.status != "approved" or approval.invalidated_at is not None:
            reasons.append("approval_stale")
        if approval.approval_scope_hash != scope_hash:
            reasons.append("scope_hash_mismatch")
        if approval.review_package_version != version:
            reasons.append("review_package_version_mismatch")

    draft_marked = bool(reasons)
    used_approval = None if draft_marked else approval
    return DraftDecision(
        draft_marked=draft_marked,
        approval=used_approval,
        scope_hash=scope_hash,
        review_package_version=version,
        reasons=tuple(reasons),
    )
