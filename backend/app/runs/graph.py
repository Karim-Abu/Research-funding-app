"""Minimal LangGraph technical workflow: initialize → validate_source_snapshot
→ finalize_run, with an official SQLite checkpointer. No LLM/agent/network.

The app DB run status is authoritative; checkpoints are diagnostic/position only.
Each node reloads the run and short-circuits on cancellation (clar. #2).
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from app.agents import evidence_mapping, fact_extraction
from app.config.settings import get_settings
from app.db.models import AnalysisRun, RunSourceSnapshot
from app.db.session import SessionLocal
from app.drafts import pipeline as drafts_pipeline
from app.evidence import pipeline as evidence_pipeline
from app.repositories import audit, controls
from app.review import package as review_package
from app.runs import evaluation
from app.runs.constants import STAGE_PROGRESS
from app.runs.transitions import transition_run

logger = logging.getLogger("app.runs.graph")


class RunState(TypedDict):
    run_id: str
    project_id: str
    workspace_id: str
    cancelled: bool


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_cancelled(run: AnalysisRun) -> bool:
    return run is None or run.cancel_requested or run.status == "cancelled"


def _set_stage(db, run: AnalysisRun, stage: str) -> None:
    run.current_stage = stage
    run.progress_percent = STAGE_PROGRESS[stage]
    audit.record(
        db,
        workspace_id=run.workspace_id,
        actor_user_id=None,
        action="run.stage_changed",
        target_type="run",
        target_id=run.run_id,
        detail={"stage": stage},
    )


def node_initialize(state: RunState) -> RunState:
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        _set_stage(db, run, "initialize")
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            source_id=None, control_id="run.operation_state", status="passed",
            detail="initialized",
        )
        db.commit()
        return state
    finally:
        db.close()


def node_validate_source_snapshot(state: RunState) -> RunState:
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        count = len(
            list(
                db.scalars(
                    select(RunSourceSnapshot.id).where(
                        RunSourceSnapshot.run_id == run.run_id
                    )
                )
            )
        )
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            source_id=None, control_id="run.source_snapshot",
            status="passed" if count > 0 else "failed",
            detail=f"frozen_versions={count}",
        )
        _set_stage(db, run, "validate_source_snapshot")
        db.commit()
        return state
    finally:
        db.close()


def node_extract_facts_and_map_evidence(state: RunState) -> RunState:
    """M9B: run advisory A1 fact extraction (safe, never fails the run), then the
    deterministic lexical evidence baseline. A1 ExtractedFacts are advisory only
    and are NEVER consumed by the deterministic evidence/requirements pipeline."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        a1 = fact_extraction.run_a1_fact_extraction(db, run)
        count = evidence_pipeline.run_discovery(db, run)
        # M9C: advisory A1 evidence-candidate mapping (safe; never fails the run).
        # Persists agent-origin EvidenceCandidates that the unchanged deterministic
        # verify/link stages then process. Deterministic baseline is unaffected.
        mapping = evidence_mapping.run_a1_evidence_mapping(db, run)
        _set_stage(db, run, "extract_facts_and_map_evidence")
        db.commit()
        logger.info(
            "A1 facts=%s/%d evidence candidates=%d mapping=%s/+%d run=%s",
            a1.status, a1.facts_persisted, count, mapping.status,
            mapping.candidates_persisted, run.run_id,
        )
        return state
    finally:
        db.close()


def node_verify_evidence(state: RunState) -> RunState:
    """Deterministic exact-quote verification → EvidenceAnchors. Continues even
    when individual candidates remain unverified or none were found."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        counts = evidence_pipeline.run_verification(db, run)
        _set_stage(db, run, "verify_evidence")
        db.commit()
        logger.info("evidence verification %s run=%s", counts, run.run_id)
        return state
    finally:
        db.close()


def node_evaluate_requirements_and_rules(state: RunState) -> RunState:
    """Deterministic formal-eligibility precheck: run the 12 official core rules
    against the frozen project+partner snapshot, persist RuleResults +
    RequirementAssessments + OpenIssues; then materialize supplementary evidence
    links. No LLM, no network, no source text."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        counts = evaluation.evaluate_run(db, run.run_id)
        # Link verified/unverified anchors to the assessments now that they
        # exist. Supplementary only — never changes a deterministic status.
        evidence_pipeline.materialize_links(db, run)
        # M9C: complete the agent evidence-proposal evaluation trail (verification
        # status + linked assessment). Internal only; idempotent under replay.
        evidence_mapping.backfill_agent_evaluation(db, run)
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            source_id=None, control_id="run.requirements_evaluated",
            status="passed",
            detail=(
                f"blocker={counts['blocker']} warning={counts['warning']} "
                f"info={counts['info']}"
            ),
        )
        _set_stage(db, run, "evaluate_requirements_and_rules")
        audit.record(
            db, workspace_id=run.workspace_id, actor_user_id=None,
            action="run.requirements_evaluated", target_type="run",
            target_id=run.run_id, detail=counts,
        )
        db.commit()
        return state
    finally:
        db.close()


def node_draft_fields(state: RunState) -> RunState:
    """A2 is deferred — record the disabled drafting route and continue to the
    deterministic template stage. No provider/LLM/network call."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        drafts_pipeline.record_a2_disabled(db, run)
        _set_stage(db, run, "draft_fields")
        db.commit()
        return state
    finally:
        db.close()


def node_create_template_drafts(state: RunState) -> RunState:
    """Create deterministic PortalFieldDraft templates + initial DraftVersions
    idempotently from the immutable run inputs."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        count = drafts_pipeline.create_template_drafts(db, run)
        _set_stage(db, run, "create_template_drafts")
        db.commit()
        logger.info("template drafts created=%d run=%s", count, run.run_id)
        return state
    finally:
        db.close()


def node_critic_review(state: RunState) -> RunState:
    """A3 is deferred — record the disabled semantic-review route and run the
    deterministic review aggregator only. Creates ReviewFindings from persisted
    M4-M6 artifacts; no provider/LLM/network call and no semantic judgement."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        review_package.apply_findings(db, run)
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            source_id=None, control_id="CTRL.DATA_POLICY", status="passed",
            detail="a3_disabled deterministic_review",
        )
        _set_stage(db, run, "critic_review")
        db.commit()
        return state
    finally:
        db.close()


def node_aggregate_review(state: RunState) -> RunState:
    """Aggregate findings, evidence gaps, open issues and assessments into the
    ReviewPackage; compute the review package version + approval scope hash."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        package = review_package.refresh_package(db, run, recompute_findings=False)
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            source_id=None, control_id="CTRL.OUTPUT_SCHEMA", status="passed",
            detail=f"review_package_version={package.review_package_version}",
        )
        _set_stage(db, run, "aggregate_review")
        db.commit()
        return state
    finally:
        db.close()


def node_human_review(state: RunState) -> RunState:
    """Record that review is available. Deterministic and non-pausing: human
    review, recheck and approval happen on the completed run via the review API.
    The run is never auto-approved here."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            source_id=None, control_id="CTRL.APPROVAL_GATE", status="passed",
            detail="review_available no_auto_approval",
        )
        _set_stage(db, run, "human_review")
        db.commit()
        return state
    finally:
        db.close()


def node_finalize_run(state: RunState) -> RunState:
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        # Reload-and-check before finalize — never complete a cancelled run.
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        _set_stage(db, run, "finalize_run")
        transition_run(run, "completed")  # guards against terminal states
        run.ended_at = _now()
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            source_id=None, control_id="run.operation_state", status="passed",
            detail="finalized",
        )
        audit.record(
            db, workspace_id=run.workspace_id, actor_user_id=None,
            action="run.completed", target_type="run", target_id=run.run_id,
        )
        db.commit()
        return state
    finally:
        db.close()


_checkpointer: SqliteSaver | None = None
_graph = None


def get_checkpointer() -> SqliteSaver:
    global _checkpointer
    if _checkpointer is None:
        path = Path(get_settings().checkpoint_db_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        _checkpointer = SqliteSaver(conn)
        _checkpointer.setup()
    return _checkpointer


def get_graph():
    global _graph
    if _graph is None:
        builder = StateGraph(RunState)
        builder.add_node("initialize", node_initialize)
        builder.add_node("validate_source_snapshot", node_validate_source_snapshot)
        builder.add_node(
            "extract_facts_and_map_evidence",
            node_extract_facts_and_map_evidence,
        )
        builder.add_node("verify_evidence", node_verify_evidence)
        builder.add_node(
            "evaluate_requirements_and_rules",
            node_evaluate_requirements_and_rules,
        )
        builder.add_node("draft_fields", node_draft_fields)
        builder.add_node("create_template_drafts", node_create_template_drafts)
        builder.add_node("critic_review", node_critic_review)
        builder.add_node("aggregate_review", node_aggregate_review)
        builder.add_node("human_review", node_human_review)
        builder.add_node("finalize_run", node_finalize_run)
        builder.add_edge(START, "initialize")
        builder.add_edge("initialize", "validate_source_snapshot")
        builder.add_edge(
            "validate_source_snapshot", "extract_facts_and_map_evidence"
        )
        builder.add_edge("extract_facts_and_map_evidence", "verify_evidence")
        builder.add_edge("verify_evidence", "evaluate_requirements_and_rules")
        builder.add_edge("evaluate_requirements_and_rules", "draft_fields")
        builder.add_edge("draft_fields", "create_template_drafts")
        builder.add_edge("create_template_drafts", "critic_review")
        builder.add_edge("critic_review", "aggregate_review")
        builder.add_edge("aggregate_review", "human_review")
        builder.add_edge("human_review", "finalize_run")
        builder.add_edge("finalize_run", END)
        _graph = builder.compile(checkpointer=get_checkpointer())
    return _graph
