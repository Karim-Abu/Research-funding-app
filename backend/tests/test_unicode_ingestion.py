"""Unicode / non-ASCII text ingestion regression (Milestone 4.1).

Guards the previously-broken path where valid German/French text (umlauts, ß,
accents, German quotation marks) was misclassified as binary and the source
ended up `failed`.
"""
from __future__ import annotations

import json
import unicodedata
import uuid

from sqlalchemy import select

from app.db.models import SourceFragment, SourceVersion
from app.db.session import SessionLocal
from app.ingestion.signatures import (
    UnsupportedFileError,
    detect_source_type,
    is_executable,
    looks_binary,
)
from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    VALID_CLASSIFICATION,
    create_project,
    login,
    unsafe_headers,
)

GERMAN = "Müller & Söhne prüfen die Förderfähigkeit für größere Vorhaben. äöüÄÖÜß"
FRENCH = "Évaluation de la faisabilité: é è à ç, déjà vu où ñ."
QUOTES = "Er sagte: „Prüfung über Förderfähigkeit“ – ‚wichtig‘ »Zitat«"
COMBINING_DIAERESIS = "̈"


# --- unit: looks_binary ----------------------------------------------------


def test_looks_binary_false_for_utf8_non_ascii_text():
    for text in (GERMAN, FRENCH, QUOTES, "ä", "ß", "é", GERMAN * 80):
        assert looks_binary(text.encode("utf-8")) is False, text


def test_looks_binary_false_for_cp1252_umlauts():
    # Valid Windows-1252, NOT valid UTF-8 — must still be recognised as text.
    data = "Müller Söhne prüfen Förderfähigkeit".encode("cp1252")
    assert looks_binary(data) is False


def test_looks_binary_true_for_nul_and_control_heavy():
    assert looks_binary(b"text\x00\x01\x02more") is True  # NUL
    # No NUL, but almost all C0 control bytes → binary via the control ratio.
    assert looks_binary(bytes(range(1, 32)) * 40) is True


def test_looks_binary_true_for_real_binary_blob():
    png = b"\x89PNG\r\n\x1a\n" + bytes(range(1, 32)) * 40
    assert looks_binary(png) is True


def test_composed_and_decomposed_unicode_not_binary():
    nfc = unicodedata.normalize("NFC", "ä").encode("utf-8")  # U+00E4
    nfd = unicodedata.normalize("NFD", "ä").encode("utf-8")  # a + U+0308
    assert nfc != nfd
    assert looks_binary(nfc) is False
    assert looks_binary(nfd) is False


def test_sample_boundary_multibyte_truncation_tolerated():
    # A 2-byte 'ü' begins at byte 8191, so the 8192-byte sample cuts it in half.
    # That is an "unexpected end of data" truncation → judge the valid prefix.
    data = b"a" * 8191 + "ü".encode("utf-8") + b" more text follows here."
    assert looks_binary(data) is False


def test_invalid_but_decodable_bytes_judged_by_control_ratio():
    # 0xFF/0xFE are invalid UTF-8 but valid cp1252 letters (ÿ/þ) → text.
    assert looks_binary(b"a" * 10 + b"\xff\xfe" + b"b" * 10) is False
    # Invalid UTF-8 AND control-heavy under cp1252 → binary.
    assert looks_binary(b"\xff" + bytes(range(1, 32)) * 40) is True


def test_executable_and_magic_detection_unaffected():
    assert is_executable(b"MZ\x90\x00") is True
    try:
        detect_source_type("payload.txt", b"MZ\x90\x00" + b"rest of file")
        raise AssertionError("executable should be rejected")
    except UnsupportedFileError:
        pass


def test_detect_source_type_accepts_umlaut_txt():
    assert detect_source_type("notiz.txt", GERMAN.encode("utf-8")) == "txt"


# --- API + persistence round-trip ------------------------------------------


def _create_text(client, project_id, csrf, name, text, key=None):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = key or uuid.uuid4().hex
    return client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={"name": name, "text": text, "data_classification": VALID_CLASSIFICATION},
        headers=headers,
    )


def test_umlaut_text_source_processed_and_preserved(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    res = _create_text(client, project_id, csrf, "Förderprüfung", GERMAN)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "processed"  # previously: failed
    assert body["name"] == "Förderprüfung"

    db = SessionLocal()
    try:
        version = db.get(SourceVersion, body["current_source_version_id"])
        assert "Müller & Söhne" in version.normalized_text
        assert "Förderfähigkeit" in version.normalized_text
        assert "äöüÄÖÜß" in version.normalized_text
        fragments = list(
            db.scalars(
                select(SourceFragment).where(
                    SourceFragment.source_version_id == version.source_version_id
                )
            )
        )
        assert fragments
        joined = " ".join(f.normalized_text for f in fragments)
        assert "Müller" in joined and "ß" in joined and "größere" in joined
    finally:
        db.close()


def test_french_and_german_quotes_preserved(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    text = FRENCH + "\n\n" + QUOTES
    res = _create_text(client, project_id, csrf, "Texte", text)
    assert res.status_code == 201, res.text
    db = SessionLocal()
    try:
        version = db.get(SourceVersion, res.json()["current_source_version_id"])
        for needle in ("Évaluation", "déjà", "ç", "„Prüfung", "»Zitat«"):
            assert needle in version.normalized_text, needle
    finally:
        db.close()


def test_decomposed_input_normalized_to_composed(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    composed = "Förderung der Prüfung"
    # Build the DECOMPOSED (NFD) form at runtime so the source bytes really carry
    # base-letter + combining-diaeresis pairs, independent of file encoding.
    nfd_text = unicodedata.normalize("NFD", composed)
    assert nfd_text != composed and COMBINING_DIAERESIS in nfd_text  # sanity
    res = _create_text(client, project_id, csrf, "NFD", nfd_text)
    assert res.status_code == 201, res.text
    db = SessionLocal()
    try:
        version = db.get(SourceVersion, res.json()["current_source_version_id"])
        # NFKC re-composed each base+combining pair into a single code point.
        assert composed in version.normalized_text
        assert COMBINING_DIAERESIS not in version.normalized_text
    finally:
        db.close()


def test_identical_umlaut_input_has_stable_hashes(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    first = _create_text(client, project_id, csrf, "A", GERMAN).json()
    second = _create_text(client, project_id, csrf, "B", GERMAN).json()
    db = SessionLocal()
    try:
        v1 = db.get(SourceVersion, first["current_source_version_id"])
        v2 = db.get(SourceVersion, second["current_source_version_id"])
        assert v1.original_content_hash == v2.original_content_hash
        assert v1.normalized_content_hash == v2.normalized_content_hash
        assert len(v1.original_content_hash) == 64  # SHA-256 hex
    finally:
        db.close()


def test_umlaut_txt_upload_processed(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf)
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = uuid.uuid4().hex
    res = client.post(
        f"/api/v1/projects/{project_id}/sources/files",
        files=[("files", ("notiz.txt", GERMAN.encode("utf-8"), "text/plain"))],
        data={"data_classification_json": json.dumps(VALID_CLASSIFICATION)},
        headers=headers,
    )
    assert res.status_code == 202, res.text
    source_id = res.json()[0]["source_id"]
    got = client.get(f"/api/v1/sources/{source_id}")
    assert got.json()["status"] == "processed", got.text
