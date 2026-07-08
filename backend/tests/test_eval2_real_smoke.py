"""EVAL.2 — Real-Smoke-Runner: Guards, Call-Cap, Failure-Metering, Renderer.

Alles fake/unit — kein Netzwerk, keine echten Provider-Calls. Die Policy-
Matrix (D2-real blockiert, Eval-Mode-Gating, D3/UNKNOWN) ist bereits in
tests/test_provider_policy.py abgedeckt und wird hier nicht dupliziert.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.agents import cost_guard
from app.agents.gateway import SafeFailure, invoke
from app.agents.providers import FakeProvider
from app.agents.providers.base import ProviderUnavailable, ProviderUsage
from app.agents.registry import get_agent_registry
from app.config.settings import get_settings
from app.db.models import UsageRecord
from app.db.session import SessionLocal
from app.evaluation.real_smoke import (
    PROFILE,
    _SingleCallAdapter,
    guard_refusal,
    main,
    no_retry_registry,
    render_report,
    run_llm_case,
)
from tests.agent_helpers import base_request, make_run, per_route_resolver

CANARY_KEY = "EVAL2-CANARY-KEY-sk-000"
CANARY_TEXT = "EVAL2_CANARY_ROHANTWORT_7Q"


def _settings_stub(**overrides) -> SimpleNamespace:
    base = dict(
        ai_eval_mode="real",
        openai_api_key="x", anthropic_api_key="x", firecrawl_api_key="x",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


# --- Guards -----------------------------------------------------------------


def test_guard_refuses_in_ci():
    refusal = guard_refusal(
        provider="openai",
        env={"CI": "1", "RUN_REAL_PROVIDER_SMOKE": "true"},
        settings=_settings_stub(),
    )
    assert refusal is not None and "ci_environment" in refusal


def test_guard_requires_env_flag_and_eval_mode():
    assert "RUN_REAL_PROVIDER_SMOKE" in guard_refusal(
        provider="openai", env={}, settings=_settings_stub()
    )
    assert "AI_EVAL_MODE" in guard_refusal(
        provider="openai",
        env={"RUN_REAL_PROVIDER_SMOKE": "true"},
        settings=_settings_stub(ai_eval_mode="off"),
    )
    assert guard_refusal(
        provider="openai",
        env={"RUN_REAL_PROVIDER_SMOKE": "true"},
        settings=_settings_stub(),
    ) is None


def test_guard_missing_key_no_secret_leak():
    # Fremder Key ist gesetzt (Canary) — die Meldung für den fehlenden
    # openai-Key darf nur den Providernamen enthalten, nie Key-Material.
    refusal = guard_refusal(
        provider="openai",
        env={"RUN_REAL_PROVIDER_SMOKE": "true"},
        settings=_settings_stub(openai_api_key=None, anthropic_api_key=CANARY_KEY),
    )
    assert refusal is not None
    assert "provider_unavailable" in refusal and "openai" in refusal
    assert CANARY_KEY not in refusal


def test_main_missing_key_exits_cleanly(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("RUN_REAL_PROVIDER_SMOKE", "true")
    s = get_settings()
    monkeypatch.setattr(s, "ai_eval_mode", "real")
    # Keys IMMER explizit patchen — nie auf den .env-Zustand vertrauen
    # (nach Owner-Befüllung enthielte .env echte Keys).
    monkeypatch.setattr(s, "openai_api_key", None)
    rc = main([
        "--case", "F1", "--provider", "openai",
        "--results-dir", str(tmp_path), "--out", str(tmp_path / "r.md"),
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "provider_unavailable" in err
    assert not (tmp_path / "r.md").exists()


def test_main_refuses_second_run_per_provider(monkeypatch, tmp_path):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("RUN_REAL_PROVIDER_SMOKE", "true")
    s = get_settings()
    monkeypatch.setattr(s, "ai_eval_mode", "real")
    monkeypatch.setattr(s, "openai_api_key", "dummy-guard-pass")
    (tmp_path / "openai.json").write_text("{}", encoding="utf-8")
    rc = main([
        "--case", "F1", "--provider", "openai",
        "--results-dir", str(tmp_path), "--out", str(tmp_path / "r.md"),
    ])
    # Abbruch VOR jeder Adapter-Konstruktion (Exists-Check liegt vor dem Smoke).
    assert rc == 2
    assert not (tmp_path / "r.md").exists()


# --- Call-Cap / Registry-Kopie ----------------------------------------------


def test_single_call_adapter_caps_and_forwards():
    proxy = _SingleCallAdapter(FakeProvider())
    assert proxy.name == "fake"
    assert proxy.available() is True
    from app.agents.providers.base import ProviderRequest

    req = ProviderRequest(
        model_id="x", prompt="p", output_schema_id="ProjectFactExtractionResult@v1",
        timeout_seconds=1,
    )
    proxy.generate(req)
    assert proxy.calls == 1
    with pytest.raises(ProviderUnavailable):
        proxy.generate(req)


def test_no_retry_registry_only_patches_a1():
    patched = no_retry_registry()
    assert cost_guard.max_retries(patched.profile(PROFILE)) == 0
    # Original (lru-gecacht) bleibt unangetastet; Routen identisch.
    original = get_agent_registry()
    assert cost_guard.max_retries(original.profile(PROFILE)) == 1
    assert patched.model_routes == original.model_routes
    assert set(patched.profiles) == set(original.profiles)


# --- Failure-Path-Metering (Gateway-Diff) -----------------------------------


def test_schema_failure_with_run_id_writes_usage_record(db):
    run_id = make_run(db)
    fake = FakeProvider(
        mode="malformed", usage=ProviderUsage(input_tokens=7, output_tokens=9)
    )
    resp = invoke(
        db,
        base_request(run_id=run_id),
        provider_resolver=per_route_resolver({"anthropic_direct": fake}),
    )
    assert isinstance(resp, SafeFailure) and resp.status == "failed"
    records = db.scalars(
        select(UsageRecord).where(UsageRecord.run_id == run_id)
    ).all()
    # Genau 1 Failure-Record; Tokens über beide Versuche akkumuliert
    # (Contract max_retries=1 ⇒ 2 generate-Calls à 7/9).
    assert len(records) == 1
    assert records[0].input_tokens == 14 and records[0].output_tokens == 18
    assert records[0].cost_status == "not_applicable"  # fake-served
    assert records[0].price_version is None


def test_schema_failure_without_run_id_writes_nothing(db):
    before = db.scalar(select(func.count(UsageRecord.usage_record_id))) or 0
    resp = invoke(
        db,
        base_request(),  # kein run_id
        provider_resolver=per_route_resolver(
            {"anthropic_direct": FakeProvider(mode="malformed")}
        ),
    )
    assert isinstance(resp, SafeFailure)
    after = db.scalar(select(func.count(UsageRecord.usage_record_id))) or 0
    assert after == before


def test_run_llm_case_with_fake_adapter_meters_schema_failure(db, monkeypatch):
    # Ganzer Runner-Fluss ohne Netz: Fake-Adapter liefert Schema-invaliden
    # Output ⇒ dokumentiertes failed-Ergebnis MIT gemeterten Tokens.
    s = get_settings()
    monkeypatch.setattr(s, "ai_eval_mode", "real")
    result = run_llm_case(db, "anthropic", adapter=FakeProvider(mode="malformed"))
    r = result["report"]
    assert r["provider"] == "anthropic"
    assert r["status"] == "failed"
    # Modell des GEMETERTEN Calls (UsageRecord), nicht die zuletzt vom
    # Gateway versuchte Fallback-Route.
    assert r["model"] == "claude-haiku-4-5-20251001"
    assert r["llm_calls"] == 1  # no_retry_registry: kein 2. Versuch
    assert r["usage_record_count"] == 1
    assert r["total_tokens"] == 30  # FakeProvider-Default 10/20
    assert r["cost_status_counts"] == {"not_applicable": 1}
    assert r["data_mode"] == "synthetic_eval"
    assert result["artifact"]["llm_output"] is None


# --- Renderer / No-Raw -------------------------------------------------------


def _llm_result(provider: str) -> dict:
    return {
        "report": {
            "provider": provider, "kind": "llm", "route_provider": "x",
            "model": "m", "data_mode": "synthetic_eval", "status": "failed",
            "error_code": "agent_invocation_failed", "llm_calls": 1,
            "latency_ms": 1234, "input_tokens": 100, "output_tokens": 50,
            "total_tokens": 150, "usage_record_count": 1,
            "cost_status_counts": {"unknown_price": 1}, "cost_chf_priced": 0.0,
            "price_table_version": "x",
        },
        "artifact": {"llm_output": {"raw": CANARY_TEXT}, "safe_detail": CANARY_TEXT},
    }


def test_renderer_no_canary_and_mandatory_notes():
    report = render_report(
        {"openai": _llm_result("openai"), "anthropic": None, "firecrawl": None},
        generated_at="2026-07-08",
    )
    # Rohoutputs (artifact.*) erscheinen nie im Report.
    assert CANARY_TEXT not in report
    # Pflichthinweise.
    assert "synthetic_eval" in report
    assert "keine" in report and "D2" in report
    assert "Azure ist NICHT Teil dieses Smoke-Tests" in report
    assert "Keine Rohprompts" in report
    # Fehlende Provider als ausstehend markiert.
    assert report.count("**ausstehend**") == 2
    # unknown_price wird nie als CHF-Summe ausgewiesen.
    assert "nie als 0 CHF lesen" in report
    assert "CHF (nur priced summiert)" not in report


def test_renderer_shows_priced_sum_only_when_priced():
    result = _llm_result("openai")
    result["report"]["cost_status_counts"] = {"priced": 1}
    result["report"]["cost_chf_priced"] = 0.42
    report = render_report(
        {"openai": result, "anthropic": None, "firecrawl": None},
        generated_at="2026-07-08",
    )
    assert "0.42 CHF (nur priced summiert)" in report
