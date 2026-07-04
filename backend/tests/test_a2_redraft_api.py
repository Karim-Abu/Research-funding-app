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
    bundle,
    build_run_with_draft,
    fake_resolver,
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
        fake_resolver(success_fake(payload or bundle())),
    )


def _create_redraft(client, csrf, run_id, field_id, base):
    return client.post(
        f"/api/v1/runs/{run_id}/fields/{field_id}/redrafts",
        json={"base_version_id": base}, headers=unsafe_headers(csrf),
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
    assert op["result"]["suggested_text"] == GOOD_TEXT
    assert op["result"]["character_limit"] == 25000


def test_redraft_other_field_404(client, monkeypatch):
    run_id, _draft_id, base = _setup()
    _arm_fake(monkeypatch)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = _create_redraft(client, csrf, run_id, "INTRO.APP.ABSTRACT", base)
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
    assert res.json()["code"] == "ai_unavailable"


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
        json={"base_version_id": base, "text": GOOD_TEXT, "source_operation_id": op_id},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200
    assert res.json()["current_version"]["created_by"] == "agent"
    assert res.json()["current_version"]["text"] == GOOD_TEXT

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
        json={"base_version_id": "stale", "text": GOOD_TEXT, "source_operation_id": op_id},
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
        json={"base_version_id": base, "text": GOOD_TEXT, "source_operation_id": op_id},
        headers=unsafe_headers(csrf),
    )
    db = SessionLocal()
    try:
        appr = db.get(ReviewApproval, "appr-1")
        assert appr.status == "stale"
    finally:
        db.close()


def test_edited_text_not_marked_agent(client, monkeypatch):
    # source_operation_id given but text differs from the suggestion → user edit.
    run_id, _draft_id, base = _setup()
    csrf, op_id = _generate(client, monkeypatch, run_id, base)
    res = client.patch(
        f"/api/v1/runs/{run_id}/fields/{FIELD_ID}",
        json={"base_version_id": base, "text": GOOD_TEXT + "\nUser edit 4.x.",
              "source_operation_id": op_id},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200
    assert res.json()["current_version"]["created_by"] == "user"
    db = SessionLocal()
    try:
        suggestion = db.scalar(
            select(DraftSuggestion).where(DraftSuggestion.operation_id == op_id)
        )
        assert suggestion.status == "proposed"  # not accepted (hash mismatch)
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
