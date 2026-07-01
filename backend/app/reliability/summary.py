"""RunQualitySummary builder (Milestone 9K, STEP 10).

Deterministic, reproducible per-run quality metrics for M10 evaluation. Coverage (did we
link ANY evidence?) is kept strictly separate from correctness/sufficiency (does the
evidence appear to support the claim?). High coverage + low sufficiency ⇒ ``quality_flag =
risky`` — never a success. Cost is never invented (nullable + ``cost_placeholder``).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalysisRun, AuditEvent, RunQualitySummary
from app.reliability import SUMMARY_VERSION
from app.reliability import sufficiency as suff
from app.reliability.extract import ExtractedClaim
from app.reliability.lineage import LineageResult


@dataclass
class ClaimResult:
    claim: ExtractedClaim
    lineage: LineageResult
    is_false_consensus: bool = False


def _has_evidence(lineage: LineageResult) -> bool:
    p = lineage.provenance
    return bool(
        p.get("evidence_anchor_ids") or p.get("extracted_fact_ids")
        or p.get("evidence_candidate_ids") or p.get("market_item_ids")
    )


def scan_leakage(db: Session, run: AnalysisRun) -> tuple[bool, bool]:
    """Best-effort deterministic leakage scan over the run's audit trail. Reuses the M9J
    no-raw-logging helper. Returns (raw_logging_detected, tool_leakage_detected). By
    construction the pipeline stores only hashes, so both are normally False."""
    from app.security.redaction import serialize_detail

    raw_logging = False
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.workspace_id == run.workspace_id)
    )
    for event in events:
        text = serialize_detail(event.detail).lower()
        # A detail carrying a query/prompt VALUE (not a *_hash) would be a leak.
        if ('"query"' in text or '"raw_query"' in text or '"prompt"' in text
                or '"claim_text"' in text):
            raw_logging = True
            break
    # ToolInvocation stores only input_hash/output_hash — no raw payload can be present.
    return raw_logging, False


def build_summary(
    db: Session,
    run: AnalysisRun,
    *,
    scope_hash: str,
    results: list[ClaimResult],
    drift_count: int,
    blocker_count: int,
    warning_count: int,
    review_required_count: int,
    fields_total: int,
    fields_needs_review: int,
    operation_id: str | None = None,
    latency_seconds: float | None = None,
) -> RunQualitySummary:
    requiring = [r for r in results if r.claim.requires_evidence]
    supported = sum(1 for r in requiring if r.lineage.supported)
    conflicting = sum(1 for r in requiring if r.lineage.lineage_status == "conflicting_evidence")
    unsupported = sum(1 for r in requiring if r.lineage.lineage_status == "no_evidence")
    weakly = sum(
        1 for r in requiring
        if not r.lineage.supported
        and r.lineage.lineage_status not in ("no_evidence", "conflicting_evidence")
    )
    with_evidence = [r for r in requiring if _has_evidence(r.lineage)]

    coverage = (len(with_evidence) / len(requiring)) if requiring else 0.0
    sample_size = len(with_evidence)
    pass_rate = (
        sum(1 for r in with_evidence if r.lineage.sufficiency_status == suff.SUPPORTS)
        / sample_size
    ) if sample_size else 0.0

    false_consensus = sum(1 for r in results if r.is_false_consensus)
    raw_logging, tool_leakage = scan_leakage(db, run)

    risky = (
        blocker_count > 0
        or unsupported > 0
        or conflicting > 0
        or (coverage >= 0.5 and pass_rate < 0.6)
    )
    quality_flag = "risky" if risky else "ok"

    summary = RunQualitySummary(
        summary_id="rqs-" + uuid.uuid4().hex[:20],
        run_id=run.run_id,
        workspace_id=run.workspace_id,
        operation_id=operation_id,
        status="current",
        source_scope_hash=scope_hash,
        claim_count=len(results),
        supported_claims=supported,
        weakly_supported_claims=weakly,
        unsupported_claims=unsupported,
        conflicting_claims=conflicting,
        evidence_coverage=round(coverage, 4),
        evidence_correctness_sample_size=sample_size,
        evidence_correctness_sample_pass_rate=round(pass_rate, 4),
        review_required_count=review_required_count,
        blocker_count=blocker_count,
        warning_count=warning_count,
        fields_ready=max(0, fields_total - fields_needs_review),
        fields_needs_review=fields_needs_review,
        false_consensus_risk_count=false_consensus,
        semantic_drift_count=drift_count,
        raw_logging_detected=raw_logging,
        tool_leakage_detected=tool_leakage,
        quality_flag=quality_flag,
        cost_chf=None,
        cost_placeholder=True,
        latency_seconds=latency_seconds,
        summary_version=SUMMARY_VERSION,
        generated_at=datetime.now(timezone.utc),
    )
    db.add(summary)
    return summary
