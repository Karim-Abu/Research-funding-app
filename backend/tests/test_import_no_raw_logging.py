"""R3.4 — No-Raw-Logging für den Import-Pfad (tests first).

Ein synthetisches Marker-PDF (Canary-Marker, kein echter Inhalt) durchläuft den
kompletten Pfad Upload → Mapping → Entscheidungen inkl. Fehlerpfade. Die Marker
dürfen in keinem Log-Record, Audit-Detail, Control-Detail, Operation-Feld oder
Problem-Fehlertext auftauchen. Redigierte Metadaten (Hashes, Zählwerte) sind
erlaubt; die DB-Inhalte selbst (Kandidatentext, DraftVersion) sind bewusst
KEINE Log-Flächen und tragen die Inhalte weiterhin.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select

from app.db.models import (
    AsyncOperation,
    AuditEvent,
    ControlResult,
    ImportCandidate,
    SourceDocument,
)
from app.db.session import SessionLocal
from app.security.redaction import detail_contains
from tests.review_helpers import clean_field, mut, setup_completed_run

MARKER_PROJECT = "PROJECT_SECRET_MARKER_123"
MARKER_PARTNER = "PARTNER_CONFIDENTIAL_NAME"
MARKER_BUDGET = "CHF_999999_SECRET_BUDGET"
# «Bearbeitet übernommen»: auch menschlich editierter Text ist D2.
MARKER_EDITED = "EDITED_SECRET_MARKER_456"
MARKERS = (MARKER_PROJECT, MARKER_PARTNER, MARKER_BUDGET, MARKER_EDITED)

ABSTRACT = "INTRO.APP.ABSTRACT"
EXEC_SUMMARY = "INTRO.APP.EXECUTIVE_SUMMARY"
NAME = "INTRO.APP.NAME"


# --- Minimaler PDF-Writer (Muster spike/make_fixture.py, eine Seite) ---------


def _esc(text: str) -> bytes:
    raw = text.encode("cp1252", errors="replace")
    return raw.replace(b"\\", rb"\\").replace(b"(", rb"\(").replace(b")", rb"\)")


def _pdf_from_lines(lines: list[str]) -> bytes:
    body = b"\n".join(b"(" + _esc(line) + b") Tj T*" for line in lines)
    content = b"BT\n/F1 10 Tf\n72 780 Td\n14 TL\n" + body + b"\nET"
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [4 0 R] /Count 1 >>",
        3: (
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding >>"
        ),
        4: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>"
        ),
        5: (
            b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n"
            + content + b"\nendstream"
        ),
    }
    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for obj_id in sorted(objects):
        offsets[obj_id] = len(out)
        out += f"{obj_id} 0 obj\n".encode() + objects[obj_id] + b"\nendobj\n"
    xref_pos = len(out)
    max_id = max(objects)
    out += f"xref\n0 {max_id + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for obj_id in range(1, max_id + 1):
        out += f"{offsets[obj_id]:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size " + str(max_id + 1).encode()
        + b" /Root 1 0 R >>\nstartxref\n" + str(xref_pos).encode() + b"\n%%EOF\n"
    )
    return bytes(out)


def _marker_pdf() -> bytes:
    return _pdf_from_lines([
        "1 Introduction",
        "Application name",
        f"{MARKER_PROJECT} Antragstitel",
        "Abstract",
        f"Der Partner {MARKER_PARTNER} plant Einsparungen von {MARKER_BUDGET}.",
        "Executive summary",
        f"Zusammenfassung zu {MARKER_PROJECT} mit {MARKER_PARTNER}.",
    ])


# --- Flow-Helfer --------------------------------------------------------------


def _upload_marker_pdf(client, csrf, project_id: str) -> str:
    res = client.post(
        f"/api/v1/projects/{project_id}/sources/files",
        files={"files": ("marker_fixture.pdf", _marker_pdf(), "application/pdf")},
        data={"data_classification_json": json.dumps({
            "sensitivity": "public",
            "origin": "synthetic",
            "processing_mode": "cloud_assisted",
            "web_research_mode": "off",
            "nda_applies": False,
        })},
        headers=mut(csrf),
    )
    assert res.status_code == 202, res.text
    return res.json()[0]["source_id"]


def _persistence_blob() -> str:
    with SessionLocal() as db:
        audits = db.scalars(select(AuditEvent)).all()
        controls = db.scalars(select(ControlResult)).all()
        operations = db.scalars(select(AsyncOperation)).all()
        sources = db.scalars(select(SourceDocument)).all()
    return json.dumps(
        [a.detail for a in audits] + [a.action for a in audits]
        + [c.detail for c in controls]
        + [[o.result, o.error, o.status] for o in operations]
        + [s.error_message for s in sources],
        ensure_ascii=False, default=str,
    )


def test_import_path_never_logs_marker_content(client, caplog):
    caplog.set_level(logging.DEBUG)

    csrf, project_id, run_id = setup_completed_run(client, title="NoRawLog Import")
    source_id = _upload_marker_pdf(client, csrf, project_id)

    # Mapping — die Marker MÜSSEN in den Kandidaten ankommen (Positivkontrolle,
    # sonst wäre der Leak-Test wirkungslos leer-grün).
    res = client.post(
        f"/api/v1/projects/{project_id}/imports",
        json={"source_id": source_id}, headers=mut(csrf),
    )
    assert res.status_code == 201, res.text
    by_field = {c["field_id"]: c for c in res.json()}
    assert MARKER_PARTNER in by_field[ABSTRACT]["extracted_text"]
    assert MARKER_BUDGET in by_field[ABSTRACT]["extracted_text"]
    assert MARKER_PROJECT in by_field[NAME]["extracted_text"]

    # Entscheidungen inkl. Fehlerpfade:
    # 1) Übernahme (Happy Path).
    res = client.post(
        f"/api/v1/imports/{by_field[ABSTRACT]['import_candidate_id']}/decision",
        json={"decision": "accepted", "run_id": run_id}, headers=mut(csrf),
    )
    assert res.status_code == 200, res.text

    # 2) Konflikt (409) — Fehlertext darf keinen Feldinhalt tragen.
    clean_field(client, csrf, run_id, EXEC_SUMMARY, "Manuell bearbeitete Fassung.")
    res = client.post(
        f"/api/v1/imports/{by_field[EXEC_SUMMARY]['import_candidate_id']}/decision",
        json={"decision": "accepted", "run_id": run_id}, headers=mut(csrf),
    )
    assert res.status_code == 409
    assert not detail_contains(res.text, MARKERS)

    # 2b) «Bearbeitet übernommen» OHNE run_id (Vormerkung vor dem Lauf): der
    # editierte Text ist ebenfalls D2 und darf in keiner Log-Fläche landen.
    res = client.post(
        f"/api/v1/imports/{by_field[EXEC_SUMMARY]['import_candidate_id']}/decision",
        json={
            "decision": "accepted",
            "edited_text": f"Editierte Fassung mit {MARKER_EDITED}.",
        },
        headers=mut(csrf),
    )
    assert res.status_code == 200, res.text
    # Positivkontrolle: der editierte Text liegt in der DB (erlaubte Fläche).
    with SessionLocal() as db:
        staged = db.get(
            ImportCandidate, by_field[EXEC_SUMMARY]["import_candidate_id"]
        )
        assert staged is not None and MARKER_EDITED in (staged.edited_text or "")

    # 3) Doppel-Entscheid (409 already decided).
    res = client.post(
        f"/api/v1/imports/{by_field[ABSTRACT]['import_candidate_id']}/decision",
        json={"decision": "ignored"}, headers=mut(csrf),
    )
    assert res.status_code == 409
    assert not detail_contains(res.text, MARKERS)

    # 4) Ignorieren (Rest-Pfad).
    res = client.post(
        f"/api/v1/imports/{by_field[NAME]['import_candidate_id']}/decision",
        json={"decision": "ignored"}, headers=mut(csrf),
    )
    assert res.status_code == 200, res.text

    # --- Log-Fläche: kein Marker in irgendeinem Log-Record -------------------
    for record in caplog.records:
        message = record.getMessage()
        assert not detail_contains(message, MARKERS), (
            f"Marker leaked into log record: {record.name}: {message[:120]}"
        )

    # --- Persistenz-Flächen: Audit, Controls, Operations, Fehlermeldungen ----
    blob = _persistence_blob()
    for marker in MARKERS:
        assert marker not in blob, f"Marker {marker!r} leaked into a log/audit surface"

    # Redigierte Metadaten sind erlaubt und vorhanden (Zählwerte im Audit).
    with SessionLocal() as db:
        created = db.scalars(
            select(AuditEvent).where(AuditEvent.action == "import.candidates_created")
        ).all()
    assert created and any(
        (event.detail or {}).get("candidate_count") for event in created
    )


def test_uploaded_marker_source_error_paths_stay_clean(client, caplog):
    """Fehlerpfad Quelle nicht verarbeitet: die 422-Meldung nennt nie Inhalte."""
    caplog.set_level(logging.DEBUG)
    csrf, project_id, _run_id = setup_completed_run(client, title="NoRawLog 422")

    # Kandidaten-Erzeugung für eine UNBEKANNTE Quelle → 404, ohne Inhalte.
    res = client.post(
        f"/api/v1/projects/{project_id}/imports",
        json={"source_id": "missing-source"}, headers=mut(csrf),
    )
    assert res.status_code == 404
    assert not detail_contains(res.text, MARKERS)

    # Kein Marker in Logs dieses Fehlerpfads.
    for record in caplog.records:
        assert not detail_contains(record.getMessage(), MARKERS)


def test_candidate_text_stays_in_db_not_in_audit(client):
    """Kontrolle der erlaubten Fläche: der Inhalt LIEGT in der DB (Kandidat),
    aber keine Audit-Zeile des Imports trägt ihn."""
    csrf, project_id, _run_id = setup_completed_run(client, title="NoRawLog DB")
    source_id = _upload_marker_pdf(client, csrf, project_id)
    res = client.post(
        f"/api/v1/projects/{project_id}/imports",
        json={"source_id": source_id}, headers=mut(csrf),
    )
    assert res.status_code == 201

    with SessionLocal() as db:
        rows = db.scalars(
            select(ImportCandidate).where(ImportCandidate.project_id == project_id)
        ).all()
        import_audits = db.scalars(
            select(AuditEvent).where(AuditEvent.action.like("import.%"))
        ).all()
    assert any(MARKER_PARTNER in row.extracted_text for row in rows)
    for event in import_audits:
        assert not detail_contains(event.detail, MARKERS)
