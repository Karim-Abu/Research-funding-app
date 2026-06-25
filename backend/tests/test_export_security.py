"""Export security: auth, CSRF/Origin, safe filenames, no traversal/network."""
from __future__ import annotations

import socket
import uuid

import pytest

from app.exports.generators.common import build_filename, slugify
from app.storage.exports import LocalExportStorage
from tests.export_helpers import create_export, make_export
from tests.review_helpers import mut, setup_completed_run


def test_create_export_unauthenticated_401(client):
    res = client.post(
        f"/api/v1/runs/{uuid.uuid4()}/exports",
        json={"type": "markdown"},
        headers={"Idempotency-Key": "abcdef123456", "Origin": "http://localhost:3000",
                 "X-CSRF-Token": "x"},
    )
    assert res.status_code == 401


def test_get_export_unauthenticated_401(client):
    assert client.get(f"/api/v1/exports/{uuid.uuid4()}").status_code == 401


def test_create_export_requires_csrf(client):
    csrf, _pid, run_id = setup_completed_run(client)
    res = client.post(
        f"/api/v1/runs/{run_id}/exports",
        json={"type": "markdown"},
        headers={"Idempotency-Key": "abcdef123456"},  # no CSRF/Origin
    )
    assert res.status_code == 403


def test_invalid_type_422(client):
    csrf, _pid, run_id = setup_completed_run(client)
    res = client.post(
        f"/api/v1/runs/{run_id}/exports",
        json={"type": "pdf"},
        headers=mut(csrf),
    )
    assert res.status_code == 422


def test_filename_is_ascii_safe_no_traversal():
    snap = {
        "meta": {
            "project_title": "../../etc/pässwörd ☠/<script>",
            "export_type": "markdown",
            "draft_marked": True,
        }
    }
    name = build_filename(snap)
    assert "/" not in name and "\\" not in name and ".." not in name
    assert name.endswith("_ENTWURF.md")
    assert slugify("") == "Export"


def test_storage_rejects_unsafe_refs(tmp_path):
    storage = LocalExportStorage(str(tmp_path), max_bytes=1024)
    with pytest.raises(ValueError):
        storage.open_verified("../escape", expected_hash="x")
    with pytest.raises(ValueError):
        storage.open_verified("not-a-hex-key", expected_hash="x")


def test_no_network_during_generation(client, monkeypatch):
    """Generation must succeed with all sockets blocked, proving no provider /
    HTTP / network call. Exercised directly (the TestClient's asyncio event loop
    itself uses a socketpair on Windows, so we block only around pure generation)."""
    from app.db.models import ExportArtifact
    from app.db.session import SessionLocal
    from app.exports.generators import GENERATORS

    csrf, _pid, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "markdown")  # before blocking
    db = SessionLocal()
    try:
        snapshot = db.get(ExportArtifact, artifact["export_id"]).export_snapshot_json
    finally:
        db.close()

    def _blocked(*_a, **_k):
        raise AssertionError("network access attempted during export generation")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    for export_type in ("docx", "markdown", "technical_evidence"):
        snap = {**snapshot, "meta": {**snapshot["meta"], "export_type": export_type}}
        assert GENERATORS[export_type](snap, "h")  # no network needed


def test_download_response_has_no_stack_trace(client):
    csrf, _pid, run_id = setup_completed_run(client)
    res = create_export(client, csrf, run_id, "markdown")
    # A normal Problem body never includes a traceback.
    assert "Traceback" not in res.text
