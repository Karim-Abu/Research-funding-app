"""EVAL.1 — Usage-/Latenz-/Kostenstatus-Aggregation und data_mode-Ableitung.

Fake-Provider only, keine Netzwerk-Calls.
"""
from __future__ import annotations

import uuid

import pytest

from app.agents.gateway import ModelResponse, invoke
from app.agents.providers import FakeProvider
from app.agents.providers.base import ProviderUsage
from app.db.models import AgentInvocation, AnalysisRun, UsageRecord
from app.db.session import SessionLocal
from app.evaluation.data_mode import DATA_MODES, derive_data_mode
from app.evaluation.summary import build_evaluation_summary, render_markdown
from app.evaluation.usage import (
    run_usage_totals,
    tool_usage_by_research_task,
    usage_by_agent_task,
)
from app.research.recording import record_tool
from tests.agent_helpers import base_request, fake_resolver, make_run

WS = "ws-demo"


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _invoke_fake(db, run_id, *, input_tokens, output_tokens):
    fake = FakeProvider(
        usage=ProviderUsage(input_tokens=input_tokens, output_tokens=output_tokens)
    )
    resp = invoke(db, base_request(run_id=run_id), provider_resolver=fake_resolver(fake))
    assert isinstance(resp, ModelResponse)
    return resp


def test_tokens_per_run_id_correct(db):
    run_a = make_run(db)
    run_b = make_run(db)
    _invoke_fake(db, run_a, input_tokens=11, output_tokens=22)
    _invoke_fake(db, run_b, input_tokens=13, output_tokens=29)

    totals_a = run_usage_totals(db, run_a)
    totals_b = run_usage_totals(db, run_b)
    # Keine Vermischung zwischen Runs; run_id IS NULL wird nie mitgezählt.
    assert totals_a["input_tokens"] == 11 and totals_a["output_tokens"] == 22
    assert totals_b["input_tokens"] == 13 and totals_b["output_tokens"] == 29
    assert totals_a["usage_record_count"] == 1
    assert totals_a["cost_status_counts"] == {"not_applicable": 1}
    assert totals_a["cost_chf_priced"] == 0.0


def test_latency_per_agent_task_from_agent_invocation(db):
    run_id = make_run(db)
    resp = _invoke_fake(db, run_id, input_tokens=5, output_tokens=6)
    # Latenz stammt aus AgentInvocation.latency_ms — explizit setzen und
    # zurücklesen, damit die Quelle der Aggregation bewiesen ist.
    inv = db.get(AgentInvocation, resp.invocation_id)
    inv.latency_ms = 137
    db.flush()

    rows = usage_by_agent_task(db, run_id)
    assert len(rows) == 1
    row = rows[0]
    assert row["agent_task"] == "A1.project_fact_extraction"
    assert row["invocation_count"] == 1
    assert row["input_tokens"] == 5 and row["output_tokens"] == 6
    assert row["avg_latency_ms"] == 137.0
    assert row["max_latency_ms"] == 137
    assert row["cost_statuses"] == ["not_applicable"]
    assert row["cost_chf_priced"] == 0.0


def test_cost_sum_ignores_unknown_and_not_applicable(db):
    run_id = make_run(db)
    for status, chf in (
        ("priced", 1.5),
        ("priced", 0.5),
        ("unknown_price", 99.0),
        ("not_applicable", 42.0),
    ):
        db.add(
            UsageRecord(
                usage_record_id=str(uuid.uuid4()),
                run_id=run_id,
                workspace_id=WS,
                cost_chf=chf,
                cost_status=status,
            )
        )
    db.flush()
    totals = run_usage_totals(db, run_id)
    assert totals["cost_chf_priced"] == pytest.approx(2.0)
    assert totals["cost_status_counts"] == {
        "not_applicable": 1, "priced": 2, "unknown_price": 1,
    }


def test_tool_invocation_count_per_research_task_without_new_table(db):
    task_id = "rt-" + uuid.uuid4().hex[:8]
    record_tool(
        db, workspace_id=WS, research_task_id=task_id, tool_id="web_search",
        caller="research_executor", input_hash="h1", output_hash=None,
        status="running",
    )
    record_tool(
        db, workspace_id=WS, research_task_id=task_id, tool_id="web_search",
        caller="research_executor", input_hash="h1", output_hash="h2",
        status="succeeded", latency_ms=42,
    )
    db.flush()
    usage = tool_usage_by_research_task(db, task_id)
    tool = usage["by_tool"]["web_search"]
    # Credits nativ = gezählte Zeilen, identisch zur Guard-Semantik
    # (running + succeeded zählen beide).
    assert tool["rows_by_status"] == {"running": 1, "succeeded": 1}
    assert tool["credits_native"] == 2


def test_data_mode_derivation_matrix():
    assert derive_data_mode(ai_eval_mode="off", origin="synthetic") == "fake_test"
    assert derive_data_mode(ai_eval_mode="real", origin="synthetic") == "synthetic_eval"
    assert derive_data_mode(ai_eval_mode="real", origin="anonymized") == "anonymized_eval"
    assert derive_data_mode(ai_eval_mode="off", origin="real_project") == "real_project"
    assert derive_data_mode(ai_eval_mode="real", origin="real_project") == "real_project"
    assert derive_data_mode(ai_eval_mode="off", origin=None) == "fake_test"
    assert set(DATA_MODES) == {
        "fake_test", "synthetic_eval", "anonymized_eval", "real_project",
    }


def test_summary_gains_usage_and_data_mode_keys_schema_kept(db):
    run_id = make_run(db)
    _invoke_fake(db, run_id, input_tokens=7, output_tokens=9)
    run = db.get(AnalysisRun, run_id)
    summary = build_evaluation_summary(
        db, run, generated_at="2026-07-08T00:00:00+00:00"
    )
    # Additiv, Schema unverändert.
    assert summary["schema"] == "evaluation-run-summary-1"
    assert summary["data_mode"] == "fake_test"
    assert summary["usage"]["input_tokens"] == 7
    assert summary["usage"]["output_tokens"] == 9
    assert summary["usage"]["cost_status_counts"] == {"not_applicable": 1}
    assert summary["usage"]["cost_chf_priced"] == 0.0
    assert summary["usage"]["price_table_version"]
    # estimated_cost bleibt der alte, ehrliche Platzhalter.
    assert summary["estimated_cost"]["placeholder"] is True
    md = render_markdown(summary)
    assert "| data_mode | fake_test |" in md
    assert "| usage.input_tokens | 7 |" in md
