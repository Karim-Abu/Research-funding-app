"""Truthful AI-only run status remains separate from deterministic completion."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.config.settings import Settings
from app.db.models import AgentInvocation, AgentInvocationAttempt, AnalysisRun
from app.db.session import SessionLocal
from app.runs import graph
from tests.agent_helpers import make_run


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def real_eval(monkeypatch):
    monkeypatch.setattr(graph, "get_settings", lambda: Settings(ai_eval_mode="real"))


def _inv(db, run_id: str, agent: str, status: str, *, error_code=None):
    invocation_id = "live-inv-" + uuid.uuid4().hex[:10]
    row = AgentInvocation(
        invocation_id=invocation_id, run_id=run_id, workspace_id="ws-demo",
        agent_id=agent, profile_id=f"{agent}.test", model_route="route",
        provider="openai_direct", model_id="requested-model",
        requested_model_id="requested-model", actual_model_id=(
            "actual-model" if status == "succeeded" else None
        ),
        input_schema_id="In@v1", output_schema_id="Out@v1",
        role_id={
            "A1": "A1_FACT_EVIDENCE_ANALYST",
            "A2": "A2_INNOSUISSE_PROPOSAL_WRITER",
            "A3": "A3_INNOSUISSE_CRITICAL_REVIEWER",
        }.get(agent, f"{agent}_ROLE"),
        skill_id=f"{agent.lower()}.skill",
        skill_version="skill-v2", status=status, error_code=error_code,
        context_meta={
            "generation_kind": "model_generated",
            "model_call_attempted": status != "blocked",
        },
    )
    db.add(row)
    db.flush()
    return row


def _attempt(db, invocation: AgentInvocation, status: str, error_class=None):
    now = datetime.now(timezone.utc)
    db.add(AgentInvocationAttempt(
        attempt_id="attempt-" + uuid.uuid4().hex[:10],
        invocation_id=invocation.invocation_id, attempt_index=0, retry_index=0,
        route_key="route", route_alias="candidate", provider="openai_direct",
        requested_model_id="requested-model", status=status,
        error_class=error_class, termination_reason=error_class or "stop",
        started_at=now, finished_at=now,
    ))
    db.flush()


def _finalize(db, run_id: str) -> AnalysisRun:
    run = db.get(AnalysisRun, run_id)
    graph._finalize_live_status(db, run)
    db.flush()
    return run


def test_completed_live_requires_a1_a2_a3(db):
    run_id = make_run(db)
    for agent in ("A1", "A2", "A3"):
        _inv(db, run_id, agent, "succeeded")
    run = _finalize(db, run_id)
    assert run.status == "completed"
    assert run.live_execution_status == "completed_live"


def test_research_synthesis_cannot_replace_core_a1(db):
    run_id = make_run(db)
    research = _inv(db, run_id, "RESEARCH", "succeeded")
    research.role_id = "RESEARCH_EVIDENCE_SYNTHESIZER"
    _inv(db, run_id, "A2", "succeeded")
    _inv(db, run_id, "A3", "succeeded")
    assert _finalize(db, run_id).live_execution_status == "partial_live"


@pytest.mark.parametrize("success_agent", ["A1", "A2"])
def test_partial_live_keeps_successful_artifacts(db, success_agent):
    run_id = make_run(db)
    _inv(db, run_id, success_agent, "succeeded")
    failed = _inv(db, run_id, "A3" if success_agent == "A2" else "A2", "failed")
    _attempt(db, failed, "failed", "provider_outage")
    run = _finalize(db, run_id)
    assert run.live_execution_status == "partial_live"
    assert db.get(AgentInvocation, failed.invocation_id).status == "failed"


def test_live_unavailable_without_provider_attempt(db):
    run_id = make_run(db)
    unavailable = _inv(db, run_id, "A1", "failed")
    _attempt(db, unavailable, "model_unavailable", "preflight_required")
    assert _finalize(db, run_id).live_execution_status == "live_unavailable"


def test_blocked_by_policy_is_not_provider_failure(db):
    run_id = make_run(db)
    _inv(db, run_id, "A1", "blocked", error_code="data_policy_blocked")
    assert _finalize(db, run_id).live_execution_status == "blocked_by_policy"


def test_failed_live_after_attempt_without_artifact(db):
    run_id = make_run(db)
    failed = _inv(db, run_id, "A1", "failed")
    _attempt(db, failed, "failed", "schema_invalid")
    assert _finalize(db, run_id).live_execution_status == "failed_live"
