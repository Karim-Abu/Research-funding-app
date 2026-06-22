"""Source ingestion: upload/parse/normalize/version/fragment/delete + security."""
from __future__ import annotations

import json
import uuid

from sqlalchemy import select

from app.db.models import SourceFragment, SourceVersion
from app.db.session import SessionLocal
from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    ORIGIN,
    OUTSIDER_EMAIL,
    OUTSIDER_PASSWORD,
    VALID_CLASSIFICATION,
    create_project,
    login,
    unsafe_headers,
)
from tests.fixtures import (
    CORRUPTED_PDF,
    EXECUTABLE_BYTES,
    TXT_BYTES,
    make_docx,
    make_image_only_pdf,
    make_text_pdf,
)


def _upload(client, project_id, csrf, filename, data, mime, classification=None, key=None):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = key or uuid.uuid4().hex
    return client.post(
        f"/api/v1/projects/{project_id}/sources/files",
        files=[("files", (filename, data, mime))],
        data={
            "data_classification_json": json.dumps(
                classification or VALID_CLASSIFICATION
            )
        },
        headers=headers,
    )


def _create_text(client, project_id, csrf, name="Notes", text="Some notes here.", classification=None, key=None):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = key or uuid.uuid4().hex
    return client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={
            "name": name,
            "text": text,
            "data_classification": classification or VALID_CLASSIFICATION,
        },
        headers=headers,
    )


def _project(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    return csrf, create_project(client, csrf)


def test_upload_pdf_docx_txt_become_processed(client):
    csrf, project_id = _project(client)
    cases = [
        ("doc.pdf", make_text_pdf("Innovation project summary."), "application/pdf"),
        ("doc.docx", make_docx(with_table=True), "application/octet-stream"),
        ("doc.txt", TXT_BYTES, "text/plain"),
    ]
    for filename, data, mime in cases:
        res = _upload(client, project_id, csrf, filename, data, mime)
        assert res.status_code == 202, res.text
        source_id = res.json()[0]["source_id"]
        got = client.get(f"/api/v1/sources/{source_id}")
        assert got.status_code == 200
        assert got.json()["status"] == "processed", (filename, got.json())
        assert got.json()["current_source_version_id"]


def test_create_text_source_processed(client):
    csrf, project_id = _project(client)
    res = _create_text(client, project_id, csrf)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["type"] == "txt"
    assert body["status"] == "processed"
    assert body["current_source_version_id"]


def test_list_and_delete(client):
    csrf, project_id = _project(client)
    source_id = _create_text(client, project_id, csrf).json()["source_id"]
    listing = client.get(f"/api/v1/projects/{project_id}/sources")
    assert listing.status_code == 200
    assert any(s["source_id"] == source_id for s in listing.json())

    deleted = client.delete(
        f"/api/v1/sources/{source_id}", headers=unsafe_headers(csrf)
    )
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/sources/{source_id}").status_code == 404


def test_workspace_isolation(client):
    csrf, project_id = _project(client)
    source_id = _create_text(client, project_id, csrf).json()["source_id"]
    # Outsider in a different workspace cannot see it.
    login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
    assert client.get(f"/api/v1/sources/{source_id}").status_code == 404


def test_csrf_and_origin_rejected(client):
    csrf, project_id = _project(client)
    no_csrf = client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={"name": "n", "text": "t", "data_classification": VALID_CLASSIFICATION},
        headers={"Origin": ORIGIN, "Idempotency-Key": uuid.uuid4().hex},
    )
    assert no_csrf.status_code == 403 and no_csrf.json()["code"] == "csrf_failed"

    bad_origin = client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={"name": "n", "text": "t", "data_classification": VALID_CLASSIFICATION},
        headers={
            "X-CSRF-Token": csrf,
            "Origin": "https://evil.example",
            "Idempotency-Key": uuid.uuid4().hex,
        },
    )
    assert bad_origin.status_code == 403 and bad_origin.json()["code"] == "origin_forbidden"


def test_idempotent_replay_and_conflict(client):
    csrf, project_id = _project(client)
    key = uuid.uuid4().hex
    first = _create_text(client, project_id, csrf, text="same", key=key)
    second = _create_text(client, project_id, csrf, text="same", key=key)
    assert first.json()["source_id"] == second.json()["source_id"]
    conflict = _create_text(client, project_id, csrf, text="different", key=key)
    assert conflict.status_code == 409


def test_unsupported_executable_rejected(client):
    csrf, project_id = _project(client)
    res = _upload(client, project_id, csrf, "evil.txt", EXECUTABLE_BYTES, "text/plain")
    assert res.status_code == 415


def test_oversized_file_rejected(client):
    csrf, project_id = _project(client)
    big = b"A" * (1024 * 1024 + 10)  # > MAX_UPLOAD_BYTES (1 MiB in tests)
    res = _upload(client, project_id, csrf, "big.txt", big, "text/plain")
    assert res.status_code == 413


def test_path_traversal_filename_is_safe(client):
    csrf, project_id = _project(client)
    res = _upload(
        client, project_id, csrf, "../../../etc/passwd.txt", TXT_BYTES, "text/plain"
    )
    # Filename is metadata only (uuid storage keys) — upload succeeds safely.
    assert res.status_code == 202
    source_id = res.json()[0]["source_id"]
    assert client.get(f"/api/v1/sources/{source_id}").status_code == 200


def test_corrupted_pdf_becomes_failed(client):
    csrf, project_id = _project(client)
    res = _upload(client, project_id, csrf, "bad.pdf", CORRUPTED_PDF, "application/pdf")
    assert res.status_code == 202
    source_id = res.json()[0]["source_id"]
    got = client.get(f"/api/v1/sources/{source_id}").json()
    assert got["status"] == "failed"
    assert got["error_message"]


def test_image_only_pdf_needs_manual_input(client):
    csrf, project_id = _project(client)
    res = _upload(
        client, project_id, csrf, "scan.pdf", make_image_only_pdf(), "application/pdf"
    )
    assert res.status_code == 202
    source_id = res.json()[0]["source_id"]
    assert client.get(f"/api/v1/sources/{source_id}").json()["status"] == "needs_manual_input"


def _confidential_project(client, csrf) -> str:
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = uuid.uuid4().hex
    payload = {
        "title": "Confidential",
        "description": "x",
        "funding_instrument_profile_id": (
            "innosuisse_innovation_project_with_implementation_partner"
        ),
        "data_classification": {
            "sensitivity": "confidential",
            "origin": "real_project",
            "processing_mode": "local_only",
            "web_research_mode": "off",
            "nda_applies": True,
        },
    }
    res = client.post("/api/v1/projects", json=payload, headers=headers)
    assert res.status_code == 201
    return res.json()["project_id"]


def test_classification_not_silently_downgraded(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _confidential_project(client, csrf)
    # Source declares public/no-NDA — must be clamped up to the project floor.
    public = {
        "sensitivity": "public",
        "origin": "synthetic",
        "processing_mode": "cloud_assisted",
        "web_research_mode": "off",
        "nda_applies": False,
    }
    res = _create_text(client, project_id, csrf, classification=public)
    assert res.status_code == 201
    effective = res.json()["data_classification"]
    assert effective["sensitivity"] == "confidential"  # not downgraded
    assert effective["nda_applies"] is True  # NDA OR


def test_content_hashes_stable_and_fragments_persist(client):
    csrf, project_id = _project(client)
    text = "Stable content for hashing.\nSecond paragraph."
    first = _create_text(client, project_id, csrf, text=text).json()
    second = _create_text(client, project_id, csrf, text=text).json()

    # Re-open the DB (simulates a restart) and verify persisted versions/fragments.
    db = SessionLocal()
    try:
        v1 = db.scalar(
            select(SourceVersion).where(
                SourceVersion.source_document_id == first["source_id"]
            )
        )
        v2 = db.scalar(
            select(SourceVersion).where(
                SourceVersion.source_document_id == second["source_id"]
            )
        )
        assert v1.original_content_hash == v2.original_content_hash
        assert v1.normalized_content_hash == v2.normalized_content_hash
        assert v1.parser_version and v1.normalizer_version and v1.chunker_version
        fragments = db.scalars(
            select(SourceFragment).where(
                SourceFragment.source_version_id == v1.source_version_id
            )
        ).all()
        assert len(fragments) >= 1
        assert all(len(f.content_hash) == 64 for f in fragments)
    finally:
        db.close()
