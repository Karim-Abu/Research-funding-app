"""Webrecherche im normalen AnalysisRun (Graph-Anbindung; Freigabepflicht R8).

max_web_calls wird durchgesetzt UND der Lauf führt nur menschlich freigegebene
Suchanfragen aus: > 0 auf einem öffentlichen Projekt mit verfügbarer Webrecherche
(Fake-Provider) und freigegebenen Queries führt den bestehenden Research-Vertikal
(Search Query Firewall → Executor) im Lauf aus; Ergebnisse bleiben Kandidaten.
0, nicht-öffentliche Klassen, fehlende Verfügbarkeit oder fehlende Freigaben ⇒
Phase ehrlich «skipped», kein Research-Call.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.config.settings import get_settings
from app.db.models import ResearchResult, ResearchTask, RunPhase, SearchQueryApproval
from app.db.session import SessionLocal
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, login, unsafe_headers
from tests.run_graph_helpers import (
    cloud_project_with_source,
    cloud_run,
    mut_headers,
)


def approve_market_queries(client, csrf, project_id) -> list[str]:
    """Plan-Endpoint aufrufen und alle vorgeschlagenen Queries freigeben (R8)."""
    res = client.post(
        f"/api/v1/projects/{project_id}/market-research/plan",
        json={}, headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200, res.text
    approval_ids = [q["approval_id"] for q in res.json()["queries"] if q["approval_id"]]
    assert approval_ids
    for approval_id in approval_ids:
        ok = client.post(
            f"/api/v1/search-query-approvals/{approval_id}/approve",
            headers=unsafe_headers(csrf),
        )
        assert ok.status_code == 200, ok.text
    return approval_ids


@pytest.fixture
def fake_providers(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "agent_fake_provider", True)
    monkeypatch.setattr(settings, "web_research_enabled", True)
    monkeypatch.setattr(settings, "web_research_fake_provider", True)


def _phase(run_id, key="web_research"):
    db = SessionLocal()
    try:
        return db.scalar(
            select(RunPhase).where(
                RunPhase.run_id == run_id, RunPhase.phase_key == key
            )
        )
    finally:
        db.close()


def _research_tasks(project_id):
    db = SessionLocal()
    try:
        return list(
            db.scalars(
                select(ResearchTask).where(ResearchTask.project_id == project_id)
            )
        )
    finally:
        db.close()


def _cloud_run_with_web(client, csrf, project_id, svid, *, max_web_calls):
    res = client.post(
        f"/api/v1/projects/{project_id}/processing-confirmations",
        json={
            "processing_mode": "cloud_assisted", "source_version_ids": [svid],
            "accepted_policy_version": "1.1.0",
            "purpose": "Textentwürfe vorbereiten", "expires_after_one_run": True,
        },
        headers=mut_headers(csrf),
    )
    assert res.status_code == 201, res.text
    confirmation_id = res.json()["confirmation_id"]
    res = client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={
            "settings": {
                "processing_mode": "cloud_assisted", "max_cost_chf": 5,
                "max_llm_calls": 25, "max_web_calls": max_web_calls,
                "source_version_ids": [svid],
                "internal_cloud_confirmation_id": confirmation_id,
            }
        },
        headers=mut_headers(csrf),
    )
    assert res.status_code == 202, res.text
    run_id = res.json()["resource_id"]
    assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "completed"
    return run_id


def test_public_run_with_web_budget_executes_capped_research(
    client, fake_providers
):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = cloud_project_with_source(client, csrf)
    approval_ids = approve_market_queries(client, csrf, project_id)
    run_id = _cloud_run_with_web(client, csrf, project_id, svid, max_web_calls=2)

    tasks = _research_tasks(project_id)
    # max_web_calls wird durchgesetzt: höchstens 2 Suchanfragen — obwohl mehr
    # Freigaben vorliegen.
    assert 0 < len(tasks) <= 2 < len(approval_ids)
    assert all(t.purpose == "market_comparison" for t in tasks)
    # Firewall-Provenienz liegt auf jeder Task (Chokepoint im Service), und jede
    # ausgeführte Query ist an ihre verbrauchte Freigabe gebunden (R8).
    assert all(t.firewall_data_class for t in tasks)
    assert all(t.firewall_approval_id in approval_ids for t in tasks)
    db = SessionLocal()
    try:
        for t in tasks:
            assert (
                db.get(SearchQueryApproval, t.firewall_approval_id).status == "used"
            )
    finally:
        db.close()

    db = SessionLocal()
    try:
        results = list(
            db.scalars(
                select(ResearchResult).where(
                    ResearchResult.research_task_id.in_(
                        [t.research_task_id for t in tasks]
                    )
                )
            )
        )
    finally:
        db.close()
    # Ergebnisse bleiben Kandidaten — nie automatisch Evidenz/Quelle.
    assert all(r.status == "candidate" for r in results)

    phase = _phase(run_id)
    assert phase.status == "succeeded"
    assert phase.detail["web_queries"] == len(tasks)


def test_no_approvals_skips_with_approval_required(client, fake_providers):
    """R8 Freigabepflicht: Web-Budget > 0, aber keine freigegebenen Suchanfragen ⇒
    Phase ehrlich «skipped» mit Grund approval_required, kein Research-Call."""
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = cloud_project_with_source(client, csrf)
    run_id = _cloud_run_with_web(client, csrf, project_id, svid, max_web_calls=2)

    assert _research_tasks(project_id) == []
    phase = _phase(run_id)
    assert phase.status == "skipped"
    assert phase.detail["reason"] == "approval_required"


def test_zero_web_budget_skips_research(client, fake_providers):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = cloud_project_with_source(client, csrf)
    run_id = cloud_run(client, csrf, project_id, svid)  # max_web_calls=0

    assert _research_tasks(project_id) == []
    phase = _phase(run_id)
    assert phase.status == "skipped"
    assert phase.detail["reason"] == "web_research_not_requested"


def test_web_research_unavailable_skips_honestly(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "agent_fake_provider", True)
    monkeypatch.setattr(settings, "web_research_enabled", False)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, svid = cloud_project_with_source(client, csrf)
    run_id = _cloud_run_with_web(client, csrf, project_id, svid, max_web_calls=3)

    assert _research_tasks(project_id) == []
    phase = _phase(run_id)
    assert phase.status == "skipped"
    assert phase.detail["reason"] == "web_research_unavailable"


def test_non_public_run_never_reaches_research(client, fake_providers):
    """Interne/vertrauliche Läufe überspringen die Recherche-Phase — die
    Search Query Firewall bleibt unangetastet und wird nie umgangen."""
    from tests.conftest import create_project

    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    res = client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={
            "name": "Src", "text": "Internal content.",
            "data_classification": {
                "sensitivity": "internal", "origin": "real_project",
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
                "max_llm_calls": 0, "max_web_calls": 3,
            }
        },
        headers=mut_headers(csrf),
    )
    assert res.status_code == 202, res.text
    run_id = res.json()["resource_id"]
    assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "completed"

    assert _research_tasks(project_id) == []
    phase = _phase(run_id)
    assert phase.status == "skipped"
    assert phase.detail["reason"] == "web_research_class_blocked"
