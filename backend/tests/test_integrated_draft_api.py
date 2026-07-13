"""DEMO.1 — API-Tests für die Integrated-Draft-Demo-View.

Kein Netz, keine echten Provider-Calls: der POST läuft nur mit
``agent_fake_provider=True`` (sonst 503, ohne dass irgendetwas geschrieben wird); der
GET real ist eine reine Datei-Leseansicht über ein tmp-Verzeichnis. Prüft die
8-Felder-Struktur, Usage-Summary, Human-Review-Pflicht, CSRF-Schutz, das strukturelle
Strippen des ``artifact``-Teils (Canary) und No-Raw im Response-JSON.
"""
from __future__ import annotations

import json

import pytest

from app.config.settings import get_settings
from app.evaluation import integrated_draft_real as idr
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, login, unsafe_headers

CANARY_TEXT = "DEMO1_CANARY_ROHANTWORT_5X"
_EXPECTED_FIELDS = [
    "INTRO.APP.NAME", "INTRO.APP.NAME_EN", "INTRO.APP.ABSTRACT",
    "INTRO.APP.EXECUTIVE_SUMMARY", "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS",
    "VC.BUSINESS_TARGETS_MODEL.EDITOR", "SOL.INNOVATION_SOLUTION.EDITOR",
    "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION",
]


@pytest.fixture
def fake_provider(monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_fake_provider", True)


# --- POST /demo/integrated-draft ---------------------------------------------


def test_post_refuses_without_fake_provider(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = client.post("/api/v1/demo/integrated-draft", headers=unsafe_headers(csrf))
    assert res.status_code == 503
    assert res.json()["code"] == "ai_unavailable"


def test_post_requires_csrf(client, fake_provider):
    login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = client.post("/api/v1/demo/integrated-draft")  # kein CSRF/Origin-Header
    assert res.status_code == 403


def test_post_creates_demo_package(client, fake_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = client.post("/api/v1/demo/integrated-draft", headers=unsafe_headers(csrf))
    assert res.status_code == 200, res.text
    pkg = res.json()
    assert [f["field_id"] for f in pkg["fields"]] == _EXPECTED_FIELDS
    assert all(f["status"] for f in pkg["fields"])
    assert all(f["human_review_required"] is True for f in pkg["fields"])
    assert pkg["human_review_required"] is True
    assert pkg["provider_mode"] == "fake"
    us = pkg["usage_summary"]
    assert us["total_tokens"] == 0 and us["usage_record_count"] == 0
    assert us["cost_status_counts"] == {}
    assert pkg["research_summary"]["market"]["used"] is True
    assert pkg["research_summary"]["partner"]["used"] is True


def test_post_response_has_no_raw_prompts_or_keys(client, fake_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = client.post("/api/v1/demo/integrated-draft", headers=unsafe_headers(csrf))
    blob = json.dumps(res.json()).lower()
    assert "begin untrusted" not in blob
    assert "api_key" not in blob
    assert "system prompt" not in blob


# --- GET /demo/integrated-draft/real ------------------------------------------


def _fake_envelope(provider: str) -> dict:
    return {
        "report": {
            "provider": provider, "case_id": "F1", "project_id": "p1", "run_id": "r1",
            "created_at": "2026-07-10T00:00:00+00:00", "data_mode": "synthetic_eval",
            "price_table_version": "x",
            "fields": [{
                "field_id": "INTRO.APP.ABSTRACT", "field_label": "Abstract",
                "status": "missing_inputs", "provider": provider, "model": "model-x",
                "input_tokens": 10, "output_tokens": 20, "total_tokens": 30,
                "latency_ms": 100, "cost_status": "unknown_price",
                "usage_record_id": "usg-1", "llm_calls": 1, "missing_inputs_count": 1,
                "human_review_required": True,
                "suggestion_preview": "Kurzvorschau des Feldentwurfs.",
            }],
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
        "artifact": {"fields": [{
            "field_id": "INTRO.APP.ABSTRACT", "suggestion_text": CANARY_TEXT,
            "ai_proposal": {"raw": CANARY_TEXT}, "raw_outputs": [CANARY_TEXT],
        }]},
    }


def test_get_real_strips_artifact_and_returns_report(client, tmp_path, monkeypatch):
    (tmp_path / "openai.json").write_text(
        json.dumps(_fake_envelope("openai")), encoding="utf-8"
    )
    monkeypatch.setattr(idr, "_default_results_dir", lambda: tmp_path)
    login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = client.get("/api/v1/demo/integrated-draft/real")
    assert res.status_code == 200
    data = res.json()
    assert set(data["providers"]) == {"openai"}
    report = data["providers"]["openai"]
    assert report["fields"][0]["suggestion_preview"] == "Kurzvorschau des Feldentwurfs."
    assert report["usage_summary"]["total_tokens"] == 30
    # Der artifact-Teil (Canary) wird strukturell nie gesendet.
    assert CANARY_TEXT not in res.text
    assert "raw_outputs" not in res.text


def test_get_real_empty_dir_returns_empty_providers(client, tmp_path, monkeypatch):
    monkeypatch.setattr(idr, "_default_results_dir", lambda: tmp_path)
    login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = client.get("/api/v1/demo/integrated-draft/real")
    assert res.status_code == 200
    assert res.json() == {"providers": {}}


def test_get_real_requires_session(client, tmp_path, monkeypatch):
    monkeypatch.setattr(idr, "_default_results_dir", lambda: tmp_path)
    res = client.get("/api/v1/demo/integrated-draft/real")
    assert res.status_code == 401
