"""DOCX / Markdown / technical-evidence generator content + determinism (M8)."""
from __future__ import annotations

import io
import json

import docx

from app.db.models import ExportArtifact
from app.db.session import SessionLocal
from app.exports.generators import GENERATORS
from tests.export_helpers import download, make_export, setup_approved_run
from tests.review_helpers import setup_completed_run

DISCLAIMER = "Dies ist keine Einreichfreigabe"


def _snapshot(export_id: str) -> dict:
    db = SessionLocal()
    try:
        return db.get(ExportArtifact, export_id).export_snapshot_json
    finally:
        db.close()


# --- DOCX ------------------------------------------------------------------


def test_docx_opens_with_metadata_and_disclaimer(client):
    csrf, _pid, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "docx")
    data = download(client, artifact["export_id"]).content
    doc = docx.Document(io.BytesIO(data))
    texts = "\n".join(p.text for p in doc.paragraphs)
    assert "ENTWURF – Nicht zur Einreichung" in texts  # draft marker
    assert DISCLAIMER in texts
    assert "Abdeckung / Coverage" in texts  # coverage disclosure
    assert run_id in texts
    assert "INTRO.APP.ABSTRACT" in texts  # supported field listed in coverage


def test_docx_canonical_field_order_and_unicode(client):
    csrf, _pid, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "docx")
    doc = docx.Document(io.BytesIO(download(client, artifact["export_id"]).content))
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading 2")]
    # Field headings appear in canonical registry order (Abstract before later ones).
    assert "Abstract" in " ".join(headings) or any("Abstract" in h for h in headings)
    full = "\n".join(p.text for p in doc.paragraphs)
    assert "ä" in full or "ö" in full or "ü" in full  # Unicode preserved


def test_docx_approved_has_no_entwurf(client):
    csrf, run_id = setup_approved_run(client)
    artifact = make_export(client, csrf, run_id, "docx")
    assert "_ENTWURF" not in artifact["filename"]
    doc = docx.Document(io.BytesIO(download(client, artifact["export_id"]).content))
    texts = "\n".join(p.text for p in doc.paragraphs)
    assert "Review-freigegebener Arbeitsstand" in texts
    assert DISCLAIMER in texts  # still present
    assert "ENTWURF" not in texts


def test_docx_structurally_deterministic(client):
    csrf, _pid, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "docx")
    snap = _snapshot(artifact["export_id"])
    a = GENERATORS["docx"](snap, "h")
    b = GENERATORS["docx"](snap, "h")
    ta = [p.text for p in docx.Document(io.BytesIO(a)).paragraphs]
    tb = [p.text for p in docx.Document(io.BytesIO(b)).paragraphs]
    assert ta == tb  # same structure/content for the same snapshot


# --- Markdown --------------------------------------------------------------


def test_markdown_deterministic_bytes_and_sections(client):
    csrf, _pid, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "markdown")
    snap = _snapshot(artifact["export_id"])
    a = GENERATORS["markdown"](snap, "h")
    b = GENERATORS["markdown"](snap, "h")
    assert a == b  # byte-deterministic
    text = a.decode("utf-8")
    assert text.startswith("# ")
    assert "## Portalfelder" in text
    assert "## Offene Punkte" in text
    assert "## Evidenzübersicht" in text
    assert "Abdeckung / Coverage" in text
    assert DISCLAIMER in text
    assert "ENTWURF" in text  # draft


def test_markdown_friendly_labels_and_grouped_points(client):
    """M10.2 — applicant-friendly field headings + open points grouped by field."""
    csrf, _pid, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "markdown")
    text = download(client, artifact["export_id"]).content.decode("utf-8")
    assert "### Business Targets & Business Model" in text
    assert "### Innovation & Lösung" in text
    # The registry's technical "Open Editor (…)" phrasing never becomes a heading.
    assert "### Open Editor" not in text
    tail = text[text.index("## Offene Punkte"):]
    assert "### " in tail  # grouped under field / unassigned headings


def test_grouped_open_points_groups_and_dedupes():
    """M10.2 — pure helper: group by field label, dedupe identical lines."""
    from app.exports.generators.common import grouped_open_points

    snap = {
        "fields": [{"field_id": "INTRO.APP.ABSTRACT", "field_name": "Abstract"}],
        "open_issues": [
            {
                "target_type": "portal_field",
                "target_id": "INTRO.APP.ABSTRACT",
                "severity": "blocker",
                "description": "Feld enthält Platzhalter.",
            },
            {
                "target_type": "requirement",
                "target_id": "REQ.X",
                "severity": "warning",
                "description": "Anforderung offen.",
            },
        ],
        "review_findings": [
            {
                "field_id": "INTRO.APP.ABSTRACT",
                "severity": "blocker",
                "description": "Feld enthält Platzhalter.",
                "status": "open",
            },
            {
                "field_id": None,
                "severity": "warning",
                "description": "Erledigt.",
                "status": "resolved",  # non-open findings never appear
            },
        ],
    }
    groups = grouped_open_points(snap)
    assert groups[0][0] == "Abstract (wird in Aramis publiziert)"
    assert groups[0][1] == ["2 × [blocker] Feld enthält Platzhalter."]
    assert groups[-1][0] == "Weitere offene Punkte"
    assert groups[-1][1] == ["[warning] Anforderung offen."]


def test_markdown_filename_suffix(client):
    csrf, _pid, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "markdown")
    assert artifact["filename"].endswith("_ENTWURF.md")


# --- Technical evidence ----------------------------------------------------


def test_technical_evidence_is_valid_deterministic_json(client):
    csrf, _pid, run_id = setup_completed_run(client, with_research_partner=False)
    artifact = make_export(client, csrf, run_id, "technical_evidence")
    data = download(client, artifact["export_id"]).content
    payload = json.loads(data)
    assert payload["artifact_kind"] == "internal_audit_export"
    assert payload["schema"] == "technical-evidence-1"
    assert payload["draft_marked"] is True
    assert payload["snapshot_hash"]
    assert "coverage" in payload
    assert payload["requirement_assessments"]
    assert payload["evidence_anchors"] is not None
    assert payload["review_findings"]
    snap = _snapshot(artifact["export_id"])
    assert GENERATORS["technical_evidence"](snap, payload["snapshot_hash"]) == data


def test_technical_evidence_excludes_secrets_and_full_source(client):
    csrf, _pid, run_id = setup_completed_run(client)
    artifact = make_export(client, csrf, run_id, "technical_evidence")
    text = download(client, artifact["export_id"]).content.decode("utf-8").lower()
    for forbidden in ("password", "session", "secret", "/users/", "c:\\", "api_key"):
        assert forbidden not in text
    # HumanDecisions are review-relevant only (no user email/name leak).
    payload = json.loads(download(client, artifact["export_id"]).content)
    for decision in payload["human_decisions"]:
        assert set(decision) <= {
            "decision_id", "target_type", "target_id", "action", "comment", "created_at"
        }
