"""Persistierte Run-Phasen: Recorder, GET /runs/{id}/phases, Reload-Sicherheit.

Deterministischer Lauf über die echte API (TestClient führt den Background-
Executor aus) — die sechs Nutzerphasen liegen danach terminal in der DB und
sind über den read-only Endpoint abrufbar (Reload zeigt denselben Stand).
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models import RunPhase
from app.db.session import SessionLocal
from app.runs.phases import PHASE_KEYS
from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    OUTSIDER_EMAIL,
    OUTSIDER_PASSWORD,
    VALID_CLASSIFICATION,
    create_project,
    login,
    unsafe_headers,
)


def _mut_headers(csrf):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = uuid.uuid4().hex
    return headers


def _run_deterministic(client, csrf, project_id) -> str:
    res = client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={
            "name": "Src",
            "text": "Phase test source content.",
            "data_classification": VALID_CLASSIFICATION,
        },
        headers=_mut_headers(csrf),
    )
    assert res.status_code == 201, res.text
    res = client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={
            "settings": {
                "processing_mode": "deterministic_only",
                "max_cost_chf": 0,
                "max_llm_calls": 0,
                "max_web_calls": 0,
            }
        },
        headers=_mut_headers(csrf),
    )
    assert res.status_code == 202, res.text
    run_id = res.json()["resource_id"]
    run = client.get(f"/api/v1/runs/{run_id}").json()
    assert run["status"] == "completed"
    return run_id


def test_deterministic_run_persists_all_phases(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    run_id = _run_deterministic(client, csrf, project_id)

    res = client.get(f"/api/v1/runs/{run_id}/phases")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["run_id"] == run_id
    assert body["run_status"] == "completed"
    by_key = {p["phase_key"]: p for p in body["phases"]}
    # Alle sechs Phasen vorhanden, in Katalog-Reihenfolge, terminal.
    assert [p["phase_key"] for p in body["phases"]] == list(PHASE_KEYS)
    for phase in body["phases"]:
        assert phase["status"] in ("succeeded", "failed", "skipped")
        assert phase["ended_at"] is not None

    assert by_key["prepare_documents"]["status"] == "succeeded"
    assert by_key["prepare_documents"]["detail"]["sources_frozen"] == 1
    assert by_key["detect_facts"]["status"] == "succeeded"
    assert by_key["formal_checks"]["status"] == "succeeded"
    assert {"blocker", "warning", "info"} <= set(
        by_key["formal_checks"]["detail"]
    )
    # Ohne Web-Budget wird die Recherche ehrlich übersprungen — kein Fehler.
    assert by_key["web_research"]["status"] == "skipped"
    assert by_key["web_research"]["detail"]["reason"]
    # Deterministisch: Template-Drafts entstehen, keine KI-Vorschläge.
    assert by_key["draft_fields"]["detail"]["suggestions_created"] == 0
    assert by_key["draft_fields"]["detail"]["template_drafts"] >= 1

    # Deterministischer Lauf: keine Agent-Kosten-Zusammenfassung erforderlich,
    # aber der technische Block existiert und nennt die Run-ID.
    assert body["technical"]["run_id"] == run_id
    assert body["technical"]["priced_cost_chf_total"] == 0.0


def test_phases_survive_session_rebuild(client):
    """Reload-Sicherheit: die Phasen liegen in der DB, nicht im Client —
    eine frische Session liest denselben Stand."""
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    run_id = _run_deterministic(client, csrf, project_id)

    db = SessionLocal()
    try:
        rows = list(
            db.scalars(select(RunPhase).where(RunPhase.run_id == run_id))
        )
    finally:
        db.close()
    assert {row.phase_key for row in rows} == set(PHASE_KEYS)
    assert all(row.status in ("succeeded", "failed", "skipped") for row in rows)

    # Zweiter (frischer) Abruf über die API liefert identische Statuswerte.
    first = client.get(f"/api/v1/runs/{run_id}/phases").json()
    second = client.get(f"/api/v1/runs/{run_id}/phases").json()
    assert first["phases"] == second["phases"]


def test_phases_workspace_isolation(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    run_id = _run_deterministic(client, csrf, project_id)

    login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
    res = client.get(f"/api/v1/runs/{run_id}/phases")
    assert res.status_code == 404
