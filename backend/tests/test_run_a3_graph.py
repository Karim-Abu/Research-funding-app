"""A3 im normalen AnalysisRun (Graph-Anbindung) + Partial Success.

Ein Cloud-Fake-Run persistiert advisory A3-ReviewFindings (source="agent",
separat von den deterministischen Findings — A2 wird nie überschrieben).
Ein A3-Provider-Fehler lässt den Lauf «teilweise abgeschlossen»: Run-Status
completed, Phase quality_review = failed, A2-Vorschläge und Drafts intakt.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import critic_review
from app.agents.a3_review import A3_PROFILE_ID
from app.config.settings import get_settings
from app.db.models import (
    DraftSuggestion,
    PortalFieldDraft,
    ReviewFinding,
    RunPhase,
)
from app.db.session import SessionLocal
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, login
from tests.run_graph_helpers import cloud_project_with_source, cloud_run


@pytest.fixture
def fake_provider(monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_fake_provider", True)


def _agent_findings(run_id):
    db = SessionLocal()
    try:
        return list(
            db.scalars(
                select(ReviewFinding).where(
                    ReviewFinding.run_id == run_id,
                    ReviewFinding.source == "agent",
                )
            )
        )
    finally:
        db.close()


def _phase(run_id, key):
    db = SessionLocal()
    try:
        return db.scalar(
            select(RunPhase).where(
                RunPhase.run_id == run_id, RunPhase.phase_key == key
            )
        )
    finally:
        db.close()


def test_cloud_fake_run_persists_a3_findings(client, fake_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = cloud_project_with_source(client, csrf)
    run_id = cloud_run(client, csrf, project_id, svid)

    findings = _agent_findings(run_id)
    assert findings, "cloud fake run must persist advisory A3 findings"
    assert all(f.profile_id == A3_PROFILE_ID for f in findings)
    assert all(f.advisory for f in findings if f.severity != "blocker")

    db = SessionLocal()
    try:
        deterministic = db.scalar(
            select(ReviewFinding.finding_id).where(
                ReviewFinding.run_id == run_id,
                ReviewFinding.source == "deterministic_review",
            )
        )
        assert deterministic is not None, (
            "deterministic findings run alongside A3, never replaced"
        )
    finally:
        db.close()

    phase = _phase(run_id, "quality_review")
    assert phase.status == "succeeded"
    assert phase.detail["a3_status"] == "succeeded"
    assert phase.detail["agent_findings"] == len(findings)


def test_a3_failure_yields_partial_success(client, fake_provider, monkeypatch):
    """Anforderung 11: Bei A3-Fehler bleiben die A2-Drafts erhalten und der
    Lauf endet «teilweise abgeschlossen — Kritik fehlgeschlagen» (completed +
    Phase failed), nicht komplett leer."""
    from app.agents.providers import FakeProvider

    monkeypatch.setattr(
        critic_review, "_fake_resolver",
        lambda _ctx: (lambda _route: FakeProvider(mode="error")),
    )
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = cloud_project_with_source(client, csrf)
    run_id = cloud_run(client, csrf, project_id, svid)  # asserts completed

    # Keine Agent-Findings, aber A2-Vorschläge und Drafts sind intakt.
    assert _agent_findings(run_id) == []
    db = SessionLocal()
    try:
        suggestions = list(
            db.scalars(
                select(DraftSuggestion).where(DraftSuggestion.run_id == run_id)
            )
        )
        drafts = list(
            db.scalars(
                select(PortalFieldDraft).where(PortalFieldDraft.run_id == run_id)
            )
        )
    finally:
        db.close()
    assert suggestions and all(s.status == "proposed" for s in suggestions)
    assert drafts and all(d.current_version_id for d in drafts)

    phase = _phase(run_id, "quality_review")
    assert phase.status == "failed"
    assert phase.error_code
    assert phase.detail["a3_status"] in ("failed", "timed_out")


def test_deterministic_run_has_no_agent_findings(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    from tests.conftest import create_project
    from tests.run_graph_helpers import mut_headers

    project_id = create_project(client, csrf)
    res = client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={
            "name": "Src", "text": "Deterministic review content.",
            "data_classification": {
                "sensitivity": "public", "origin": "synthetic",
                "processing_mode": "deterministic_only",
                "web_research_mode": "off", "nda_applies": False,
            },
        },
        headers=mut_headers(csrf),
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
        headers=mut_headers(csrf),
    )
    run_id = res.json()["resource_id"]
    assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "completed"

    assert _agent_findings(run_id) == []
    phase = _phase(run_id, "quality_review")
    assert phase.status == "succeeded"
    assert phase.detail["a3_status"] == "skipped"
    assert phase.detail["a3_reason"] == "processing_mode_deterministic_only"
