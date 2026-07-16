"""GET /runs/{id}/fields/{field}/suggestion — Read-only-Anzeige der im Lauf
erzeugten A2-Vorschläge (Owner-Entscheid: echte Operation + Read-Endpoint).

Der Endpoint liefert die proposed Suggestion zur AKTUELLEN Basisversion mit
demselben View wie das Redraft-Ergebnis (inkl. human_review_required=True);
nach Annahme oder Basiswechsel liefert er null. Kein Provider-Call, keine
Mutation, keine Prompts/Keys im Response.
"""
from __future__ import annotations

import json

import pytest

from app.config.settings import get_settings
from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    OUTSIDER_EMAIL,
    OUTSIDER_PASSWORD,
    login,
    unsafe_headers,
)
from tests.run_graph_helpers import cloud_project_with_source, cloud_run

SOL = "SOL.INNOVATION_SOLUTION.EDITOR"


@pytest.fixture
def fake_provider(monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_fake_provider", True)


def _get_suggestion(client, run_id, field_id=SOL):
    res = client.get(f"/api/v1/runs/{run_id}/fields/{field_id}/suggestions")
    assert res.status_code == 200, res.text
    suggestions = res.json()["suggestions"]
    if field_id == SOL:
        return next((s for s in suggestions if s["target_section"] == "4.2"), None)
    return suggestions[0] if suggestions else None


def test_in_run_suggestion_is_readable(client, fake_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = cloud_project_with_source(client, csrf)
    run_id = cloud_run(client, csrf, project_id, svid)

    suggestion = _get_suggestion(client, run_id)
    assert suggestion is not None
    assert suggestion["field_id"] == SOL
    assert suggestion["operation_id"]
    assert suggestion["base_version_id"]
    assert suggestion["suggested_text"]
    # Nie Auto-Übernahme; Fake-Demo bleibt explizit außerhalb des AIProposal-Felds.
    assert suggestion["proposal"]["human_review_required"] is True
    assert suggestion["generation_kind"] == "fake_demo"
    assert suggestion["ai_proposal"] is None

    # Kein Leak: weder Prompt- noch Key-Material im Response.
    raw = json.dumps(suggestion).lower()
    assert "api_key" not in raw
    assert "prompt_text" not in raw


def test_suggestion_gone_after_acceptance(client, fake_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = cloud_project_with_source(client, csrf)
    run_id = cloud_run(client, csrf, project_id, svid)

    suggestion = _get_suggestion(client, run_id)
    res = client.patch(
        f"/api/v1/runs/{run_id}/fields/{SOL}",
        json={
            "base_version_id": suggestion["base_version_id"],
            "text": suggestion["suggested_text"],
            "source_operation_id": suggestion["operation_id"],
        },
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200, res.text
    assert res.json()["current_version"]["created_by"] == "agent"
    # Angenommen + neue Basisversion ⇒ keine offene Suggestion mehr.
    assert _get_suggestion(client, run_id) is None


def test_field_without_suggestion_returns_null(client, fake_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = cloud_project_with_source(client, csrf)
    run_id = cloud_run(client, csrf, project_id, svid)
    # Deterministisches Namensfeld — nie ein A2-Feld.
    assert _get_suggestion(client, run_id, "INTRO.APP.NAME") is None


def test_suggestion_read_workspace_isolation(client, fake_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = cloud_project_with_source(client, csrf)
    run_id = cloud_run(client, csrf, project_id, svid)

    login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
    res = client.get(f"/api/v1/runs/{run_id}/fields/{SOL}/suggestions")
    assert res.status_code == 404
