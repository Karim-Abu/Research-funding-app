"""Opt-in synthetic A1/A2/A3 live E2E; never runs in CI or without full config."""
from __future__ import annotations

import os

import pytest
from sqlalchemy import select

from app.agents.registry import get_agent_registry
from app.config.settings import get_settings
from app.db.models import AgentInvocation, AgentInvocationAttempt, AnalysisRun
from app.db.session import SessionLocal
from app.evaluation.pricing import resolve_cost
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, login, unsafe_headers
from tests.run_graph_helpers import cloud_project_with_source, cloud_run

pytestmark = pytest.mark.skipif(
    bool(os.environ.get("CI")) or os.environ.get("RUN_REAL_PROVIDER_SMOKE") != "true",
    reason="manual only: RUN_REAL_PROVIDER_SMOKE=true outside CI",
)


def _require_complete_live_configuration():
    settings = get_settings()
    if settings.ai_eval_mode != "real" or settings.agent_fake_provider:
        pytest.skip("requires AI_EVAL_MODE=real and AGENT_FAKE_PROVIDER=false")
    if not (settings.openai_api_key and settings.anthropic_api_key):
        pytest.skip("requires both real provider API keys")
    registry = get_agent_registry()
    for role_id in (
        "A1_FACT_EVIDENCE_ANALYST",
        "A2_INNOSUISSE_PROPOSAL_WRITER",
        "A3_INNOSUISSE_CRITICAL_REVIEWER",
    ):
        role = registry.role_routes[role_id]
        route = registry.route(role.primary)
        requested = route.requested_model_id(settings)
        if not requested:
            pytest.skip(f"missing provider model resolution for {route.alias}")
        if resolve_cost(
            provider=route.provider, model_id=requested,
            input_tokens=0, output_tokens=0,
        ).cost_status != "priced":
            pytest.skip(f"missing versioned CHF price evidence for {route.alias}")


def test_synthetic_live_run_creates_truthful_a1_a2_a3_artifacts(client):
    _require_complete_live_configuration()
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    preflight = client.post(
        "/api/v1/admin/live-system-status/preflight",
        headers=unsafe_headers(csrf),
    )
    assert preflight.status_code == 200, preflight.text
    assert preflight.json()["status"]["overall_status"] == "available"

    project_id, source_version_id = cloud_project_with_source(
        client, csrf, "Synthetic live role-routing smoke"
    )
    run_id = cloud_run(client, csrf, project_id, source_version_id, max_llm_calls=25)

    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        assert run.live_execution_status == "completed_live"
        invocations = list(db.scalars(
            select(AgentInvocation).where(AgentInvocation.run_id == run_id)
        ))
        by_agent = {inv.agent_id: inv for inv in invocations if inv.status == "succeeded"}
        assert {"A1", "A2", "A3"} <= set(by_agent)
        for agent in ("A1", "A2", "A3"):
            inv = by_agent[agent]
            assert inv.requested_model_id
            assert inv.actual_model_id
            assert inv.skill_version
            attempts = list(db.scalars(select(AgentInvocationAttempt).where(
                AgentInvocationAttempt.invocation_id == inv.invocation_id,
                AgentInvocationAttempt.status == "succeeded",
            )))
            assert attempts and attempts[-1].actual_model_id
    finally:
        db.close()
