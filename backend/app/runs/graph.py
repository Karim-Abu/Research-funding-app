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
from app.repositories import audit, controls
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
        builder.add_node("finalize_run", node_finalize_run)
        builder.add_edge(START, "initialize")
        builder.add_edge("initialize", "validate_source_snapshot")
        builder.add_edge("validate_source_snapshot", "finalize_run")
        builder.add_edge("finalize_run", END)
        _graph = builder.compile(checkpointer=get_checkpointer())
    return _graph
