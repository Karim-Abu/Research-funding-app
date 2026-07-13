"""R5.9-REAL — hermetische Tests für den Real-Provider Integrated Draft Run.

Kein Netz, keine echten Provider-Calls: alles über FakeProvider bzw. reine Guard-/
Renderer-Logik. Prüft Manual-Mode-Refusals (rc 2, kein Report, kein Secret-Leak), dass
alle 6 A2-Felder über den erzwungenen Provider gemetert werden, dass confidential/
real_project-Daten den gesamten Lauf blockieren (SmokeFailure, 0 Provider-Calls,
unabhängig von API-Keys), und den No-Raw-Report-Canary.
"""
from __future__ import annotations

import json

import pytest

from app.agents import a2_fields
from app.config.settings import get_settings
from app.db.session import SessionLocal
from app.evaluation.integrated_draft_real import main, render_report, run_integrated_draft_real
from app.evaluation.usage_smoke import F1_SMOKE_CLASSIFICATION, SmokeFailure
from tests.a2_helpers import bundle, success_fake

ABSTRACT = "INTRO.APP.ABSTRACT"
EXEC = "INTRO.APP.EXECUTIVE_SUMMARY"
FIN = "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS"
VC = "VC.BUSINESS_TARGETS_MODEL.EDITOR"
SOL = "SOL.INNOVATION_SOLUTION.EDITOR"
HOURS = "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION"
A2_FIELDS = (ABSTRACT, EXEC, FIN, VC, SOL, HOURS)
CANARY_TEXT = "R5_9_REAL_CANARY_ROHANTWORT_9Z"
CANARY_KEY = "R5_9_REAL-CANARY-KEY-sk-000"


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


def _args(tmp_path, provider):
    return [
        "--provider", provider,
        "--results-dir", str(tmp_path), "--out", str(tmp_path / "r.md"),
    ]


def _adapters_for(field_ids) -> dict:
    """Registry-konforme Fake-Adapter je Feld (respektiert die Pflicht-Marker)."""
    adapters = {}
    for field_id in field_ids:
        config = a2_fields.resolve_field_config(field_id)
        adapters[field_id] = success_fake(
            bundle(field_id=field_id, suggested_text=config.fake_text)
        )
    return adapters


def _fake_result(provider: str = "openai") -> dict:
    field_row = {
        "field_id": ABSTRACT, "field_label": "Abstract", "status": "generated",
        "provider": provider, "model": "gpt-x", "input_tokens": 10, "output_tokens": 20,
        "total_tokens": 30, "latency_ms": 123, "cost_status": "unknown_price",
        "usage_record_id": "usg-1", "llm_calls": 1, "missing_inputs_count": 0,
        "human_review_required": True,
        "suggestion_preview": "Öffentliche Kurzfassung (Vorschau, kein Rohtext).",
    }
    return {
        "report": {
            "provider": provider, "case_id": "F1", "project_id": "p1", "run_id": "r1",
            "created_at": "2026-07-09T00:00:00+00:00", "data_mode": "synthetic_eval",
            "price_table_version": "x", "fields": [field_row],
            "usage_summary": {
                "input_tokens": 10, "output_tokens": 20, "total_tokens": 30,
                "usage_record_count": 1, "cost_status_counts": {"unknown_price": 1},
            },
            "research_summary": {
                "market": {"used": True, "candidates": 1, "imported_sources": 0},
                "partner": {"used": False, "candidates": 0, "imported_sources": 0},
            },
            "human_review_required": True,
        },
        "artifact": {
            "fields": [{
                "field_id": ABSTRACT, "suggestion_text": CANARY_TEXT,
                "ai_proposal": {"raw": CANARY_TEXT}, "raw_outputs": [CANARY_TEXT, CANARY_KEY],
            }],
        },
    }


# --- Manual-Mode: Runner verweigert ohne Flags/Key --------------------------


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


def test_main_refuses_missing_key_no_secret_leak(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("RUN_REAL_PROVIDER_SMOKE", "true")
    s = get_settings()
    monkeypatch.setattr(s, "openai_api_key", None)
    # Anthropic key present but irrelevant (openai was requested) — must never leak.
    monkeypatch.setattr(s, "anthropic_api_key", CANARY_KEY)
    assert main(_args(tmp_path, "openai")) == 2
    assert not (tmp_path / "r.md").exists()
    err = capsys.readouterr().err
    assert "provider_unavailable" in err and "openai" in err
    assert CANARY_KEY not in err


def test_main_skips_existing_artifact(monkeypatch, tmp_path):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("RUN_REAL_PROVIDER_SMOKE", "true")
    s = get_settings()
    monkeypatch.setattr(s, "openai_api_key", "dummy-guard-pass")
    (tmp_path / "openai.json").write_text(
        json.dumps(_fake_result("openai")), encoding="utf-8"
    )
    assert main(_args(tmp_path, "openai")) == 0
    assert (tmp_path / "r.md").exists()  # Report aus bestehendem Artefakt gerendert


# --- run_integrated_draft_real (FakeProvider) -------------------------------


def test_run_real_all_a2_fields_metered(db):
    result = run_integrated_draft_real(
        db, provider="anthropic", adapters=_adapters_for(A2_FIELDS)
    )
    r = result["report"]
    assert len(r["fields"]) == 8
    by_id = {f["field_id"]: f for f in r["fields"]}
    for field_id in A2_FIELDS:
        f = by_id[field_id]
        assert f["status"] == "generated"
        assert f["llm_calls"] == 1
        assert f["usage_record_id"]
        assert f["total_tokens"] and f["total_tokens"] > 0
        assert f["latency_ms"] is not None
        # Injizierter FakeProvider ⇒ adapter.name=="fake" ⇒ cost_status=not_applicable
        # (resolve_cost). Ein echter Provider-Call würde unknown_price liefern (leere
        # Preistabelle) — hier bewusst nicht real, siehe Modul-Docstring.
        assert f["cost_status"] == "not_applicable"
        assert f["human_review_required"] is True
    # Namensfelder bleiben deterministisch, unabhängig vom Provider.
    assert by_id["INTRO.APP.NAME"]["status"] == "deterministic"
    assert by_id["INTRO.APP.NAME_EN"]["status"] == "deterministic"
    # Rohtext/AIProposal nur im Artefakt, nie im Report.
    assert "suggestion_text" not in r["fields"][0]
    assert "ai_proposal" not in r["fields"][0]
    artifact_by_id = {f["field_id"]: f for f in result["artifact"]["fields"]}
    for field_id in A2_FIELDS:
        assert artifact_by_id[field_id]["suggestion_text"]
        assert artifact_by_id[field_id]["ai_proposal"] is not None


def test_run_real_blocks_confidential_real_project_data(db):
    # Vollständige Klassifikation (sonst schlägt spätere Contract-Validierung anderer
    # Tests auf der geteilten ws-demo-DB fehl) — nur sensitivity/origin überschrieben.
    classification = {
        **F1_SMOKE_CLASSIFICATION, "sensitivity": "confidential", "origin": "real_project",
    }
    # Keine Adapter injiziert — reale Provider-Klassen werden konstruiert (kein Netz beim
    # Konstruieren); der Data-Policy-Gate blockiert VOR jedem Adapter-Zugriff.
    with pytest.raises(SmokeFailure):
        run_integrated_draft_real(db, provider="openai", classification=classification)


# --- No-Raw-Report-Canary ----------------------------------------------------


def test_renderer_no_canary_and_mandatory_notes():
    report = render_report({"openai": _fake_result("openai")}, generated_at="2026-07-09")
    assert CANARY_TEXT not in report
    assert CANARY_KEY not in report
    assert "synthetic_eval" in report
    assert "Keine Förderzusage" in report
    assert "Human Review" in report
    assert "ResearchCandidates" in report
    assert "nie 0 CHF als gratis lesen" in report
    assert "unknown_price" in report


# --- R5.9b: provider-limitation Demo-Default note ---------------------------


def _field_row(field_id: str, status: str) -> dict:
    return {
        "field_id": field_id, "field_label": "Solution", "status": status,
        "provider": "x", "model": "m", "input_tokens": 10, "output_tokens": 20,
        "total_tokens": 30, "latency_ms": 100, "cost_status": "unknown_price",
        "usage_record_id": "usg-1", "llm_calls": 1, "missing_inputs_count": 0,
        "human_review_required": True, "suggestion_preview": "Vorschau.",
    }


def _envelope(provider: str, field_row: dict) -> dict:
    return {
        "report": {
            "provider": provider, "case_id": "F1", "project_id": "p1", "run_id": "r1",
            "created_at": "2026-07-09T00:00:00+00:00", "data_mode": "synthetic_eval",
            "price_table_version": "x", "fields": [field_row],
            "usage_summary": {
                "input_tokens": 10, "output_tokens": 20, "total_tokens": 30,
                "usage_record_count": 1, "cost_status_counts": {"unknown_price": 1},
            },
            "research_summary": {
                "market": {"used": True, "candidates": 1, "imported_sources": 0},
                "partner": {"used": False, "candidates": 0, "imported_sources": 0},
            },
            "human_review_required": True,
        },
        "artifact": {"fields": [{"field_id": field_row["field_id"], "suggestion_text": "x",
                                   "ai_proposal": None, "raw_outputs": []}]},
    }


def test_limitations_names_demo_default_when_other_provider_succeeds():
    results = {
        "openai": _envelope("openai", _field_row("SOL.INNOVATION_SOLUTION.EDITOR", "failed")),
        "anthropic": _envelope(
            "anthropic", _field_row("SOL.INNOVATION_SOLUTION.EDITOR", "missing_inputs")
        ),
    }
    report = render_report(results, generated_at="2026-07-09")
    assert "SOL.INNOVATION_SOLUTION.EDITOR" in report.split("## 7. Limitations")[1]
    assert "openai" in report.split("## 7. Limitations")[1]
    assert "anthropic" in report.split("## 7. Limitations")[1]
    assert "mandatory_structure_missing" in report
    assert "Demo-Default" in report


def test_limitations_flags_no_demo_default_when_all_providers_fail():
    results = {
        "openai": _envelope("openai", _field_row("SOL.INNOVATION_SOLUTION.EDITOR", "failed")),
    }
    report = render_report(results, generated_at="2026-07-09")
    assert "kein Demo-Default verfügbar" in report


def test_limitations_silent_when_no_field_failed():
    results = {"openai": _fake_result("openai")}
    report = render_report(results, generated_at="2026-07-09")
    assert "Demo-Default" not in report
