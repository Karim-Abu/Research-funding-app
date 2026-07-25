"""Project cost API exposes persisted usage only, never reconstructed prices."""
from __future__ import annotations

import uuid

from app.agents import cost_guard
from app.agents.providers.base import ProviderUsage
from app.db.models import (
    AgentInvocation,
    AgentInvocationAttempt,
    AnalysisRun,
    ResearchTask,
    ToolInvocation,
)
from app.db.session import SessionLocal
from tests.agent_helpers import WS, make_run
from tests.conftest import TOBIAS_EMAIL, TOBIAS_PASSWORD, login


def test_member_sees_partial_costs_without_an_invented_total(client):
    db = SessionLocal()
    try:
        run_id = make_run(db)
        run = db.get(AnalysisRun, run_id)
        assert run is not None
        cost_guard.record_usage(
            db,
            run_id=run_id,
            workspace_id="ws-demo",
            provider="openai_direct",
            model_id="gpt-5.6-luna",
            usage=ProviderUsage(input_tokens=20_000, output_tokens=3_000),
        )
        # A provider-confirmed id without a verified catalogue row stays
        # unpriced and makes the aggregate explicitly partial.
        cost_guard.record_usage(
            db,
            run_id=run_id,
            workspace_id="ws-demo",
            provider="openai_direct",
            model_id="provider-alias-not-in-catalogue",
            usage=ProviderUsage(input_tokens=100, output_tokens=100),
        )
        db.commit()
        project_id = run.project_id
    finally:
        db.close()

    login(client, TOBIAS_EMAIL, TOBIAS_PASSWORD)
    response = client.get(f"/api/v1/projects/{project_id}/costs")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["billing_currency"] == "USD"
    assert body["runs"][0]["cost"] == {
        "status": "partial",
        "usd": None,
        "chf_reference": None,
        "known_usd": 0.038,
        "known_chf_reference": 0.030647,
        "unpriced_call_count": 1,
    }
    assert any(
        execution["cost"]["status"] == "unknown_price"
        for execution in body["runs"][0]["executions"]
    )


def test_cost_view_is_empty_when_project_has_no_runs(client):
    from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, create_project

    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf, "No cost runs")
    response = client.get(f"/api/v1/projects/{project_id}/costs")
    assert response.status_code == 200, response.text
    assert response.json()["runs"] == []


def test_execution_exposes_the_human_system_role(client):
    db = SessionLocal()
    try:
        run_id = make_run(db)
        run = db.get(AnalysisRun, run_id)
        record = cost_guard.record_usage(
            db,
            run_id=run_id,
            workspace_id=WS,
            provider="openai_direct",
            model_id="gpt-5.6-terra",
            usage=ProviderUsage(input_tokens=7_256, output_tokens=3_627),
        )
        invocation_id = "inv-" + uuid.uuid4().hex[:8]
        db.add(AgentInvocation(
            invocation_id=invocation_id, run_id=run_id, workspace_id=WS,
            agent_id="A2", profile_id="A2.value_creation_market_logic",
            model_route="openai_gpt_56_terra_candidate", provider="openai_direct",
            model_id="gpt-5.6-terra", input_schema_id="in", output_schema_id="out",
            role_id="A2_INNOSUISSE_PROPOSAL_WRITER", status="succeeded",
            usage_record_id=record.usage_record_id,
        ))
        db.add(AgentInvocationAttempt(
            attempt_id="att-" + uuid.uuid4().hex[:8], invocation_id=invocation_id,
            attempt_index=0, route_key="openai_gpt_56_terra_candidate",
            route_alias="gpt-5.6-terra", provider="openai_direct", status="succeeded",
            usage_record_id=record.usage_record_id,
        ))
        db.commit()
        project_id = run.project_id
    finally:
        db.close()

    login(client, TOBIAS_EMAIL, TOBIAS_PASSWORD)
    response = client.get(f"/api/v1/projects/{project_id}/costs")
    assert response.status_code == 200, response.text
    execution = response.json()["runs"][0]["executions"][0]
    assert execution["role_id"] == "A2_INNOSUISSE_PROPOSAL_WRITER"
    assert execution["model"] == "gpt-5.6-terra"


def test_web_research_calls_counts_firecrawl_not_internal_tools(client):
    db = SessionLocal()
    try:
        run_id = make_run(db)
        run = db.get(AnalysisRun, run_id)
        project_id = run.project_id
        task_id = "rt-" + uuid.uuid4().hex[:8]
        db.add(ResearchTask(
            research_task_id=task_id, project_id=project_id, workspace_id=WS,
            created_by="user-anna", purpose="competence_gap_analysis",
            subject_type="organisation", query_text="q",
            normalized_query_hash="h", status="succeeded",
        ))
        for tool_id in ("search_public_professional_sources", "fetch_validated_public_url"):
            db.add(ToolInvocation(
                invocation_id="ti-" + uuid.uuid4().hex[:8], workspace_id=WS,
                research_task_id=task_id, tool_id=tool_id, caller="research.executor",
                input_hash="ih", status="succeeded",
            ))
        # An internal, non-Firecrawl tool call must not be counted.
        db.add(ToolInvocation(
            invocation_id="ti-" + uuid.uuid4().hex[:8], workspace_id=WS,
            research_task_id=task_id, tool_id="retrieve_source_fragments",
            caller="agents.context", input_hash="ih", status="succeeded",
        ))
        db.commit()
    finally:
        db.close()

    login(client, TOBIAS_EMAIL, TOBIAS_PASSWORD)
    response = client.get(f"/api/v1/projects/{project_id}/costs")
    assert response.status_code == 200, response.text
    assert response.json()["web_research_calls"] == 2
