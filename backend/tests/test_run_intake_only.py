"""Intake-only-Projekte (0 Dateien) als gültiger versionierter Run-Input.

Der Lauf startet ohne Quellen (test_runs deckt den API-Pfad); hier: der
A1-Kontext enthält die strukturierte Projektbeschreibung aus dem
eingefrorenen RunProjectSnapshot — datenminimiert (Titel, Beschreibung,
Partnerzahlen; keine Partnernamen).
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.agents.context import assemble_a1_context
from app.db.models import AnalysisRun, ControlResult, Partner
from app.db.session import SessionLocal
from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    create_project,
    login,
    unsafe_headers,
)


def _mut(csrf):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = uuid.uuid4().hex
    return headers


def _intake_only_run(client, csrf, project_id) -> str:
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
    return run_id


def test_a1_context_contains_intake_description(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf, title="Intake Only Project")
    # Partner vor dem Run anlegen — der Snapshot friert sie mit ein.
    res = client.post(
        f"/api/v1/projects/{project_id}/partners",
        json={"name": "Geheim AG", "partner_type": "implementation_partner"},
        headers=_mut(csrf),
    )
    assert res.status_code == 201, res.text
    run_id = _intake_only_run(client, csrf, project_id)

    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        ctx = assemble_a1_context(db, run, max_fragments=80)
    finally:
        db.rollback()
        db.close()

    # Der versionierte Intake-Input steht als eigener untrusted Block im
    # Kontext — auch ohne eine einzige Datei/Quelle.
    assert "structured_project_description" in ctx.context_text
    assert "Intake Only Project" in ctx.context_text
    assert "A test innovation project." in ctx.context_text
    # Datenminimierung: Partnerzahlen ja, Partnernamen nie.
    assert "implementation_partner" in ctx.context_text
    assert "Geheim AG" not in ctx.context_text
    assert ctx.fragment_blocks == []
    assert ctx.context_hash
    assert ctx.meta["project_description_chars"] > 0


def test_intake_only_snapshot_control_passes(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    _intake_only_run(client, csrf, project_id)

    db = SessionLocal()
    try:
        # prepare_run schreibt zusätzlich ein detail-loses run.source_snapshot-
        # Control — relevant ist das Graph-Control mit dem Snapshot-Detail.
        controls = list(
            db.scalars(
                select(ControlResult).where(
                    ControlResult.project_id == project_id,
                    ControlResult.control_id == "run.source_snapshot",
                    ControlResult.detail.like("frozen_versions%"),
                )
            )
        )
    finally:
        db.close()
    assert controls, "graph snapshot control missing"
    assert all(c.status == "passed" for c in controls)
    assert any(
        "frozen_versions=0 intake_description=present" == c.detail
        for c in controls
    )


def test_partner_only_never_leaks_names_into_context(client):
    """Regressionsschutz für die Datenminimierung des Beschreibungs-Blocks."""
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    for name in ("Vertraulich GmbH", "NDA Partner AG"):
        res = client.post(
            f"/api/v1/projects/{project_id}/partners",
            json={"name": name, "partner_type": "research_partner"},
            headers=_mut(csrf),
        )
        assert res.status_code == 201, res.text
    run_id = _intake_only_run(client, csrf, project_id)

    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        ctx = assemble_a1_context(db, run, max_fragments=80)
        partners = list(
            db.scalars(select(Partner).where(Partner.project_id == project_id))
        )
    finally:
        db.rollback()
        db.close()
    assert len(partners) == 2
    assert "2× research_partner" in ctx.context_text
    assert "Vertraulich GmbH" not in ctx.context_text
    assert "NDA Partner AG" not in ctx.context_text
