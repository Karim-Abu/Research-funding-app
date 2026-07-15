"""R5.5-REAL — hermetische Tests für den A2-Feld-Real-Smoke.

Kein Netz, keine echten Provider-Calls: alles über FakeProvider bzw. die reine
Guard-/Renderer-Logik. Prüft Manual-Mode-Refusals (rc 2, kein Report), die
Status-Ableitung proposal_valid/schema_failed, das Schema-Failure-Metering und
den No-Raw-Report-Canary.
"""
from __future__ import annotations

import json

import pytest

from app.agents.providers.fake import FakeProvider
from app.config.settings import get_settings
from app.db.session import SessionLocal
from app.evaluation.field_real_smoke import main, render_report, run_field_case
from tests.a2_helpers import bundle, success_fake

ABSTRACT = "INTRO.APP.ABSTRACT"
EXEC = "INTRO.APP.EXECUTIVE_SUMMARY"
CANARY_TEXT = "R5_5_CANARY_ROHANTWORT_7Q"
CANARY_KEY = "R5_5-CANARY-KEY-sk-000"
ABSTRACT_TEXT = "Öffentlicher synthetischer Projektkontext."


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(autouse=True)
def _eval_mode(monkeypatch):
    # AI_EVAL_MODE=real ⇒ data_mode==synthetic_eval (Manual-Mode-Voraussetzung).
    monkeypatch.setattr(get_settings(), "ai_eval_mode", "real")


def _args(tmp_path, provider, fields="both"):
    return [
        "--provider", provider, "--fields", fields,
        "--results-dir", str(tmp_path), "--out", str(tmp_path / "r.md"),
    ]


# --- Manual-Mode: Runner verweigert ohne Flags/Key -------------------------


def test_main_refuses_in_ci(monkeypatch, tmp_path):
    monkeypatch.setenv("CI", "1")
    monkeypatch.setenv("RUN_REAL_PROVIDER_SMOKE", "true")
    assert main(_args(tmp_path, "openai")) == 2
    assert not (tmp_path / "r.md").exists()


def test_main_refuses_without_optin(monkeypatch, tmp_path):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("RUN_REAL_PROVIDER_SMOKE", raising=False)
    assert main(_args(tmp_path, "openai")) == 2
    assert not (tmp_path / "r.md").exists()


def test_main_refuses_missing_key(monkeypatch, tmp_path):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("RUN_REAL_PROVIDER_SMOKE", "true")
    s = get_settings()
    monkeypatch.setattr(s, "ai_eval_mode", "real")
    # Keys IMMER explizit patchen — nie auf den .env-Zustand vertrauen.
    monkeypatch.setattr(s, "openai_api_key", None)
    assert main(_args(tmp_path, "openai")) == 2
    assert not (tmp_path / "r.md").exists()


def test_main_skips_existing_artifact(monkeypatch, tmp_path):
    # Existierendes Artefakt ⇒ übersprungen, KEIN (realer) Provider-Call.
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("RUN_REAL_PROVIDER_SMOKE", "true")
    s = get_settings()
    monkeypatch.setattr(s, "ai_eval_mode", "real")
    monkeypatch.setattr(s, "openai_api_key", "dummy-guard-pass")
    (tmp_path / "abstract_openai.json").write_text(
        json.dumps(_fake_result(ABSTRACT, "openai")), encoding="utf-8"
    )
    assert main(_args(tmp_path, "openai", fields="abstract")) == 0
    assert (tmp_path / "r.md").exists()  # Report aus bestehendem Artefakt gerendert


# --- run_field_case (FakeProvider) -----------------------------------------


def test_field_case_valid_proposal(db):
    result = run_field_case(
        db, "anthropic", ABSTRACT,
        adapter=success_fake(bundle(field_id=ABSTRACT, suggested_text=ABSTRACT_TEXT)),
    )
    r = result["report"]
    assert r["status"] == "proposal_valid"
    assert r["failure_category"] == "none"
    assert r["field"] == ABSTRACT and r["provider"] == "anthropic"
    assert r["llm_calls"] == 1
    assert r["usage_record_count"] == 1 and r["usage_record_id"]
    assert r["human_review_required"] is True  # kein Auto-Accept
    assert r["data_mode"] == "synthetic_eval"
    assert r["suggested_text_length"] == len(ABSTRACT_TEXT)
    # Rohtext nur im git-ignorierten Artefakt, nie im Report.
    assert "suggested_text" not in r
    assert result["artifact"]["suggested_text"] == ABSTRACT_TEXT


def test_field_case_schema_failure_still_meters(db):
    result = run_field_case(db, "anthropic", EXEC, adapter=FakeProvider(mode="malformed"))
    r = result["report"]
    assert r["status"] == "schema_failed"
    # Ein UsageRecord je Schema-Versuch (max_retries=1 => zwei Versuche).
    assert r["usage_record_count"] == 2
    assert r["usage_record_id"]  # aus dem UsageRecord (nicht inv — nur bei Erfolg gekoppelt)
    assert r["total_tokens"] > 0
    assert r["human_review_required"] is None
    assert result["artifact"]["ai_proposal"] is None
    # R5.5b-Diagnose: Kategorie whitelist-safe (Schema-Feldnamen + Zählwert),
    # Rohantworten/Detail nur im git-ignorierten Artefakt.
    assert r["failure_category"] == (
        "missing_required:draft_candidates+placeholders; unknown_keys:1"
    )
    assert result["artifact"]["raw_outputs"] == ['{"unexpected_field": true}'] * 2
    assert "unexpected_field" in result["artifact"]["failure_detail"]
    assert "unexpected_field" not in json.dumps(r)  # Fremd-Key nie im Report-Teil


def test_field_case_not_json_category(db):
    result = run_field_case(
        db, "anthropic", EXEC, adapter=FakeProvider(mode="malformed_json")
    )
    r = result["report"]
    assert r["status"] == "schema_failed"
    assert r["failure_category"] == "not_json"


# --- No-Raw-Report-Canary ---------------------------------------------------


def _fake_result(field: str, provider: str) -> dict:
    return {
        "report": {
            "field": field, "provider": provider, "route_provider": "x", "model": "m",
            "data_mode": "synthetic_eval", "status": "schema_failed",
            "reason": "agent_invocation_failed", "failure_category": "not_json",
            "llm_calls": 2, "latency_ms": 1234,
            "input_tokens": 20, "output_tokens": 40, "total_tokens": 60,
            "usage_record_count": 1, "usage_record_id": "usg-1",
            "cost_status_counts": {"unknown_price": 1}, "cost_chf_priced": 0.0,
            "price_table_version": "x", "missing_inputs_count": 0,
            "human_review_required": None, "suggested_text_length": 0,
        },
        "artifact": {
            "suggested_text": CANARY_TEXT, "ai_proposal": {"raw": CANARY_TEXT},
            "reason": CANARY_TEXT, "raw_outputs": [CANARY_TEXT, CANARY_KEY],
            "failure_detail": CANARY_TEXT,
        },
    }


def test_renderer_no_canary_and_mandatory_notes():
    report = render_report(
        {"abstract_openai": _fake_result(ABSTRACT, "openai")}, generated_at="2026-07-09"
    )
    # Rohoutputs (artifact.*, inkl. R5.5b raw_outputs/failure_detail) nie im Report.
    assert CANARY_TEXT not in report
    assert CANARY_KEY not in report
    # R5.5b: Diagnose-Kategorie erscheint als eigene Whitelist-Zeile.
    assert "Schema-Fehlerkategorie" in report
    assert "not_json" in report
    # Pflichthinweise.
    assert "synthetic_eval" in report
    assert "D2" in report
    assert "Schema-Failure ist ein messbares Ergebnis" in report
    assert "nie als 0 CHF lesen" in report
    # 4 Zellen (2 Felder × 2 Provider) − 1 befüllt ⇒ 3 ausstehend.
    assert report.count("**ausstehend**") == 3
