"""A2 im normalen AnalysisRun (Graph-Anbindung).

Beweist über die echte API (TestClient führt den Background-Executor aus):
ein Cloud-Fake-Run erzeugt advisory DraftSuggestions für alle sechs
A2-Felder (inkl. BEIDER Intro-Felder — Registry-Limit 2), jede Suggestion
hängt an einer erfolgreichen AsyncOperation und ist über den unveränderten
updateField-Pfad annehmbar; nichts wird auto-übernommen; das Run-Budget-Gate
(max_llm_calls aus dem RunPolicySnapshot) wird durchgesetzt; deterministische
Läufe machen weiterhin 0 Provider-Calls.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents.a2_fields import A2_FIELD_PROFILES
from app.config.settings import get_settings
from app.db.models import (
    AgentInvocation,
    AsyncOperation,
    DraftSuggestion,
    DraftVersion,
    PortalFieldDraft,
    RunPhase,
)
from app.db.session import SessionLocal
from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    login,
    project_payload,
    unsafe_headers,
)
from tests.run_graph_helpers import (
    cloud_project_with_source as _cloud_project_with_source,
)
from tests.run_graph_helpers import cloud_run as _cloud_run
from tests.run_graph_helpers import mut_headers as _mut


@pytest.fixture
def fake_provider(monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_fake_provider", True)


def _suggestions(run_id):
    db = SessionLocal()
    try:
        return list(
            db.scalars(
                select(DraftSuggestion).where(DraftSuggestion.run_id == run_id)
            )
        )
    finally:
        db.close()


def _invocations(run_id):
    db = SessionLocal()
    try:
        return list(
            db.scalars(
                select(AgentInvocation).where(AgentInvocation.run_id == run_id)
            )
        )
    finally:
        db.close()


def test_cloud_fake_run_creates_suggestions_for_all_a2_fields(
    client, fake_provider
):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _cloud_project_with_source(client, csrf)
    run_id = _cloud_run(client, csrf, project_id, svid)

    suggestions = _suggestions(run_id)
    by_field = {s.field_id: s for s in suggestions}
    # Alle sechs A2-Felder — inklusive BEIDER Intro-Felder (Registry-Limit 2).
    assert set(by_field) == set(A2_FIELD_PROFILES)
    assert all(s.status == "proposed" for s in suggestions)

    # Graph-Beweis: A2 ist im normalen Lauf nicht mehr disabled.
    invs = _invocations(run_id)
    assert any(i.agent_id == "A2" for i in invs)
    assert {
        i.profile_id for i in invs if i.agent_id == "A2"
    } == set(A2_FIELD_PROFILES.values())

    # Jede Suggestion hängt an einer ECHTEN, erfolgreichen AsyncOperation —
    # Voraussetzung für den unveränderten Annahme-Pfad.
    db = SessionLocal()
    try:
        for s in suggestions:
            op = db.get(AsyncOperation, s.operation_id)
            assert op is not None and op.status == "succeeded"
            assert op.resource_type == "redraft"
            assert op.result and op.result["suggestion_id"] == s.suggestion_id
        phase = db.scalar(
            select(RunPhase).where(
                RunPhase.run_id == run_id, RunPhase.phase_key == "draft_fields"
            )
        )
        assert phase.status == "succeeded"
        assert phase.detail["suggestions_created"] == 16, phase.detail
        assert phase.detail["template_drafts"] >= len(A2_FIELD_PROFILES)
    finally:
        db.close()


def test_a2_suggestions_are_never_auto_applied(client, fake_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _cloud_project_with_source(client, csrf)
    run_id = _cloud_run(client, csrf, project_id, svid)

    db = SessionLocal()
    try:
        drafts = list(
            db.scalars(
                select(PortalFieldDraft).where(PortalFieldDraft.run_id == run_id)
            )
        )
        assert drafts, "run must have drafts"
        for draft in drafts:
            version = db.get(DraftVersion, draft.current_version_id)
            # Aktuelle Version bleibt die deterministische Basis — nie "agent",
            # solange kein Mensch angenommen hat.
            assert version.created_by in ("template", "import", "carried_over")
    finally:
        db.close()


def test_in_run_suggestion_acceptable_via_update_field(client, fake_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _cloud_project_with_source(client, csrf)
    run_id = _cloud_run(client, csrf, project_id, svid)

    suggestion = next(
        s for s in _suggestions(run_id)
        if s.field_id == "SOL.INNOVATION_SOLUTION.EDITOR"
    )
    res = client.patch(
        f"/api/v1/runs/{run_id}/fields/{suggestion.field_id}",
        json={
            "base_version_id": suggestion.base_version_id,
            "text": suggestion.suggested_text,
            "source_operation_id": suggestion.operation_id,
        },
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    # Explizite menschliche Annahme ⇒ neue Version created_by="agent".
    assert body["current_version"]["created_by"] == "agent"


def test_run_llm_budget_gate_limits_a2_calls(client, fake_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = _cloud_project_with_source(client, csrf)
    run_id = _cloud_run(client, csrf, project_id, svid, max_llm_calls=4)

    invs = _invocations(run_id)
    a2 = [i for i in invs if i.agent_id == "A2"]
    others = [i for i in invs if i.agent_id != "A2"]
    # Das Gate stoppt VOR jedem weiteren A2-Call, sobald das Run-Budget
    # erreicht ist: insgesamt nie mehr als max_llm_calls gezählte Calls.
    assert len(invs) <= 4
    assert len(a2) == 4 - len(others)
    assert 0 < len(a2) < len(A2_FIELD_PROFILES)

    db = SessionLocal()
    try:
        phase = db.scalar(
            select(RunPhase).where(
                RunPhase.run_id == run_id, RunPhase.phase_key == "draft_fields"
            )
        )
        assert phase.detail["budget_stop"] == "llm_budget_exhausted"
        assert phase.detail["suggestions_created"] == len(a2)
        assert phase.detail["fields_skipped"] > 0
    finally:
        db.close()


def test_deterministic_run_still_makes_no_provider_calls(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = client.post(
        "/api/v1/projects", json=project_payload("Det Project"),
        headers=_mut(csrf),
    )
    project_id = res.json()["project_id"]
    res = client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={
            "name": "Src", "text": "Deterministic content.",
            "data_classification": {
                "sensitivity": "public", "origin": "synthetic",
                "processing_mode": "deterministic_only",
                "web_research_mode": "off", "nda_applies": False,
            },
        },
        headers=_mut(csrf),
    )
    assert res.status_code == 201, res.text
    res = client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={
            "settings": {
                "processing_mode": "deterministic_only", "max_cost_chf": 0,
                "max_llm_calls": 0, "max_web_calls": 0,
            }
        },
        headers=_mut(csrf),
    )
    assert res.status_code == 202, res.text
    run_id = res.json()["resource_id"]
    assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "completed"

    assert _invocations(run_id) == []
    assert _suggestions(run_id) == []
    db = SessionLocal()
    try:
        phase = db.scalar(
            select(RunPhase).where(
                RunPhase.run_id == run_id, RunPhase.phase_key == "draft_fields"
            )
        )
        assert phase.status == "succeeded"
        assert phase.detail["suggestions_created"] == 0
        assert phase.detail["a2_reason"] == "mode_deterministic_only"
    finally:
        db.close()
