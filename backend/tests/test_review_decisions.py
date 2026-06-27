"""Human decisions + section comments + review-level evidence semantics."""
from __future__ import annotations

from sqlalchemy import select

from app.db.models import EvidenceAnchor
from app.db.session import SessionLocal
from tests.conftest import OUTSIDER_EMAIL, OUTSIDER_PASSWORD, login
from tests.review_helpers import ABSTRACT, get_review, mut, setup_completed_run


def _decide(client, csrf, run_id, body):
    return client.post(
        f"/api/v1/runs/{run_id}/human-decisions", json=body, headers=mut(csrf)
    )


def _abstract_draft_id(client, run_id) -> str:
    draft = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()
    return draft["draft_id"]


def test_comment_creates_human_finding(client):
    csrf, _pid, run_id = setup_completed_run(client)
    draft_id = _abstract_draft_id(client, run_id)
    res = _decide(
        client, csrf, run_id,
        {
            "target_type": "portal_field_draft",
            "target_id": draft_id,
            "action": "request_changes",
            "comment": "Bitte den Nutzen konkretisieren.",
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["target_type"] == "portal_field_draft"

    comments = [
        f for f in get_review(client, run_id)["findings"]
        if f["field_id"] == ABSTRACT and f["description"] == "Bitte den Nutzen konkretisieren."
    ]
    assert len(comments) == 1
    assert comments[0]["severity"] == "warning"


def test_comment_confirm_resolves_field_comments(client):
    csrf, _pid, run_id = setup_completed_run(client)
    draft_id = _abstract_draft_id(client, run_id)
    _decide(
        client, csrf, run_id,
        {"target_type": "portal_field_draft", "target_id": draft_id,
         "action": "request_changes", "comment": "Punkt offen."},
    )
    res = _decide(
        client, csrf, run_id,
        {"target_type": "portal_field_draft", "target_id": draft_id, "action": "confirm"},
    )
    assert res.status_code == 201
    assert not [
        f for f in get_review(client, run_id)["findings"]
        if f["field_id"] == ABSTRACT and f["description"] == "Punkt offen."
    ]


def test_request_changes_requires_comment(client):
    csrf, _pid, run_id = setup_completed_run(client)
    draft_id = _abstract_draft_id(client, run_id)
    res = _decide(
        client, csrf, run_id,
        {"target_type": "portal_field_draft", "target_id": draft_id,
         "action": "request_changes", "comment": "  "},
    )
    assert res.status_code == 422
    assert res.json()["code"] == "comment_required"


def test_finding_dismiss_updates_status(client):
    csrf, _pid, run_id = setup_completed_run(client)
    finding = next(
        f for f in get_review(client, run_id)["findings"] if f["severity"] == "blocker"
    )
    res = _decide(
        client, csrf, run_id,
        {"target_type": "review_finding", "target_id": finding["finding_id"],
         "action": "dismiss", "comment": "Bewusst akzeptiert."},
    )
    assert res.status_code == 201
    # Dismissed → no longer in the open findings list.
    assert finding["finding_id"] not in {
        f["finding_id"] for f in get_review(client, run_id)["findings"]
    }


def test_evidence_decision_does_not_change_verification(client):
    csrf, _pid, run_id = setup_completed_run(client)
    db = SessionLocal()
    try:
        anchor = db.scalar(
            select(EvidenceAnchor).where(EvidenceAnchor.run_id == run_id)
        )
        assert anchor is not None
        anchor_id = anchor.anchor_id
        before = anchor.verification_status
    finally:
        db.close()

    res = _decide(
        client, csrf, run_id,
        {"target_type": "evidence_anchor", "target_id": anchor_id,
         "action": "confirm", "comment": "Fachlich bestätigt."},
    )
    assert res.status_code == 201
    db = SessionLocal()
    try:
        anchor = db.get(EvidenceAnchor, anchor_id)
        assert anchor.verification_status == before  # technical status untouched
        assert anchor.verification_status != "human_verified"
    finally:
        db.close()


def test_decision_idempotency_replay(client):
    csrf, _pid, run_id = setup_completed_run(client)
    draft_id = _abstract_draft_id(client, run_id)
    body = {
        "target_type": "portal_field_draft", "target_id": draft_id,
        "action": "request_changes", "comment": "Einmalig.",
    }
    headers = mut(csrf)
    first = client.post(
        f"/api/v1/runs/{run_id}/human-decisions", json=body, headers=headers
    )
    second = client.post(
        f"/api/v1/runs/{run_id}/human-decisions", json=body, headers=headers
    )
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["decision_id"] == second.json()["decision_id"]


def test_outsider_cannot_decide_foreign_run(client):
    _csrf, _pid, run_id = setup_completed_run(client)
    out_csrf = login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
    res = _decide(
        client, out_csrf, run_id,
        {"target_type": "review_finding", "target_id": "any", "action": "dismiss"},
    )
    assert res.status_code == 404
