"""Draft-marking eligibility + immutable snapshot (Milestone 8)."""
from __future__ import annotations

from sqlalchemy import select

from app.db.models import ExportArtifact
from app.db.session import SessionLocal
from tests.export_helpers import (
    create_export,
    get_export,
    make_export,
    setup_approved_run,
)
from tests.review_helpers import (
    ABSTRACT,
    clean_field,
    mut,
    run_recheck,
    setup_completed_run,
)


def test_unapproved_run_is_draft_marked(client):
    csrf, _pid, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "markdown")
    assert artifact["draft_marked"] is True
    assert "_ENTWURF" in artifact["filename"]


def test_force_draft_always_draft(client):
    csrf, run_id = setup_approved_run(client)
    artifact = make_export(client, csrf, run_id, "markdown", force_draft=True)
    assert artifact["draft_marked"] is True


def test_valid_run_approval_is_not_draft(client):
    csrf, run_id = setup_approved_run(client)
    artifact = make_export(client, csrf, run_id, "docx")
    assert artifact["draft_marked"] is False
    assert "_ENTWURF" not in artifact["filename"]


def test_field_only_approval_is_draft(client):
    csrf, _pid, run_id = setup_completed_run(client)
    clean_field(client, csrf, run_id, ABSTRACT, "Kurzfassung ohne Platzhalter.")
    run_recheck(client, csrf, run_id)
    from tests.review_helpers import approve

    assert approve(client, csrf, run_id, scope="field", scope_id=ABSTRACT).status_code == 201
    artifact = make_export(client, csrf, run_id, "markdown")
    assert artifact["draft_marked"] is True  # field-scope insufficient for run export


def test_edit_after_approval_makes_new_export_draft_but_keeps_old(client):
    csrf, run_id = setup_approved_run(client)
    approved_export = make_export(client, csrf, run_id, "technical_evidence")
    assert approved_export["draft_marked"] is False

    # A later edit invalidates the approval; a NEW export is draft-marked …
    clean_field(client, csrf, run_id, ABSTRACT, "Neue Kurzfassung nach Freigabe.")
    new_export = make_export(client, csrf, run_id, "technical_evidence")
    assert new_export["draft_marked"] is True

    # … but the already-generated approved artifact is unchanged.
    assert get_export(client, approved_export["export_id"]).json()["draft_marked"] is False


def test_snapshot_is_frozen_against_later_edits(client):
    csrf, _pid, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "technical_evidence")
    db = SessionLocal()
    try:
        row = db.get(ExportArtifact, artifact["export_id"])
        frozen_abstract = next(
            f for f in row.export_snapshot_json["fields"] if f["field_id"] == ABSTRACT
        )
        frozen_text = frozen_abstract["text"]
        frozen_hash = row.export_snapshot_hash
    finally:
        db.close()

    clean_field(client, csrf, run_id, ABSTRACT, "Komplett anderer Text nach Export.")

    db = SessionLocal()
    try:
        row = db.get(ExportArtifact, artifact["export_id"])
        still = next(
            f for f in row.export_snapshot_json["fields"] if f["field_id"] == ABSTRACT
        )
        assert still["text"] == frozen_text  # snapshot unchanged by the edit
        assert row.export_snapshot_hash == frozen_hash
    finally:
        db.close()


def test_snapshot_completeness_includes_mutable_entities(client):
    csrf, _pid, run_id = setup_completed_run(client, with_research_partner=False)
    artifact = make_export(client, csrf, run_id, "technical_evidence")
    db = SessionLocal()
    try:
        snap = db.get(ExportArtifact, artifact["export_id"]).export_snapshot_json
        # Full frozen representation of mutable entities (corr. #1).
        assert snap["requirements"], "requirement assessments frozen"
        assert snap["open_issues"], "open issues frozen"
        assert snap["review_findings"], "review findings frozen"
        assert "evidence_links" in snap and "evidence_anchors" in snap
        assert snap["fields"][0]["text"]  # immutable draft text embedded
    finally:
        db.close()


def test_blockers_do_not_prevent_draft_export(client):
    # Missing research partner → blocker, but a draft export is still allowed.
    csrf, _pid, run_id = setup_completed_run(client, with_research_partner=False)
    accepted = create_export(client, csrf, run_id, "docx")
    assert accepted.status_code == 202
    assert get_export(client, accepted.json()["resource_id"]).json()["draft_marked"] is True
