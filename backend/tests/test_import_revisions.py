from __future__ import annotations

from sqlalchemy import select

from app.db.models import (
    AuditEvent,
    ImportCandidateRevision,
    StructuredImportCandidateRevision,
)
from app.db.session import SessionLocal
from app.security.redaction import detail_contains
from tests.conftest import create_project
from tests.review_helpers import ABSTRACT, clean_field, mut
from tests.test_import_api import _decide, _setup_with_candidates, _setup_without_run
from tests.test_structured_import import _decide as decide_structured
from tests.test_structured_import import _setup as setup_structured


def narrative_scope(project_id: str, candidate: dict) -> dict:
    return {
        "project_id": project_id,
        "source_id": candidate["source_id"],
        "expected_revision_id": candidate["current_revision_id"],
    }


def structured_scope(project_id: str, candidate: dict) -> dict:
    return {
        "project_id": project_id,
        "source_id": candidate["source_id"],
        "expected_revision_id": candidate["current_revision_id"],
    }


def test_narrative_edit_reset_idempotent_reset_and_undo(client):
    csrf, project_id, by_field = _setup_without_run(client)
    candidate = by_field[ABSTRACT]
    first = _decide(client, csrf, candidate["import_candidate_id"], decision="ignored")
    assert first.status_code == 200
    ignored = first.json()

    edited = client.patch(
        f"/api/v1/imports/{candidate['import_candidate_id']}/decision",
        json={
            **narrative_scope(project_id, ignored),
            "decision": "accepted",
            "edited_text": "Vom Menschen bearbeitete Importfassung.",
        },
        headers=mut(csrf),
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["acceptance_state"] == "accepted_modified"

    reset = client.post(
        f"/api/v1/imports/{candidate['import_candidate_id']}/reset",
        json=narrative_scope(project_id, edited.json()),
        headers=mut(csrf),
    )
    assert reset.status_code == 200, reset.text
    body = reset.json()
    assert body["acceptance_state"] == "accepted_original"
    reset_revision = body["current_revision_id"]

    repeated = client.post(
        f"/api/v1/imports/{candidate['import_candidate_id']}/reset",
        json=narrative_scope(project_id, body),
        headers=mut(csrf),
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["current_revision_id"] == reset_revision
    assert repeated.json()["idempotent_replay"] is True

    undone = client.post(
        f"/api/v1/imports/{candidate['import_candidate_id']}/undo",
        json=narrative_scope(project_id, repeated.json()),
        headers=mut(csrf),
    )
    assert undone.status_code == 200, undone.text
    assert undone.json()["decision"] == "pending"
    assert undone.json()["revision_number"] == body["revision_number"] + 1

    with SessionLocal() as db:
        revisions = list(
            db.scalars(
                select(ImportCandidateRevision)
                .where(
                    ImportCandidateRevision.import_candidate_id
                    == candidate["import_candidate_id"]
                )
                .order_by(ImportCandidateRevision.revision_number)
            )
        )
    assert [row.action for row in revisions] == [
        "detected",
        "decision",
        "edit",
        "reset",
        "undo",
    ]


def test_narrative_undo_preserves_later_manual_draft(client):
    csrf, project_id, run_id, _, by_field = _setup_with_candidates(client)
    candidate = by_field[ABSTRACT]
    accepted = _decide(
        client,
        csrf,
        candidate["import_candidate_id"],
        decision="accepted",
        run_id=run_id,
    )
    assert accepted.status_code == 200, accepted.text
    manual = "Spätere manuelle Fassung ohne offene Angaben."
    clean_field(client, csrf, run_id, ABSTRACT, manual)

    conflict = client.post(
        f"/api/v1/imports/{candidate['import_candidate_id']}/undo",
        json=narrative_scope(project_id, accepted.json()),
        headers=mut(csrf),
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["code"] == "import_revision_conflict"
    draft = client.get(f"/api/v1/runs/{run_id}/fields/{ABSTRACT}").json()
    assert draft["current_version"]["text"] == manual
    listed = client.get(f"/api/v1/projects/{project_id}/imports").json()
    current = next(
        item
        for item in listed
        if item["import_candidate_id"] == candidate["import_candidate_id"]
    )
    assert current["decision"] == "conflict"
    assert current["conflict_reason"] == "manual_resolution_required"


def test_narrative_scope_and_revision_preconditions_are_fail_closed(client):
    csrf, project_id, by_field = _setup_without_run(client)
    candidate = by_field[ABSTRACT]
    wrong_project = create_project(client, csrf, "Wrong import target")
    mismatch = client.patch(
        f"/api/v1/imports/{candidate['import_candidate_id']}/decision",
        json={
            **narrative_scope(wrong_project, candidate),
            "decision": "ignored",
        },
        headers=mut(csrf),
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "import_project_source_mismatch"

    stale = client.patch(
        f"/api/v1/imports/{candidate['import_candidate_id']}/decision",
        json={
            **narrative_scope(project_id, candidate),
            "expected_revision_id": "stale-revision",
            "decision": "ignored",
        },
        headers=mut(csrf),
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "import_revision_conflict"

    invalid = client.post(
        f"/api/v1/imports/{candidate['import_candidate_id']}/undo",
        json=narrative_scope(project_id, candidate),
        headers=mut(csrf),
    )
    assert invalid.status_code == 409
    assert invalid.json()["code"] == "import_invalid_transition"

    missing = client.post(
        "/api/v1/imports/missing-candidate/undo",
        json=narrative_scope(project_id, candidate),
        headers=mut(csrf),
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "import_candidate_not_found"


def test_structured_project_edit_reset_undo_and_manual_conflict(client):
    csrf, project_id, _, by_target = setup_structured(client)
    candidate = by_target["project.cash_contribution"]
    accepted = decide_structured(client, csrf, candidate)
    assert accepted.status_code == 200, accepted.text

    edited = client.patch(
        f"/api/v1/structured-imports/{candidate['candidate_id']}/decision",
        json={
            **structured_scope(project_id, accepted.json()),
            "decision": "accepted",
            "edited_payload_json": {"cash_contribution": 21000},
            "confirm_overwrite": True,
        },
        headers=mut(csrf),
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["acceptance_state"] == "accepted_modified"

    reset = client.post(
        f"/api/v1/structured-imports/{candidate['candidate_id']}/reset",
        json=structured_scope(project_id, edited.json()),
        headers=mut(csrf),
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["acceptance_state"] == "accepted_original"

    manual = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"cash_contribution": 99999},
        headers=mut(csrf),
    )
    assert manual.status_code == 200, manual.text
    conflict = client.post(
        f"/api/v1/structured-imports/{candidate['candidate_id']}/undo",
        json=structured_scope(project_id, reset.json()),
        headers=mut(csrf),
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["code"] == "import_revision_conflict"
    assert client.get(f"/api/v1/projects/{project_id}").json()[
        "cash_contribution"
    ] == 99999


def test_structured_partner_undo_removes_only_unchanged_import_target(client):
    csrf, project_id, _, by_target = setup_structured(client)
    candidate = by_target["partner.research.01"]
    accepted = decide_structured(client, csrf, candidate)
    assert accepted.status_code == 200, accepted.text
    assert len(client.get(f"/api/v1/projects/{project_id}/partners").json()) == 1
    undone = client.post(
        f"/api/v1/structured-imports/{candidate['candidate_id']}/undo",
        json=structured_scope(project_id, accepted.json()),
        headers=mut(csrf),
    )
    assert undone.status_code == 200, undone.text
    assert undone.json()["decision"] == "pending"
    assert client.get(f"/api/v1/projects/{project_id}/partners").json() == []


def test_revision_audit_contains_no_d2_values(client):
    csrf, project_id, _, by_target = setup_structured(client)
    candidate = by_target["partner.research.01"]
    marker = candidate["payload_json"]["name"]
    accepted = decide_structured(client, csrf, candidate)
    assert accepted.status_code == 200
    with SessionLocal() as db:
        revisions = list(
            db.scalars(
                select(StructuredImportCandidateRevision).where(
                    StructuredImportCandidateRevision.candidate_id
                    == candidate["candidate_id"]
                )
            )
        )
        events = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.target_id == candidate["candidate_id"]
                )
            )
        )
    assert revisions
    assert events
    assert all(not detail_contains(event.detail, (marker,)) for event in events)
