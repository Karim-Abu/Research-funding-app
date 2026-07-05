"""Async lifecycle, idempotency, limits, recovery, download (Milestone 8)."""
from __future__ import annotations

from sqlalchemy import select

from app.db.models import AnalysisRun, AsyncOperation, ControlResult, ExportArtifact, ToolInvocation
from app.db.session import SessionLocal
from app.exports.executor import recover_interrupted_exports
from app.exports.service import prepare_export
from app.storage.exports import get_export_storage
from tests.conftest import OUTSIDER_EMAIL, OUTSIDER_PASSWORD, login
from tests.export_helpers import create_export, download, get_export, make_export, setup_approved_run
from tests.review_helpers import mut, setup_completed_run


def _linked_controls(db, invocation_id):
    return db.scalars(
        select(ControlResult).where(
            ControlResult.tool_invocation_id == invocation_id
        )
    ).all()


def _only_control(controls, control_id):
    matches = [control for control in controls if control.control_id == control_id]
    assert len(matches) == 1
    return matches[0]


def test_create_export_returns_202_async_accepted(client):
    csrf, _pid, run_id = setup_completed_run(client)
    res = create_export(client, csrf, run_id, "markdown")
    assert res.status_code == 202
    body = res.json()
    assert body["resource_type"] == "export"
    assert body["status"] == "queued"
    assert body["poll_url"].startswith("/api/v1/operations/")


def test_lifecycle_reaches_available_with_tool_invocation(client):
    csrf, _pid, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "docx")
    assert artifact["status"] == "available"
    db = SessionLocal()
    try:
        row = db.get(ExportArtifact, artifact["export_id"])
        assert row.content_hash and row.size_bytes and row.storage_key
        inv = db.get(ToolInvocation, row.tool_invocation_id)
        assert inv.tool_id == "create_export_artifact" and inv.status == "succeeded"
        # ControlResults linked to the invocation.
        linked = _linked_controls(db, inv.invocation_id)
        ids = {c.control_id for c in linked}
        assert "CTRL.OUTPUT_SCHEMA" in ids
        approval = _only_control(linked, "CTRL.APPROVAL_GATE")
        assert approval.status == "warning"
        assert "phase=export" in approval.detail
        assert "draft_marked=true" in approval.detail
        assert "reason=export_marked_as_draft" in approval.detail
        assert row.export_snapshot_hash in approval.detail
        classification = _only_control(linked, "CTRL.EXPORT_CLASSIFICATION")
        assert classification.status == "passed"
        assert classification.detail == (
            f"sensitivity={row.effective_data_classification.get('sensitivity')}"
        )
    finally:
        db.close()


def test_approved_export_records_approval_gate_passed(client):
    csrf, run_id = setup_approved_run(client)
    artifact = make_export(client, csrf, run_id, "markdown")
    db = SessionLocal()
    try:
        row = db.get(ExportArtifact, artifact["export_id"])
        inv = db.get(ToolInvocation, row.tool_invocation_id)
        approval = _only_control(
            _linked_controls(db, inv.invocation_id), "CTRL.APPROVAL_GATE"
        )
        assert approval.status == "passed"
        assert "phase=export" in approval.detail
        assert "draft_marked=false" in approval.detail
        assert "reason=approval_current" in approval.detail
        assert row.export_snapshot_hash in approval.detail
    finally:
        db.close()


def test_human_review_records_checkpoint_warning(client):
    _csrf, project_id, _run_id = setup_completed_run(client)
    db = SessionLocal()
    try:
        records = db.scalars(
            select(ControlResult).where(
                ControlResult.project_id == project_id,
                ControlResult.control_id == "CTRL.APPROVAL_GATE",
                ControlResult.detail == (
                    "phase=human_review; reason=review_available_no_auto_approval"
                ),
            )
        ).all()
        assert records
        assert all(record.status == "warning" for record in records)
        passed = db.scalars(
            select(ControlResult).where(
                ControlResult.project_id == project_id,
                ControlResult.control_id == "CTRL.APPROVAL_GATE",
                ControlResult.status == "passed",
                ControlResult.detail == (
                    "phase=human_review; reason=review_available_no_auto_approval"
                ),
            )
        ).all()
        assert passed == []
    finally:
        db.close()


def test_idempotency_replay_and_conflict(client):
    csrf, _pid, run_id = setup_completed_run(client)
    headers = mut(csrf)
    body = {"type": "markdown", "force_draft": False}
    first = client.post(
        f"/api/v1/runs/{run_id}/exports", json=body, headers=headers)
    second = client.post(
        f"/api/v1/runs/{run_id}/exports", json=body, headers=headers)
    assert first.json()["resource_id"] == second.json()[
        "resource_id"]  # replay

    conflict = client.post(
        f"/api/v1/runs/{run_id}/exports",
        json={"type": "docx", "force_draft": False},
        headers=headers,  # same key, different body
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"


def test_export_limit_returns_429(client):
    csrf, _pid, run_id = setup_completed_run(client)
    for _ in range(5):
        assert create_export(client, csrf, run_id,
                             "markdown").status_code == 202
    res = create_export(client, csrf, run_id, "markdown")
    assert res.status_code == 429
    assert res.json()["code"] == "export_limit_reached"
    # A different type is independent.
    assert create_export(client, csrf, run_id, "docx").status_code == 202


def test_run_must_be_completed(client):
    csrf, _pid, run_id = setup_completed_run(client)
    db = SessionLocal()
    try:
        from app.db.models import AnalysisRun

        run = db.get(AnalysisRun, run_id)
        run.status = "running"
        db.commit()
    finally:
        db.close()
    res = create_export(client, csrf, run_id, "markdown")
    assert res.status_code == 409


def test_download_before_available_conflicts(client):
    csrf, _pid, run_id = setup_completed_run(client)
    # Create an artifact stuck in queued (via the service, no executor dispatch).
    db = SessionLocal()
    try:
        from app.db.models import AnalysisRun

        run = db.get(AnalysisRun, run_id)
        _artifact, _op, accepted = prepare_export(
            db, run=run, export_type="markdown", force_draft=False,
            actor_user_id="user-anna", idempotency_key=None, correlation_id=None,
        )
        db.commit()
        export_id = accepted.resource_id
    finally:
        db.close()
    assert download(client, export_id).status_code == 409


def test_download_after_available_returns_bytes_and_filename(client):
    csrf, _pid, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "markdown")
    res = download(client, artifact["export_id"])
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/octet-stream"
    assert "_ENTWURF.md" in res.headers["content-disposition"]
    assert res.content.decode("utf-8").startswith("# ")


def test_hash_mismatch_download_fails_closed(client):
    csrf, _pid, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "markdown")
    db = SessionLocal()
    try:
        row = db.get(ExportArtifact, artifact["export_id"])
        row.content_hash = "0" * 64  # corrupt the recorded hash
        db.commit()
    finally:
        db.close()
    res = download(client, artifact["export_id"])
    assert res.status_code == 409
    assert res.json()["code"] == "export_unavailable"


def test_failure_path_marks_failed(client, monkeypatch):
    csrf, _pid, run_id = setup_completed_run(client)

    def _boom(*_a, **_k):
        raise RuntimeError("forced generator failure")

    import app.exports.tool as tool_mod

    monkeypatch.setitem(tool_mod.GENERATORS, "markdown", _boom)
    accepted = create_export(client, csrf, run_id, "markdown")
    assert accepted.status_code == 202
    export_id = accepted.json()["resource_id"]
    artifact = get_export(client, export_id).json()
    assert artifact["status"] == "failed"
    # No partial file, no stack trace exposed.
    db = SessionLocal()
    try:
        row = db.get(ExportArtifact, export_id)
        assert row.storage_key is None
        assert row.error_code == "EXPORT_FAILED"
    finally:
        db.close()


def test_recovery_fails_interrupted_and_purges_orphans(client):
    csrf, _pid, run_id = setup_completed_run(client)
    # A real available export (its file must be kept).
    available = make_export(client, csrf, run_id, "markdown")

    db = SessionLocal()
    try:
        from app.db.models import AnalysisRun

        run = db.get(AnalysisRun, run_id)
        _artifact, op, accepted = prepare_export(
            db, run=run, export_type="docx", force_draft=False,
            actor_user_id="user-anna", idempotency_key=None, correlation_id=None,
        )
        # Simulate an interrupted in-flight generation.
        stuck = db.get(ExportArtifact, accepted.resource_id)
        stuck.status = "generating"
        db.commit()
        op_id = op.operation_id
        kept_key = db.get(ExportArtifact, available["export_id"]).storage_key
    finally:
        db.close()

    # An orphan file with a valid-looking key.
    orphan = get_export_storage().put(b"orphan").storage_key

    recovered = recover_interrupted_exports()
    assert recovered >= 1

    db = SessionLocal()
    try:
        stuck = db.get(ExportArtifact, accepted.resource_id)
        assert stuck.status == "failed" and stuck.error_code == "EXPORT_INTERRUPTED"
        assert db.get(AsyncOperation, op_id).status == "failed"
        storage = get_export_storage()
        assert storage.exists(kept_key)  # available file kept
        assert not storage.exists(orphan)  # orphan purged
    finally:
        db.close()


def test_workspace_isolation(client):
    csrf, _pid, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "markdown")
    login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
    assert get_export(client, artifact["export_id"]).status_code == 404
    assert download(client, artifact["export_id"]).status_code == 404
