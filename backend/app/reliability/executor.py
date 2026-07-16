"""Reliability pass orchestration (Milestone 9K, STEP 12).

Deterministic per-run pass over the current DraftVersions of a completed run: extract claims
→ lineage → evidence-sufficiency → unsupported/false-consensus/drift findings → a per-run
RunQualitySummary. Idempotent per ``source_scope_hash``; a changed scope produces a new
current summary and marks the old one stale. No provider call, no draft mutation.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisRun,
    AsyncOperation,
    ClaimLineage,
    DraftClaim,
    DraftVersion,
    PortalFieldDraft,
    RunQualitySummary,
)
from app.db.session import SessionLocal
from app.repositories import audit
from app.reliability import drift as drift_mod
from app.reliability import false_consensus as fc_mod
from app.reliability import gate as gate_mod
from app.reliability.extract import extract_claims
from app.reliability.lineage import build_lineage
from app.reliability.scope import compute_reliability_scope_hash
from app.reliability.summary import ClaimResult, build_summary
from app.review import package as review_package
from app.runs.constants import TERMINAL_OPERATION_STATUSES

logger = logging.getLogger("app.reliability.executor")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def run_reliability_pass(
    db: Session, run: AnalysisRun, *, operation_id: str | None = None
) -> RunQualitySummary:
    """Synchronous core. Idempotent: reuse a current same-scope summary; otherwise recompute
    and mark prior summaries stale. Caller owns commit."""
    scope_hash = compute_reliability_scope_hash(db, run)

    existing = db.scalar(
        select(RunQualitySummary)
        .where(RunQualitySummary.run_id == run.run_id)
        .order_by(RunQualitySummary.generated_at.desc())
    )
    if (
        existing is not None
        and existing.status == "current"
        and existing.source_scope_hash == scope_hash
    ):
        return existing  # idempotent no-op on the same scope (corr 6)

    # A new scope → the previous current summary is stale.
    db.execute(
        update(RunQualitySummary)
        .where(
            RunQualitySummary.run_id == run.run_id,
            RunQualitySummary.status == "current",
        )
        .values(status="stale")
    )
    # Recompute cleanly for this run.
    db.execute(delete(ClaimLineage).where(ClaimLineage.run_id == run.run_id))
    db.execute(delete(DraftClaim).where(DraftClaim.run_id == run.run_id))
    db.flush()

    results: list[ClaimResult] = []
    all_specs: list[gate_mod.ReliabilityFindingSpec] = []
    drift_count = 0
    fields_with_findings: set[str] = set()
    claims_with_findings: set[str] = set()

    drafts = db.scalars(
        select(PortalFieldDraft)
        .where(PortalFieldDraft.run_id == run.run_id)
        .order_by(PortalFieldDraft.field_id.asc())
    ).all()
    fields_total = 0
    for draft in drafts:
        version = (
            db.get(DraftVersion, draft.current_version_id)
            if draft.current_version_id else None
        )
        if version is None:
            continue
        fields_total += 1
        text = version.text or ""

        # Field-level semantic drift.
        drift_specs = drift_mod.detect_drift(field_id=draft.field_id, text=text)
        if drift_specs:
            drift_count += len(drift_specs)
            all_specs.extend(drift_specs)
            fields_with_findings.add(draft.field_id)

        for claim in extract_claims(
            run_id=run.run_id, draft_id=draft.draft_id,
            draft_version_id=version.draft_version_id, field_id=draft.field_id, text=text,
        ):
            db.add(DraftClaim(
                claim_id=claim.claim_id, run_id=run.run_id, workspace_id=run.workspace_id,
                draft_id=claim.draft_id, draft_version_id=claim.draft_version_id,
                field_id=claim.field_id, start_char=claim.start_char, end_char=claim.end_char,
                claim_text=claim.claim_text, claim_type=claim.claim_type,
                strength=claim.strength, requires_evidence=claim.requires_evidence,
                extraction_method=claim.extraction_method,
                source_text_hash=claim.source_text_hash, source_scope_hash=scope_hash,
            ))
            lineage = build_lineage(db, run, claim)
            db.add(ClaimLineage(
                lineage_id="lin-" + uuid.uuid4().hex[:20], claim_id=claim.claim_id,
                run_id=run.run_id, workspace_id=run.workspace_id,
                lineage_status=lineage.lineage_status,
                sufficiency_status=lineage.sufficiency_status,
                provenance=lineage.provenance, matched_terms=lineage.matched_terms,
                reason=lineage.reason,
            ))
            gate_specs = gate_mod.gate_claim(claim, lineage)
            fc_specs = fc_mod.false_consensus_specs(claim, lineage)
            # B6 — pro Claim nur die primäre Ursache persistieren (Dedup über
            # Gate- UND False-Consensus-Findings); die Summary-Metriken unten
            # bleiben claimgenau (is_false_consensus vor dem Dedup bestimmt).
            claim_specs = gate_mod.primary_claim_spec(gate_specs + fc_specs)
            if claim_specs:
                claims_with_findings.add(claim.claim_id)
                fields_with_findings.add(claim.field_id)
            all_specs.extend(claim_specs)
            results.append(ClaimResult(
                claim=claim, lineage=lineage,
                is_false_consensus=bool(fc_specs),
            ))

    blocker, warning = gate_mod.apply_reliability_findings(db, run, all_specs)

    summary = build_summary(
        db, run, scope_hash=scope_hash, results=results, drift_count=drift_count,
        blocker_count=blocker, warning_count=warning,
        review_required_count=len(claims_with_findings),
        fields_total=fields_total, fields_needs_review=len(fields_with_findings),
        operation_id=operation_id,
    )
    # Reflect reliability findings in the ReviewPackage (counts + approval_status) without
    # re-running deterministic findings or clearing recheck.
    review_package.refresh_package(db, run, recompute_findings=False)
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None,
        action="reliability.pass_completed", target_type="run", target_id=run.run_id,
        detail={
            "summary_id": summary.summary_id, "claim_count": summary.claim_count,
            "quality_flag": summary.quality_flag, "blocker_count": blocker,
        },
    )
    db.flush()
    return summary


def reliability_executor(run_id: str, operation_id: str) -> None:
    """Background pass. Fail-closed; never changes run.status; never mutates drafts."""
    started = _now()
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        op = db.get(AsyncOperation, operation_id)
        if run is None or op is None:
            return
        if op.status in TERMINAL_OPERATION_STATUSES:
            return
        op.status = "running"
        op.started_at = started
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        db.close()
        _mark_failed(run_id, operation_id)
        return
    finally:
        db.close()

    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        op = db.get(AsyncOperation, operation_id)
        if run is None or op is None:
            return
        summary = run_reliability_pass(db, run, operation_id=operation_id)
        summary.latency_seconds = max(0.0, (_now() - started).total_seconds())
        if op.status not in TERMINAL_OPERATION_STATUSES:
            op.status = "succeeded"
            op.finished_at = _now()
            op.progress_percent = 100
            op.result = {
                "run_id": run_id, "summary_id": summary.summary_id,
                "quality_flag": summary.quality_flag,
            }
        db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("reliability pass failed")
        db.rollback()
        _mark_failed(run_id, operation_id)
    finally:
        db.close()


def _mark_failed(run_id: str, operation_id: str) -> None:
    db = SessionLocal()
    try:
        op = db.get(AsyncOperation, operation_id)
        if op is not None and op.status not in TERMINAL_OPERATION_STATUSES:
            op.status = "failed"
            op.finished_at = _now()
            op.last_error_code = "RELIABILITY_FAILED"
            op.error = {
                "type": "/problems/reliability_failed", "title": "Reliability Error",
                "status": 500, "detail": "Reliability pass failed.",
                "code": "RELIABILITY_FAILED", "correlation_id": str(uuid.uuid4()),
            }
        # Mark any half-written current summary failed.
        db.execute(
            update(RunQualitySummary)
            .where(
                RunQualitySummary.operation_id == operation_id,
                RunQualitySummary.status == "current",
            )
            .values(status="failed")
        )
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    finally:
        db.close()
