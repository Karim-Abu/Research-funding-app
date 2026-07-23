"""Final-Acceptance-Slice: Der Suggestion-Read-Pfad projiziert gespeicherte
Beleg-Zitate (`evidence_anchor_ids`) aus den persistierten EvidenceAnchor-Zeilen
in `suggestion.evidence` — Quelle, Fundstelle (Seite/Abschnitt), Ausschnitt und
Verifikationsstatus werden damit auch für gespeicherte Vorschläge sichtbar.

Autorisierter Read-only-Slice (FINAL_ACCEPTANCE_BLOCKED_EVIDENCE_READ_CONTRACT):
keine neue Evidenzlogik, keine Migration; nur geprüfte Anker (exact_verified/
human_verified) in Zitierreihenfolge, Workspace-/Run-/Projekt-isoliert.

Der Fake-Provider zitiert selbst nie Anker; die Zitate werden hier als
Test-Arrangement direkt in der DB gesetzt (die Projektion liest nur
persistierte Zeilen — die Herkunft des Zitats ist für den Slice irrelevant).
"""
from __future__ import annotations

import json

import pytest

from app.config.settings import get_settings
from app.contracts.draft import SuggestionEvidenceItem
from app.db.models import DraftSuggestion, EvidenceAnchor
from app.db.session import SessionLocal
from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    DEMO_WS,
    TEST_WS,
    login,
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


def _add_anchor(
    db,
    *,
    anchor_id: str,
    workspace_id: str = DEMO_WS,
    run_id: str | None = None,
    project_id: str | None = None,
    verification_status: str = "exact_verified",
    quote: str = "Das Konsortium umfasst einen Schweizer Umsetzungspartner.",
    source_name: str = "Quelle-A.pdf",
    page: int | None = None,
    section: str | None = None,
) -> None:
    db.add(
        EvidenceAnchor(
            anchor_id=anchor_id,
            workspace_id=workspace_id,
            run_id=run_id,
            project_id=project_id,
            source_version_id=f"sv-{anchor_id}",
            source_id=f"src-{anchor_id}",
            source_name=source_name,
            source_type="pdf",
            fragment_id=f"frag-{anchor_id}",
            quote=quote,
            quote_hash=f"hash-{anchor_id}",
            page=page,
            section=section,
            normalizer_version="v1",
            verification_status=verification_status,
        )
    )


def _cite(suggestion_id: str, anchor_ids: list[str]) -> None:
    db = SessionLocal()
    try:
        suggestion = db.get(DraftSuggestion, suggestion_id)
        assert suggestion is not None
        suggestion.evidence_anchor_ids = list(anchor_ids)
        db.commit()
    finally:
        db.close()


def test_stored_citations_are_projected_with_details(client, fake_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, _svid = cloud_project_with_source(client, csrf)
    run_id = cloud_run(client, csrf, project_id, _svid)
    suggestion = _get_suggestion(client, run_id)
    assert suggestion is not None

    db = SessionLocal()
    try:
        # Beide legitimen Scope-Arme: run-gebundener Anker + Projekt-Kontextanker.
        _add_anchor(
            db, anchor_id="fa-run", run_id=run_id,
            verification_status="exact_verified", page=3,
            quote="Die Pilotlinie reduziert Ausschuss um 18 Prozent.",
            source_name="Projektplan.pdf",
        )
        _add_anchor(
            db, anchor_id="fa-project", project_id=project_id,
            verification_status="human_verified", section="4.2",
            quote="Der Marktzugang erfolgt ueber bestehende OEM-Partner.",
            source_name="Marktnotiz.pdf",
        )
        db.commit()
    finally:
        db.close()
    _cite(suggestion["suggestion_id"], ["fa-project", "fa-run"])

    stored = _get_suggestion(client, run_id)
    assert stored is not None
    evidence = stored["evidence"]
    # Zitierreihenfolge bleibt erhalten; beide Scope-Arme werden projiziert.
    assert [e["anchor_id"] for e in evidence] == ["fa-project", "fa-run"]
    first, second = evidence
    assert first["source_name"] == "Marktnotiz.pdf"
    assert first["section"] == "4.2"
    assert first["page"] is None
    assert first["verification_status"] == "human_verified"
    assert first["quote"] == "Der Marktzugang erfolgt ueber bestehende OEM-Partner."
    assert second["source_name"] == "Projektplan.pdf"
    assert second["page"] == 3
    assert second["verification_status"] == "exact_verified"
    for item in evidence:
        SuggestionEvidenceItem.model_validate(item)
    assert stored["proposal"]["used_anchor_ids"] == ["fa-project", "fa-run"]

    # Kein Leak: nur der Anker-Ausschnitt, kein Quelltext/Prompt-/Key-Material.
    raw = json.dumps(stored).lower()
    assert "api_key" not in raw
    assert "prompt_text" not in raw
    assert "normalized_text" not in raw


def test_unverified_and_rejected_citations_are_not_projected(client, fake_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, _svid = cloud_project_with_source(client, csrf)
    run_id = cloud_run(client, csrf, project_id, _svid)
    suggestion = _get_suggestion(client, run_id)

    db = SessionLocal()
    try:
        _add_anchor(db, anchor_id="fa-unverified", run_id=run_id,
                    verification_status="unverified")
        _add_anchor(db, anchor_id="fa-rejected", run_id=run_id,
                    verification_status="rejected")
        db.commit()
    finally:
        db.close()
    _cite(suggestion["suggestion_id"], ["fa-unverified", "fa-rejected"])

    stored = _get_suggestion(client, run_id)
    assert stored["evidence"] == []
    # Ehrliche Divergenz: die rohe Zitatliste bleibt im Proposal sichtbar.
    assert stored["proposal"]["used_anchor_ids"] == ["fa-unverified", "fa-rejected"]


def test_projection_is_workspace_and_scope_isolated(client, fake_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, _svid = cloud_project_with_source(client, csrf)
    run_id = cloud_run(client, csrf, project_id, _svid)
    suggestion = _get_suggestion(client, run_id)

    db = SessionLocal()
    try:
        # Fremder Workspace (gleiches Projekt) und fremdes Projekt (gleicher
        # Workspace) — beides darf nie projiziert werden.
        _add_anchor(db, anchor_id="fa-foreign-ws", workspace_id=TEST_WS,
                    project_id=project_id)
        _add_anchor(db, anchor_id="fa-foreign-project",
                    project_id="proj-other")
        db.commit()
    finally:
        db.close()
    _cite(suggestion["suggestion_id"], ["fa-foreign-ws", "fa-foreign-project"])

    stored = _get_suggestion(client, run_id)
    assert stored["evidence"] == []


def test_suggestion_without_citations_keeps_empty_evidence(client, fake_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id, _svid = cloud_project_with_source(client, csrf)
    run_id = cloud_run(client, csrf, project_id, _svid)

    stored = _get_suggestion(client, run_id)
    assert stored is not None
    assert stored["evidence"] == []
    assert stored["proposal"]["used_anchor_ids"] == []
