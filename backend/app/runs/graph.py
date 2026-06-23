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

from app.config.settings import get_settings
from app.db.models import AnalysisRun, RunSourceSnapshot
from app.db.session import SessionLocal
from app.evidence import pipeline as evidence_pipeline
from app.repositories import audit, controls
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
    """A1 is deferred — run the deterministic lexical evidence baseline only.
    Creates EvidenceCandidates from requirements + frozen fragments; creates NO
    ExtractedFacts and makes no LLM/network/embedding call."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, state["run_id"])
        if _is_cancelled(run):
            return {**state, "cancelled": True}
        count = evidence_pipeline.run_discovery(db, run)
        _set_stage(db, run, "extract_facts_and_map_evidence")
        db.commit()
        logger.info("evidence discovery candidates=%d run=%s", count, run.run_id)
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
        builder.add_node("finalize_run", node_finalize_run)
        builder.add_edge(START, "initialize")
        builder.add_edge("initialize", "validate_source_snapshot")
        builder.add_edge(
            "validate_source_snapshot", "extract_facts_and_map_evidence"
        )
        builder.add_edge("extract_facts_and_map_evidence", "verify_evidence")
        builder.add_edge("verify_evidence", "evaluate_requirements_and_rules")
        builder.add_edge("evaluate_requirements_and_rules", "finalize_run")
        builder.add_edge("finalize_run", END)
        _graph = builder.compile(checkpointer=get_checkpointer())
    return _graph
