"""createRedraft endpoint + accept/reject flow (Milestone 9D)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import field_drafting
from app.db.models import (
    AnalysisRun,
    DraftSuggestion,
    DraftVersion,
    PortalFieldDraft,
    ReviewApproval,
)
from app.db.session import SessionLocal
from tests.a2_helpers import (
    FIELD_ID,
    GOOD_TEXT,
    SECTION_GOOD_TEXT,
    TARGET_SECTION,
    build_run_with_draft,
    fake_resolver,
    section_bundle,
    success_fake,
)
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, login, unsafe_headers


def _setup(processing_mode="cloud_assisted"):
    db = SessionLocal()
    try:
        run, draft, base = build_run_with_draft(db, processing_mode=processing_mode)
        ids = (run.run_id, draft.draft_id, base)
        db.commit()
        return ids
    finally:
        db.close()


def _arm_fake(monkeypatch, payload=None):
    monkeypatch.setattr(
        field_drafting, "_PROVIDER_RESOLVER",
        fake_resolver(success_fake(payload or section_bundle())),
    )


def _create_redraft(client, csrf, run_id, field_id, base):
    return client.post(
        f"/api/v1/runs/{run_id}/fields/{field_id}/redrafts",
        json={"base_version_id": base, "target_section": TARGET_SECTION},
        headers=unsafe_headers(csrf),
    )


def test_create_redraft_async_then_result(client, monkeypatch):
    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert res.status_code == 202
    op_id = res.json()["operation_id"]
    op = client.get(f"/api/v1/operations/{op_id}").json()
    assert op["status"] == "succeeded"
    assert op["result"]["suggested_text"] == SECTION_GOOD_TEXT
    assert op["result"]["target_section"] == TARGET_SECTION
    assert op["result"]["generation_kind"] == "fake_demo"
    assert op["result"]["ai_proposal"] is None
    assert op["result"]["character_limit"] == 25000


def test_redraft_other_field_404(client, monkeypatch):
    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    # INTRO.APP.NAME is outside the A2 allow-list (Abstract/Exec Summary now in).
    res = _create_redraft(client, csrf, run_id, "INTRO.APP.NAME", base)
    assert res.status_code == 404


def test_redraft_stale_base_409(client, monkeypatch):
    run_id, _draft_id, _base = _setup()
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, FIELD_ID, "not-current")
    assert res.status_code == 409
    assert res.json()["code"] == "stale_base_version"


def test_redraft_deterministic_only_503(client, monkeypatch):
    run_id, _draft_id, base = _setup(processing_mode="deterministic_only")
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert res.status_code == 503
    body = res.json()
    assert body["code"] == "ai_unavailable"
    # R4.2: konkreter, maschinenlesbarer Grund + freigegebener deutscher Text.
    assert body["reason_code"] == "mode_deterministic_only"
    assert body["detail"] == (
        "Dieses Projekt ist aktuell auf regelbasierte Verarbeitung beschränkt."
    )
    assert "Datenklasse oder Umgebung" not in body["detail"]


# --- Kein vorgetäuschter lokaler KI-Pfad ------------------------------------

def _setup_local(sensitivity: str = "confidential", nda: bool = False):
    db = SessionLocal()
    try:
        run, draft, base = build_run_with_draft(
            db, processing_mode="local_only", sensitivity=sensitivity,
            origin="real_project", nda=nda,
        )
        ids = (run.run_id, draft.draft_id, base)
        db.commit()
        return ids
    finally:
        db.close()


def _attach_local_confirmation(run_id: str) -> None:
    """Simuliert den beim Run-Start verbrauchten Local-AI-Opt-in."""
    import uuid as _uuid

    from app.db.models import ProcessingConfirmation

    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        db.add(ProcessingConfirmation(
            confirmation_id=str(_uuid.uuid4()), project_id=run.project_id,
            workspace_id=run.workspace_id, created_by="test-user", status="used",
            processing_mode="local_only", source_version_ids=[],
            accepted_policy_version="1.1.0", purpose="KI-Vorschläge (lokal)",
            provider_route_class="fake_local",
            confirmation_text_version="local-ai-confirm-v1",
            data_classification_shown={}, expires_after_one_run=True,
            used_by_run_id=run_id,
        ))
        db.commit()
    finally:
        db.close()


def test_redraft_local_only_without_opt_in_503(client, monkeypatch):
    run_id, _draft_id, base = _setup_local()
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert res.status_code == 503
    assert res.json()["reason_code"] == "provider_unavailable"


def test_redraft_local_only_with_legacy_opt_in_stays_unavailable(client, monkeypatch):
    """Auch eine alte Bestätigung darf keinen nicht existierenden Adapter erzeugen."""
    run_id, _draft_id, base = _setup_local()
    _attach_local_confirmation(run_id)
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert res.status_code == 503, res.text
    assert res.json()["reason_code"] == "provider_unavailable"


def test_redraft_local_only_nda_stays_blocked(client, monkeypatch):
    """D3 bleibt blockiert — auch mit (fälschlich) vorhandenem Opt-in."""
    run_id, _draft_id, base = _setup_local(nda=True)
    _attach_local_confirmation(run_id)
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, FIELD_ID, base)
    assert res.status_code == 503
    assert res.json()["reason_code"] == "provider_unavailable"


def _generate(client, monkeypatch, run_id, base) -> str:
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    op_id = _create_redraft(client, csrf, run_id, FIELD_ID, base).json()["operation_id"]
    return csrf, op_id


def test_accept_creates_agent_draft_version(client, monkeypatch):
    run_id, _draft_id, base = _setup()
    csrf, op_id = _generate(client, monkeypatch, run_id, base)
    res = client.patch(
        f"/api/v1/runs/{run_id}/fields/{FIELD_ID}",
        json={"base_version_id": base, "text": SECTION_GOOD_TEXT,
              "source_operation_id": op_id},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200
    assert res.json()["current_version"]["created_by"] == "agent"
    assert SECTION_GOOD_TEXT in res.json()["current_version"]["text"]
    assert "4.1 Stand der Technik" in res.json()["current_version"]["text"]
    assert "4.3 Ziele" in res.json()["current_version"]["text"]

    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        assert run.recheck_required is True
        suggestion = db.scalar(
            select(DraftSuggestion).where(DraftSuggestion.operation_id == op_id)
        )
        assert suggestion.status == "accepted" and suggestion.accepted_draft_version_id
    finally:
        db.close()


def test_accept_stale_base_409(client, monkeypatch):
    run_id, _draft_id, base = _setup()
    csrf, op_id = _generate(client, monkeypatch, run_id, base)
    res = client.patch(
        f"/api/v1/runs/{run_id}/fields/{FIELD_ID}",
        json={"base_version_id": "stale", "text": SECTION_GOOD_TEXT,
              "source_operation_id": op_id},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 409


def test_accept_invalidates_existing_approval(client, monkeypatch):
    run_id, draft_id, base = _setup()
    # Seed an approved review approval on the run.
    db = SessionLocal()
    try:
        db.add(ReviewApproval(
            approval_id="appr-1", run_id=run_id, workspace_id="ws-demo", scope="run",
            scope_id=run_id, status="approved", approval_scope_hash="h",
            review_package_version="1",
        ))
        db.commit()
    finally:
        db.close()
    csrf, op_id = _generate(client, monkeypatch, run_id, base)
    client.patch(
        f"/api/v1/runs/{run_id}/fields/{FIELD_ID}",
        json={"base_version_id": base, "text": SECTION_GOOD_TEXT,
              "source_operation_id": op_id},
        headers=unsafe_headers(csrf),
    )
    db = SessionLocal()
    try:
        appr = db.get(ReviewApproval, "appr-1")
        assert appr.status == "stale"
    finally:
        db.close()


def test_edited_text_not_marked_agent(client, monkeypatch):
    # A human-edited proposal is merged only into its target section and keeps
    # user provenance, while the reviewed proposal becomes terminally accepted.
    run_id, _draft_id, base = _setup()
    csrf, op_id = _generate(client, monkeypatch, run_id, base)
    res = client.patch(
        f"/api/v1/runs/{run_id}/fields/{FIELD_ID}",
        json={"base_version_id": base, "text": "4.2 Menschlich bearbeitete Neuheit.",
              "source_operation_id": op_id},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200
    assert res.json()["current_version"]["created_by"] == "user"
    assert "4.2 Menschlich bearbeitete Neuheit." in res.json()["current_version"]["text"]
    assert "4.1 Stand der Technik" in res.json()["current_version"]["text"]
    assert "4.3 Ziele" in res.json()["current_version"]["text"]
    db = SessionLocal()
    try:
        suggestion = db.scalar(
            select(DraftSuggestion).where(DraftSuggestion.operation_id == op_id)
        )
        assert suggestion.status == "accepted"
    finally:
        db.close()


def test_reject_creates_no_version(client, monkeypatch):
    # "Reject" is a client-side dismiss — no backend call → no new version.
    run_id, draft_id, base = _setup()
    _generate(client, monkeypatch, run_id, base)
    db = SessionLocal()
    try:
        draft = db.get(PortalFieldDraft, draft_id)
        versions = db.scalars(
            select(DraftVersion).where(DraftVersion.draft_id == draft_id)
        ).all()
        assert len(versions) == 1 and draft.current_version_id == base
    finally:
        db.close()
