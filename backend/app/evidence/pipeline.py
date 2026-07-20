"""Deterministic evidence pipeline orchestration (Milestone 5).

Three deterministic stages wired into the run graph: discovery (persist
candidates), verification (persist anchors), and link materialization (anchors
-> requirement assessments). All persistence is upsert-only; the caller owns the
transaction. No LLM, network, embeddings or provider calls anywhere.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models import AnalysisRun, RequirementAssessment
from app.evidence import discovery, verification
from app.repositories import audit, controls
from app.repositories import evidence as evidence_repo


def run_discovery(db: Session, run: AnalysisRun) -> int:
    """A1 is disabled — deterministic lexical baseline only. No ExtractedFacts."""
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None,
        action="evidence.discovery_started", target_type="run", target_id=run.run_id,
    )
    max_per = get_settings().evidence_max_candidates_per_requirement
    specs = discovery.discover_candidates(db, run, max_per_requirement=max_per)
    for spec in specs:
        candidate = evidence_repo.upsert_candidate(db, run, spec)
        audit.record(
            db, workspace_id=run.workspace_id, actor_user_id=None,
            action="evidence.candidate_created", target_type="evidence_candidate",
            target_id=candidate.candidate_id,
            detail={"requirement_id": spec.target_requirement_id},
        )
    controls.record(
        db, workspace_id=run.workspace_id, project_id=run.project_id,
        source_id=None, control_id="CTRL.LEAST_CONTEXT", status="passed",
        detail=f"deterministic_baseline a1_disabled candidates={len(specs)}",
    )
    controls.record(
        db, workspace_id=run.workspace_id, project_id=run.project_id,
        source_id=None, control_id="CTRL.RUN_SNAPSHOT_SCOPE", status="passed",
        detail=f"algo={discovery.RETRIEVAL_ALGORITHM_VERSION}",
    )
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None,
        action="evidence.discovery_completed", target_type="run",
        target_id=run.run_id, detail={"candidates": len(specs)},
    )
    return len(specs)


def run_verification(db: Session, run: AnalysisRun) -> dict[str, int]:
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None,
        action="evidence.verification_started", target_type="run",
        target_id=run.run_id,
    )
    counts = {"exact_verified": 0, "unverified": 0, "rejected": 0}
    candidates = evidence_repo.list_candidates_for_run(db, run.run_id)
    for candidate in candidates:
        outcome = verification.verify_candidate(db, run, candidate)
        candidate.status = (
            "accepted"
            if outcome.verification_status == "exact_verified"
            else "rejected"
            if outcome.verification_status == "rejected"
            else "needs_human_review"
        )
        candidate.rejection_reason_code = (
            outcome.reason if outcome.verification_status == "rejected" else None
        )
        anchor = evidence_repo.upsert_anchor(db, run, candidate, outcome)
        candidate.anchor_id = anchor.anchor_id
        counts[outcome.verification_status] = (
            counts.get(outcome.verification_status, 0) + 1
        )
        action = (
            "evidence.anchor_created"
            if outcome.verification_status == "exact_verified"
            else "evidence.anchor_unverified"
        )
        audit.record(
            db, workspace_id=run.workspace_id, actor_user_id=None, action=action,
            target_type="evidence_anchor", target_id=anchor.anchor_id,
            detail={"status": outcome.verification_status, "reason": outcome.reason},
        )
    # Version + normalizer lock and exact-only auto-verification controls.
    blocked = counts.get("rejected", 0)
    controls.record(
        db, workspace_id=run.workspace_id, project_id=run.project_id,
        source_id=None, control_id="CTRL.VERSION_LOCK",
        status="passed" if blocked == 0 else "warning",
        detail=f"rejected={blocked}",
    )
    controls.record(
        db, workspace_id=run.workspace_id, project_id=run.project_id,
        source_id=None, control_id="CTRL.EVIDENCE_VERIFICATION", status="passed",
        detail=(
            f"exact_verified={counts['exact_verified']} "
            f"unverified={counts['unverified']} rejected={counts['rejected']}"
        ),
    )
    controls.record(
        db, workspace_id=run.workspace_id, project_id=run.project_id,
        source_id=None, control_id="CTRL.OUTPUT_SCHEMA", status="passed",
        detail="evidence_anchor",
    )
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None,
        action="evidence.verification_completed", target_type="run",
        target_id=run.run_id, detail=counts,
    )
    return counts


def materialize_links(db: Session, run: AnalysisRun) -> int:
    """After RequirementAssessments exist, link each candidate's anchor to the
    assessment for the requirement it targeted. Supplementary only — never
    changes an assessment status."""
    assessment_by_requirement = {
        a.requirement_id: a.assessment_id
        for a in db.scalars(
            select(RequirementAssessment).where(
                RequirementAssessment.run_id == run.run_id
            )
        )
    }
    created = 0
    for candidate in evidence_repo.list_candidates_for_run(db, run.run_id):
        if candidate.anchor_id is None:
            continue
        assessment_id = assessment_by_requirement.get(candidate.target_requirement_id)
        if assessment_id is None:
            continue  # requirement was not applicable → no assessment to link
        link = evidence_repo.upsert_link(
            db, run, candidate.anchor_id, assessment_id
        )
        audit.record(
            db, workspace_id=run.workspace_id, actor_user_id=None,
            action="evidence.link_created", target_type="evidence_link",
            target_id=link.evidence_link_id,
            detail={"assessment_id": assessment_id},
        )
        created += 1
    controls.record(
        db, workspace_id=run.workspace_id, project_id=run.project_id,
        source_id=None, control_id="CTRL.EVIDENCE_REQUIREMENT", status="passed",
        detail=f"links={created}",
    )
    return created
