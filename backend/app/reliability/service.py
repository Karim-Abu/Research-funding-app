"""Reliability pass service (Milestone 9K, STEP 12) — create the async pass + read view."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.contracts.reliability import (
    ReliabilityClaimView,
    ReliabilityFindingView,
    ReliabilityView,
    RunQualitySummaryView,
)
from app.contracts.run import AsyncAccepted
from app.db.models import (
    AnalysisRun,
    AsyncOperation,
    ClaimLineage,
    DraftClaim,
    ReviewFinding,
)
from app.reliability import RELIABILITY_PROFILE_ID
from app.reliability import approval as reliability_approval
from app.repositories import audit


def create_reliability_pass(
    db: Session,
    *,
    run: AnalysisRun,
    actor_user_id: str,
    idempotency_key: str | None = None,
    correlation_id: str | None = None,
) -> tuple[AsyncOperation, AsyncAccepted]:
    if run.status != "completed":
        raise ProblemException(
            status=409, code="run_not_reviewable", title="Conflict",
            detail="Die Zuverlässigkeitsprüfung ist erst nach Abschluss des Durchlaufs verfügbar.",
        )
    operation = AsyncOperation(
        operation_id=str(uuid.uuid4()),
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        resource_type="reliability",
        resource_id=run.run_id,
        status="queued",
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )
    db.add(operation)
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=actor_user_id,
        action="reliability.pass_requested", target_type="run", target_id=run.run_id,
        detail={"operation_id": operation.operation_id},
    )
    accepted = AsyncAccepted(
        operation_id=operation.operation_id,
        resource_type="reliability",
        resource_id=run.run_id,
        status="queued",
        poll_url=f"/api/v1/operations/{operation.operation_id}",
    )
    return operation, accepted


def get_view(db: Session, run: AnalysisRun) -> ReliabilityView:
    summary = reliability_approval.latest_summary(db, run)
    stale = reliability_approval.is_stale(db, run)
    if summary is None:
        return ReliabilityView(run_id=run.run_id, available=False, reliability_stale=False)

    claims = db.scalars(
        select(DraftClaim).where(DraftClaim.run_id == run.run_id)
        .order_by(DraftClaim.field_id.asc(), DraftClaim.start_char.asc())
    ).all()
    lineages = {
        lin.claim_id: lin
        for lin in db.scalars(
            select(ClaimLineage).where(ClaimLineage.run_id == run.run_id)
        )
    }
    claim_views = [
        ReliabilityClaimView(
            claim_id=c.claim_id, field_id=c.field_id, claim_type=c.claim_type,
            strength=c.strength, requires_evidence=c.requires_evidence,
            claim_text=c.claim_text,
            lineage_status=lineages[c.claim_id].lineage_status if c.claim_id in lineages else "no_evidence",
            sufficiency_status=lineages[c.claim_id].sufficiency_status if c.claim_id in lineages else "insufficient_evidence",
            reason=lineages[c.claim_id].reason if c.claim_id in lineages else None,
        )
        for c in claims
    ]
    findings = db.scalars(
        select(ReviewFinding).where(
            ReviewFinding.run_id == run.run_id,
            ReviewFinding.source == "agent",
            ReviewFinding.profile_id == RELIABILITY_PROFILE_ID,
            ReviewFinding.status == "open",
        )
    ).all()
    finding_views = [
        ReliabilityFindingView(
            finding_id=f.finding_id, field_id=f.field_id, severity=f.severity,
            description=f.description, status=f.status, finding_code=f.finding_code,
            target_type=f.target_type, target_id=f.target_id,
        )
        for f in findings
    ]
    return ReliabilityView(
        run_id=run.run_id, available=True, reliability_stale=stale,
        summary=_summary_view(summary, stale), claims=claim_views, findings=finding_views,
    )


def _summary_view(summary, stale: bool) -> RunQualitySummaryView:
    return RunQualitySummaryView(
        summary_id=summary.summary_id, run_id=summary.run_id, status=summary.status,
        stale=stale, quality_flag=summary.quality_flag, claim_count=summary.claim_count,
        supported_claims=summary.supported_claims,
        weakly_supported_claims=summary.weakly_supported_claims,
        unsupported_claims=summary.unsupported_claims,
        conflicting_claims=summary.conflicting_claims,
        evidence_coverage=summary.evidence_coverage,
        evidence_correctness_sample_size=summary.evidence_correctness_sample_size,
        evidence_correctness_sample_pass_rate=summary.evidence_correctness_sample_pass_rate,
        review_required_count=summary.review_required_count,
        blocker_count=summary.blocker_count, warning_count=summary.warning_count,
        fields_ready=summary.fields_ready, fields_needs_review=summary.fields_needs_review,
        false_consensus_risk_count=summary.false_consensus_risk_count,
        semantic_drift_count=summary.semantic_drift_count,
        raw_logging_detected=summary.raw_logging_detected,
        tool_leakage_detected=summary.tool_leakage_detected,
        cost_chf=summary.cost_chf, cost_placeholder=summary.cost_placeholder,
        latency_seconds=summary.latency_seconds, summary_version=summary.summary_version,
        generated_at=summary.generated_at,
    )
