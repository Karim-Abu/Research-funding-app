"""EVAL.1 — Smoke-Pipeline: No-Raw-Canary, Pflicht-Disclaimer, CI-Guards.

Fake-Provider only. Der Canary-Marker wird in Projekttitel/-beschreibung
injiziert und darf in keiner Metering-/Log-/Audit-/Report-Fläche auftauchen
(Pattern: tests/test_import_no_raw_logging.py).
"""
from __future__ import annotations

import json
import logging
import uuid

import pytest
from sqlalchemy import select

from app.db.models import (
    AgentInvocation,
    AsyncOperation,
    AuditEvent,
    ControlResult,
    ResearchTask,
    ToolInvocation,
    UsageRecord,
)
from app.db.session import SessionLocal
from app.evaluation.usage_smoke import SmokeFailure, main, render_report, run_case_f1

CANARY = "EVAL1_CANARY_PROJEKTIDEE_9Z7Q"


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _metering_blob(id_prefix: str) -> str:
    """Alle Metering-/Audit-/Control-/Operation-Flächen als ein JSON-Blob."""
    with SessionLocal() as db:
        usage = db.scalars(select(UsageRecord)).all()
        agents = db.scalars(select(AgentInvocation)).all()
        tools = db.scalars(select(ToolInvocation)).all()
        audits = db.scalars(select(AuditEvent)).all()
        controls = db.scalars(select(ControlResult)).all()
        operations = db.scalars(select(AsyncOperation)).all()
        tasks = db.scalars(
            select(ResearchTask).where(
                ResearchTask.research_task_id.like(f"{id_prefix}%")
            )
        ).all()
    return json.dumps(
        [
            [u.provider, u.model, u.cost_status, u.price_version] for u in usage
        ]
        + [
            [a.profile_id, a.input_hash, a.output_hash, a.safe_error_detail,
             a.error_code, a.model_route]
            for a in agents
        ]
        + [[t.tool_id, t.caller, t.input_hash, t.output_hash, t.error_class]
           for t in tools]
        + [[a.action, a.detail] for a in audits]
        + [[c.control_id, c.detail] for c in controls]
        + [[o.result, o.error, o.status] for o in operations]
        + [[t.query_text, t.safe_error_detail] for t in tasks],
        ensure_ascii=False, default=str,
    )


def test_smoke_run_produces_records_and_report_without_canary(db, caplog, monkeypatch):
    from app.config.settings import get_settings

    # Settings-Restauration absichern, falls run_case_f1 intern abbricht.
    s = get_settings()
    monkeypatch.setattr(s, "web_research_enabled", s.web_research_enabled)
    monkeypatch.setattr(s, "web_research_fake_provider", s.web_research_fake_provider)

    caplog.set_level(logging.DEBUG)
    prefix = "eval1c-" + uuid.uuid4().hex[:6]
    result = run_case_f1(
        db,
        id_prefix=prefix,
        project_title=f"F1 {CANARY} Projekt",
        project_description=f"Beschreibung mit {CANARY} als vertraulicher Idee.",
    )

    # Messbare Records existieren (LLM + Web).
    assert len(result["runs"]) == 2
    for totals in result["runs"].values():
        assert totals["usage_record_count"] == 1
        assert totals["cost_status_counts"] == {"not_applicable": 1}
    assert result["web_provider"] == "fake"
    web_tool = result["web"]["by_tool"]["search_public_professional_sources"]
    assert web_tool["credits_native"] == 2  # running + succeeded (Guard-Semantik)

    # Canary erscheint in keiner Log-Fläche ...
    for record in caplog.records:
        assert CANARY not in record.getMessage(), (
            f"Canary leaked into log record: {record.name}"
        )
    # ... in keiner Metering-/Audit-/Control-/Operation-Fläche ...
    assert CANARY not in _metering_blob(prefix)
    # ... und nicht im gerenderten Report.
    report = render_report(result)
    assert CANARY not in report


def test_report_contains_mandatory_disclaimers(db):
    prefix = "eval1d-" + uuid.uuid4().hex[:6]
    result = run_case_f1(db, id_prefix=prefix, include_web_research=False)
    report = render_report(result)
    assert "keine echten API-Calls" in report
    assert "keine Kostenrechnung" in report
    assert "Fake-" in report
    assert "cost_status='priced'" in report
    assert "| data_mode" not in report  # data_mode als Abschnitt, nicht Tabelle
    assert "## data_mode: `fake_test`" in report
    # Latenz nie als exakter ms-Wert im committeten Report.
    assert "exact_latencies" not in report


def test_smoke_refuses_non_fake_provider():
    with pytest.raises(SystemExit) as exc:
        main(["--case", "F1", "--provider", "openai"])
    assert exc.value.code != 0


def test_smoke_refuses_unknown_case():
    with pytest.raises(SystemExit) as exc:
        main(["--case", "F2", "--provider", "fake"])
    assert exc.value.code != 0


def test_smoke_web_provider_is_fake_and_no_settings_leak(db):
    # CI-Guard: kein echtes Firecrawl — der Task-Provider ist der Fake, und
    # die Smoke-Funktion stellt die Settings-Flags wieder her.
    from app.config.settings import get_settings

    s = get_settings()
    before = (s.web_research_enabled, s.web_research_fake_provider)
    prefix = "eval1w-" + uuid.uuid4().hex[:6]
    result = run_case_f1(db, id_prefix=prefix)
    assert result["web_provider"] == "fake"
    with SessionLocal() as check:
        task = check.get(ResearchTask, f"{prefix}-task")
        assert task is not None and task.provider == "fake"
    assert (s.web_research_enabled, s.web_research_fake_provider) == before


def test_smoke_fails_closed_on_failed_web_task(db, monkeypatch):
    # Fail-closed: liefert der Web-Teil keinen Erfolg, bricht der Smoke ab
    # statt einen 0-Credit-Report zu schreiben.
    import app.evaluation.usage_smoke as smoke

    def _noop_executor(task_id, operation_id):
        return None  # Task bleibt "queued" → nie succeeded

    monkeypatch.setattr(smoke, "research_executor", _noop_executor)
    prefix = "eval1f-" + uuid.uuid4().hex[:6]
    with pytest.raises(SmokeFailure):
        run_case_f1(db, id_prefix=prefix)
