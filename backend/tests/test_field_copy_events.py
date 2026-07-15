"""Slice 3 (Council E2-A) — copy governance: POST /runs/{id}/fields/{id}/copy-events.

Server-side CopyEvent per Innolink copy action: metadata only (content hash of
the copied version, warning codes, override reason), never raw field text. The
server recomputes the open/limit warnings itself, so the client cannot
understate them; a non-empty warning union requires an override reason.

NOTE: file name deliberately sorts AFTER test_demo_seed.py — earlier files that
create projects in the shared test DB break the demo-seed isolation test
(same trap as test_budget_flow.py in Slice 1).
"""
from __future__ import annotations

import json

from sqlalchemy import select

from app.db.models import AuditEvent, CopyEvent
from app.db.session import SessionLocal
from tests.conftest import unsafe_headers
from tests.review_helpers import ABSTRACT, clean_field, setup_completed_run

CLEAN_TEXT = "Ein vollständig ausgearbeiteter Abstract ohne offene Angaben."
DISTINCT_TEXT = (
    "GovernanceMarkerText: hochvertrauliche Projektidee QuantumTurbine-X99."
)


def _post_copy_event(client, csrf, run_id, field_id, body):
    return client.post(
        f"/api/v1/runs/{run_id}/fields/{field_id}/copy-events",
        json=body,
        headers=unsafe_headers(csrf),
    )


def _current_version(client, run_id, field_id) -> dict:
    return client.get(f"/api/v1/runs/{run_id}/fields/{field_id}").json()[
        "current_version"
    ]


def _audit_events(action: str, target_id: str) -> list[AuditEvent]:
    db = SessionLocal()
    try:
        return list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.action == action, AuditEvent.target_id == target_id
                )
            )
        )
    finally:
        db.close()


def test_copy_event_happy_path_without_warnings(client):
    csrf, _, run_id = setup_completed_run(client, title="Copy Event Clean")
    clean_field(client, csrf, run_id, ABSTRACT, CLEAN_TEXT)
    version = _current_version(client, run_id, ABSTRACT)

    res = _post_copy_event(
        client, csrf, run_id, ABSTRACT,
        {"draft_version_id": version["draft_version_id"], "client_warnings": []},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["field_id"] == ABSTRACT
    assert body["draft_version_id"] == version["draft_version_id"]
    assert body["client_warnings"] == []
    assert body["server_warnings"] == []
    assert body["override_reason_code"] is None
    assert "created_at" in body

    db = SessionLocal()
    try:
        event = db.get(CopyEvent, body["copy_event_id"])
        assert event is not None
        # Server-derived hash of the copied version — never client-provided.
        assert event.content_hash == version["content_hash"]
        assert event.override_reason_note is None
    finally:
        db.close()
    assert len(_audit_events("copy.requested", body["copy_event_id"])) == 1


def test_server_recomputed_warnings_require_reason(client):
    """A fresh template draft contains placeholders; the client reports no
    warnings and sends no reason → the server-side recomputation must 422."""
    csrf, _, run_id = setup_completed_run(client, title="Copy Event Cheat")
    version = _current_version(client, run_id, ABSTRACT)

    res = _post_copy_event(
        client, csrf, run_id, ABSTRACT,
        {"draft_version_id": version["draft_version_id"], "client_warnings": []},
    )
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "override_reason_required"


def test_override_reason_creates_override_audit(client):
    csrf, _, run_id = setup_completed_run(client, title="Copy Event Override")
    version = _current_version(client, run_id, ABSTRACT)

    res = _post_copy_event(
        client, csrf, run_id, ABSTRACT,
        {
            "draft_version_id": version["draft_version_id"],
            "client_warnings": ["open"],
            "override_reason_code": "portal_finalization",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["override_reason_code"] == "portal_finalization"
    assert "open" in body["server_warnings"]
    assert len(_audit_events("copy.override_requested", body["copy_event_id"])) == 1
    assert _audit_events("copy.requested", body["copy_event_id"]) == []


def test_reason_other_requires_note_and_note_stays_out_of_audit(client):
    csrf, _, run_id = setup_completed_run(client, title="Copy Event Other")
    version = _current_version(client, run_id, ABSTRACT)

    # "other" with an empty/whitespace note → 422 (server-side requirement).
    res = _post_copy_event(
        client, csrf, run_id, ABSTRACT,
        {
            "draft_version_id": version["draft_version_id"],
            "client_warnings": [],
            "override_reason_code": "other",
            "override_reason_note": "   ",
        },
    )
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "override_reason_note_required"

    res = _post_copy_event(
        client, csrf, run_id, ABSTRACT,
        {
            "draft_version_id": version["draft_version_id"],
            "client_warnings": [],
            "override_reason_code": "other",
            "override_reason_note": "  Feld wird extern abgestimmt.  ",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    # The note is trimmed, persisted on the event only, never in the response
    # or the audit detail.
    assert "override_reason_note" not in body
    db = SessionLocal()
    try:
        event = db.get(CopyEvent, body["copy_event_id"])
        assert event.override_reason_note == "Feld wird extern abgestimmt."
    finally:
        db.close()
    (audit_event,) = _audit_events("copy.override_requested", body["copy_event_id"])
    assert "Feld wird extern abgestimmt" not in json.dumps(
        audit_event.detail, ensure_ascii=False
    )


def test_stale_version_conflicts(client):
    csrf, _, run_id = setup_completed_run(client, title="Copy Event Stale")
    stale_version = _current_version(client, run_id, ABSTRACT)
    clean_field(client, csrf, run_id, ABSTRACT, CLEAN_TEXT)

    res = _post_copy_event(
        client, csrf, run_id, ABSTRACT,
        {"draft_version_id": stale_version["draft_version_id"]},
    )
    assert res.status_code == 409, res.text
    assert res.json()["code"] == "stale_base_version"


def test_unknown_payload_property_rejected(client):
    """extra="forbid": there is no request property named "warnings"."""
    csrf, _, run_id = setup_completed_run(client, title="Copy Event Payload")
    version = _current_version(client, run_id, ABSTRACT)

    res = _post_copy_event(
        client, csrf, run_id, ABSTRACT,
        {"draft_version_id": version["draft_version_id"], "warnings": ["open"]},
    )
    assert res.status_code == 422, res.text


def test_unsupported_field_is_404(client):
    csrf, _, run_id = setup_completed_run(client, title="Copy Event 404")
    res = _post_copy_event(
        client, csrf, run_id, "NOT.A.FIELD", {"draft_version_id": "x"}
    )
    assert res.status_code == 404


def test_audit_detail_contains_no_field_text(client):
    csrf, _, run_id = setup_completed_run(client, title="Copy Event NoText")
    clean_field(client, csrf, run_id, ABSTRACT, DISTINCT_TEXT)
    version = _current_version(client, run_id, ABSTRACT)

    res = _post_copy_event(
        client, csrf, run_id, ABSTRACT,
        {"draft_version_id": version["draft_version_id"]},
    )
    assert res.status_code == 201, res.text
    copy_event_id = res.json()["copy_event_id"]

    db = SessionLocal()
    try:
        event = db.get(CopyEvent, copy_event_id)
        # The event itself stores only the hash — never the text.
        dumped = json.dumps(
            {
                c.name: str(getattr(event, c.name))
                for c in CopyEvent.__table__.columns
            },
            ensure_ascii=False,
        )
        assert "QuantumTurbine-X99" not in dumped
        audit_rows = db.scalars(
            select(AuditEvent).where(AuditEvent.target_id == copy_event_id)
        )
        for row in audit_rows:
            assert "QuantumTurbine-X99" not in json.dumps(
                row.detail, ensure_ascii=False
            )
    finally:
        db.close()


def test_structured_copy_events_are_snapshot_addressed_and_text_free(client):
    csrf, _project_id, run_id = setup_completed_run(client, title="Structured Copy Event")
    snapshot = client.get(f"/api/v1/runs/{run_id}/transfer-snapshot")
    assert snapshot.status_code == 200, snapshot.text
    body = snapshot.json()
    assert body["snapshot_available"] is True
    assert body["partners"]

    attempts = [
        ("partner_row", body["partners"][0]["copy_target_row"]),
        ("partner_cell", "partner:0:name"),
        ("duration", "duration"),
    ]
    if body["budget"]["values"]:
        attempts.append(("budget_value", body["budget"]["values"][0]["copy_target"]))
    for target_type, target_key in attempts:
        response = client.post(
            f"/api/v1/runs/{run_id}/transfer-copy-events",
            json={"target_type": target_type, "target_key": target_key},
            headers=unsafe_headers(csrf),
        )
        assert response.status_code == 201, response.text
        assert response.json()["target_type"] == target_type
        event_id = response.json()["copy_event_id"]
        db = SessionLocal()
        try:
            event = db.get(CopyEvent, event_id)
            assert event.field_id is None and event.draft_version_id is None
            assert event.target_type == target_type and event.target_key == target_key
            assert event.content_hash
            audit_event = db.scalar(select(AuditEvent).where(AuditEvent.target_id == event_id))
            dumped = json.dumps(audit_event.detail, ensure_ascii=False)
            assert "text" not in dumped.lower()
            assert set(audit_event.detail) == {"target_type", "target_key", "content_hash"}
        finally:
            db.close()

    rejected = client.post(
        f"/api/v1/runs/{run_id}/transfer-copy-events",
        json={"target_type": "duration", "target_key": "duration", "text": "must not be accepted"},
        headers=unsafe_headers(csrf),
    )
    assert rejected.status_code == 422
