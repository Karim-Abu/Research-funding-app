"""Scope-bound reliability approval gating (Milestone 9K, corr 3/13; M10.1 F3).

A reliability blocker's *claim-bound* reason governs approval **only** when its target claim
belongs to the current, non-stale RunQualitySummary (i.e. the draft has not changed since
the pass). Since M10.1 a stale summary additionally yields a run-level ``reliability_stale``
blocking reason and a visible run-level ReviewFinding: once a pass has run, a changed draft
requires a fresh pass before approval. A run that never ran a reliability pass is
unaffected. Imported by the review layer via lazy imports to avoid an import cycle.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalysisRun, DraftClaim, ReviewFinding, RunQualitySummary
from app.reliability import RELIABILITY_PROFILE_ID
from app.reliability.scope import compute_reliability_scope_hash
from app.repositories import audit
from app.review.copy_readiness import fields_with_valid_approval
from app.review.fingerprint import finding_code_family

# B5 — «unsupported strong claim» wird erst blockierend, wenn der Nutzer das
# betroffene Feld als bereit freigegeben hat. Diese Familien sind Varianten
# einer unbelegten Aussage; reliability:conflict ist ohnehin Blocker,
# reliability:weak/market bleiben Reviewer-Risiko.
_ESCALATION_FAMILIES = {
    "reliability:unsupported",
    "reliability:quantified",
    "reliability:proposed_fact",
    "reliability:false_consensus",
}


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
    """Approval-blocking reasons from OPEN reliability findings whose target claim belongs
    to the current non-stale summary (corr 13), plus — M10.1 (F3) — a run-level
    ``reliability_stale`` reason whenever a pass ran but its summary no longer reflects the
    current inputs. The stale reason applies to run AND field approvals (fail closed).

    Blockierend sind (B5): persistierte Blocker-Findings (``reliability:conflict``)
    sowie — Eskalation — offene Warning-Findings der ``_ESCALATION_FAMILIES``,
    wenn der Ziel-Claim stark formuliert ist UND sein Feld vom Nutzer bereits
    als bereit freigegeben wurde. Bei der Feld-Freigabe selbst ist das Feld noch
    nicht freigegeben — die Eskalation greift erst danach (Run-Freigabe)."""
    reasons: list[str] = []
    if is_stale(db, run):
        reasons.append(f"reliability_stale:{run.run_id}")
    summary = current_summary(db, run)
    if summary is None:
        return reasons
    approved_fields = fields_with_valid_approval(db, run.run_id)
    findings = db.scalars(
        select(ReviewFinding).where(
            ReviewFinding.run_id == run.run_id,
            ReviewFinding.source == "agent",
            ReviewFinding.profile_id == RELIABILITY_PROFILE_ID,
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
        if finding.severity == "blocker":
            reasons.append(f"reliability_blocker:{finding.target_id}")
        elif (
            finding.severity == "warning"
            and claim.strength == "strong"
            and claim.field_id in approved_fields
            and finding_code_family(finding.finding_code) in _ESCALATION_FAMILIES
        ):
            reasons.append(f"reliability_blocker:{finding.target_id}")
    return reasons


def has_reliability_blocker(db: Session, run: AnalysisRun) -> bool:
    return bool(reliability_blocker_reasons(db, run))


def stale_finding_code(run: AnalysisRun) -> str:
    return f"reliability:stale:{run.run_id}"


def sync_stale_finding(db: Session, run: AnalysisRun) -> None:
    """Idempotently surface staleness as a run-level blocker ReviewFinding (M10.1, F3) so it
    is visible in the normal ReviewPackage. Open while ``is_stale``; resolved (never
    deleted) once a fresh pass makes the summary current again. Run-level identity:
    profile=M9K + ``field_id=None`` + ``target_type="run"`` — claim-bound gate findings
    always carry a field_id, so the review UI can distinguish them without new contract
    fields. Caller owns commit."""
    # SessionLocal runs with autoflush=False: a summary the caller just built (fresh pass)
    # must be flushed to be visible to the staleness check, or it would be re-opened here.
    db.flush()
    code = stale_finding_code(run)
    row = db.scalar(
        select(ReviewFinding).where(
            ReviewFinding.run_id == run.run_id,
            ReviewFinding.source == "agent",
            ReviewFinding.profile_id == RELIABILITY_PROFILE_ID,
            ReviewFinding.finding_code == code,
        )
    )
    if is_stale(db, run):
        if row is None:
            row = ReviewFinding(
                finding_id=str(uuid.uuid4()), run_id=run.run_id,
                workspace_id=run.workspace_id, profile_id=RELIABILITY_PROFILE_ID,
                field_id=None, requirement_id=None, severity="blocker",
                description=(
                    "Qualitätsprüfung veraltet: der Entwurf wurde nach dem letzten "
                    "Reliability-Lauf geändert. Bitte die Reliability-Prüfung erneut "
                    "ausführen, bevor freigegeben wird."
                ),
                suggested_improvement=None, status="open", advisory=False,
                source="agent", finding_code=code,
                target_type="run", target_id=run.run_id,
                recommended_next_action=None,
            )
            db.add(row)
            audit.record(
                db, workspace_id=run.workspace_id, actor_user_id=None,
                action="reliability.finding_created", target_type="review_finding",
                target_id=row.finding_id,
                detail={"code": code, "severity": "blocker"},
            )
        elif row.status != "open":
            row.status = "open"
            audit.record(
                db, workspace_id=run.workspace_id, actor_user_id=None,
                action="reliability.finding_updated", target_type="review_finding",
                target_id=row.finding_id, detail={"status": "open"},
            )
    elif row is not None and row.status == "open":
        row.status = "resolved"
        audit.record(
            db, workspace_id=run.workspace_id, actor_user_id=None,
            action="reliability.finding_updated", target_type="review_finding",
            target_id=row.finding_id, detail={"status": "resolved"},
        )
    db.flush()
