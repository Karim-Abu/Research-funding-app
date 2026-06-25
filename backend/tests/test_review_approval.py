"""Approval gating: scope, scope hash, staleness on edit, guards, isolation."""
from __future__ import annotations

from tests.conftest import (
    OUTSIDER_EMAIL,
    OUTSIDER_PASSWORD,
    login,
    unsafe_headers,
)
from tests.review_helpers import (
    ABSTRACT,
    approve,
    clean_field,
    get_review,
    mut,
    run_recheck,
    setup_completed_run,
)


def test_run_scope_approval_blocked_by_placeholders(client):
    csrf, _pid, run_id = setup_completed_run(client)
    res = approve(client, csrf, run_id, scope="run", scope_id=run_id)
    assert res.status_code == 409
    assert res.json()["code"] == "approval_blocked"


def test_field_scope_approval_succeeds_after_clean_and_recheck(client):
    csrf, _pid, run_id = setup_completed_run(client)
    clean_field(client, csrf, run_id, ABSTRACT, "Kurzfassung ohne Platzhalter.")
    assert run_recheck(client, csrf, run_id).status_code == 202

    res = approve(client, csrf, run_id, scope="field", scope_id=ABSTRACT)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "approved"
    assert body["scope"] == "field"
    assert body["approved_by"] == "user-anna"
    assert get_review(client, run_id)["approval_status"] in ("approved", "blocked")


def test_approval_with_stale_hash_conflicts(client):
    csrf, _pid, run_id = setup_completed_run(client)
    clean_field(client, csrf, run_id, ABSTRACT, "Kurzfassung ohne Platzhalter.")
    run_recheck(client, csrf, run_id)
    res = client.post(
        f"/api/v1/runs/{run_id}/approvals",
        json={
            "scope": "field",
            "scope_id": ABSTRACT,
            "expected_approval_scope_hash": "deadbeef" * 8,
            "expected_review_package_version": "rpv-wrong",
            "confirm_not_submission_approval": True,
        },
        headers=mut(csrf),
    )
    assert res.status_code == 409
    assert res.json()["code"] == "review_package_stale"


def test_edit_after_approval_invalidates_it(client):
    csrf, _pid, run_id = setup_completed_run(client)
    clean_field(client, csrf, run_id, ABSTRACT, "Kurzfassung ohne Platzhalter.")
    run_recheck(client, csrf, run_id)
    assert approve(client, csrf, run_id, scope="field", scope_id=ABSTRACT).status_code == 201

    # A further edit to the approved field invalidates the approval.
    clean_field(client, csrf, run_id, ABSTRACT, "Aktualisierte Kurzfassung.")
    pkg = get_review(client, run_id)
    assert pkg["approval_status"] == "stale"
    assert pkg["recheck_required"] is True


def test_confirm_not_submission_must_be_true(client):
    csrf, _pid, run_id = setup_completed_run(client)
    pkg = get_review(client, run_id)
    res = client.post(
        f"/api/v1/runs/{run_id}/approvals",
        json={
            "scope": "run",
            "scope_id": run_id,
            "expected_approval_scope_hash": pkg["current_approval_scope_hash"],
            "expected_review_package_version": pkg["review_package_version"],
            "confirm_not_submission_approval": False,
        },
        headers=mut(csrf),
    )
    assert res.status_code == 422  # const true violated by schema


def test_approval_requires_csrf(client):
    csrf, _pid, run_id = setup_completed_run(client)
    pkg = get_review(client, run_id)
    res = client.post(
        f"/api/v1/runs/{run_id}/approvals",
        json={
            "scope": "field",
            "scope_id": ABSTRACT,
            "expected_approval_scope_hash": pkg["current_approval_scope_hash"],
            "expected_review_package_version": pkg["review_package_version"],
            "confirm_not_submission_approval": True,
        },
        headers={"Idempotency-Key": "abcdef123456"},
    )
    assert res.status_code == 403


def test_outsider_cannot_approve_foreign_run(client):
    _csrf, _pid, run_id = setup_completed_run(client)
    # Switch to an isolated-workspace user.
    out_csrf = login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
    res = client.post(
        f"/api/v1/runs/{run_id}/approvals",
        json={
            "scope": "field",
            "scope_id": ABSTRACT,
            "expected_approval_scope_hash": "x" * 64,
            "expected_review_package_version": "rpv-x",
            "confirm_not_submission_approval": True,
        },
        headers=mut(out_csrf),
    )
    assert res.status_code == 404


def test_run_scope_blocked_by_missing_partner(client):
    csrf, _pid, run_id = setup_completed_run(client, with_research_partner=False)
    res = approve(client, csrf, run_id, scope="run", scope_id=run_id)
    assert res.status_code == 409
    assert "blocker_issue" in res.json()["detail"]
