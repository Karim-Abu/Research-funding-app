"""Targeted recheck: currency vs approvability, staleness guard, no mutation."""
from __future__ import annotations

from sqlalchemy import func, select

from app.db.models import DraftVersion, EvidenceAnchor, PortalFieldDraft
from app.db.session import SessionLocal
from tests.review_helpers import (
    ABSTRACT,
    NAME,
    clean_field,
    get_review,
    mut,
    run_recheck,
    setup_completed_run,
)


def _draft_version_count(run_id: str) -> int:
    db = SessionLocal()
    try:
        return db.scalar(
            select(func.count(DraftVersion.draft_version_id))
            .join(PortalFieldDraft, DraftVersion.draft_id == PortalFieldDraft.draft_id)
            .where(PortalFieldDraft.run_id == run_id)
        )
    finally:
        db.close()


def test_edit_sets_recheck_required_then_recheck_clears_it(client):
    csrf, _pid, run_id = setup_completed_run(client)
    assert get_review(client, run_id)["recheck_required"] is False

    clean_field(client, csrf, run_id, ABSTRACT, "Kurzfassung ohne Platzhalter.")
    assert get_review(client, run_id)["recheck_required"] is True

    assert run_recheck(client, csrf, run_id).status_code == 202
    assert get_review(client, run_id)["recheck_required"] is False


def test_recheck_clears_required_even_with_remaining_blockers(client):
    csrf, _pid, run_id = setup_completed_run(client)
    # Clean only one field; the other template fields keep their placeholders.
    clean_field(client, csrf, run_id, ABSTRACT, "Kurzfassung ohne Platzhalter.")
    assert run_recheck(client, csrf, run_id).status_code == 202

    pkg = get_review(client, run_id)
    assert pkg["recheck_required"] is False  # review is current again (corr. #1)
    assert pkg["approval_status"] == "blocked"  # other placeholders still block
    assert pkg["blocker_count"] >= 1


def test_recheck_with_stale_version_conflicts(client):
    csrf, _pid, run_id = setup_completed_run(client)
    res = client.post(
        f"/api/v1/runs/{run_id}/rechecks",
        json={
            "expected_review_package_version": "rpv-staleversion",
            "changed_target_refs": [],
        },
        headers=mut(csrf),
    )
    assert res.status_code == 409
    assert res.json()["code"] == "review_package_stale"


def test_recheck_does_not_mutate_history(client):
    csrf, _pid, run_id = setup_completed_run(client)
    clean_field(client, csrf, run_id, NAME, "Projekt Verbundwerkstoffe")
    versions_before = _draft_version_count(run_id)
    db = SessionLocal()
    try:
        anchors_before = {
            a.anchor_id: a.verification_status
            for a in db.scalars(
                select(EvidenceAnchor).where(EvidenceAnchor.run_id == run_id)
            )
        }
    finally:
        db.close()

    assert run_recheck(client, csrf, run_id).status_code == 202

    assert _draft_version_count(run_id) == versions_before  # no new versions
    db = SessionLocal()
    try:
        anchors_after = {
            a.anchor_id: a.verification_status
            for a in db.scalars(
                select(EvidenceAnchor).where(EvidenceAnchor.run_id == run_id)
            )
        }
        assert anchors_after == anchors_before  # technical evidence untouched
    finally:
        db.close()


def test_recheck_requires_csrf_and_session(client):
    csrf, _pid, run_id = setup_completed_run(client)
    pkg = get_review(client, run_id)
    body = {
        "expected_review_package_version": pkg["review_package_version"],
        "changed_target_refs": [],
    }
    # No CSRF/Origin headers (but Idempotency-Key present) → 403.
    res = client.post(
        f"/api/v1/runs/{run_id}/rechecks",
        json=body,
        headers={"Idempotency-Key": "abcdef123456"},
    )
    assert res.status_code == 403

    client.delete(
        "/api/v1/session",
        headers={"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"},
    )
    res = client.post(f"/api/v1/runs/{run_id}/rechecks", json=body, headers=mut(csrf))
    assert res.status_code == 401
