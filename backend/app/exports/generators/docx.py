"""Deterministic DOCX export (Milestone 8) via python-docx.

Structurally and semantically deterministic: current draft text only, canonical
field order, normalized core document properties + the frozen snapshot timestamp
(no system clock). Editable Word working document; never byte-asserted.
"""
from __future__ import annotations

import io
from datetime import datetime

from docx import Document

from app.exports.generators.common import (
    APPROVED_STATUS,
    COVERAGE_TITLE,
    DRAFT_BODY,
    DRAFT_HEADER,
    NO_SUBMISSION,
)


_BULLET = "List Bullet"


def _char_info(field: dict) -> str:
    limit = field.get("character_limit")
    count = field.get("character_count", 0)
    return f"{count} / {limit} Zeichen" if limit else f"{count} Zeichen"


def generate_docx(snapshot: dict, snapshot_hash: str) -> bytes:
    meta = snapshot["meta"]
    review = snapshot["review"]
    draft = meta["draft_marked"]
    doc = Document()

    # Normalize core properties to frozen, fixed values (reproducible metadata).
    frozen = datetime.fromisoformat(meta["frozen_at"]).replace(tzinfo=None)
    cp = doc.core_properties
    cp.title = meta["project_title"]
    cp.author = "Evidenzbasierte Proposal-Unterstützung"
    cp.last_modified_by = "export"
    cp.created = frozen
    cp.modified = frozen
    cp.revision = 1

    doc.add_heading(meta["project_title"], level=0)
    if draft:
        doc.add_paragraph().add_run(DRAFT_HEADER).bold = True
        doc.add_paragraph(DRAFT_BODY)
    else:
        doc.add_paragraph().add_run(APPROVED_STATUS).bold = True

    doc.add_heading("Metadaten", level=1)
    doc.add_paragraph(f"Förderinstrument: {meta['funding_profile_id']}")
    doc.add_paragraph(f"Run: {meta['run_id']}")
    doc.add_paragraph(f"Erstellt am: {meta['frozen_at']}")
    doc.add_paragraph(
        "Review-Status: " + ("ENTWURF" if draft else "review-freigegeben")
    )
    doc.add_paragraph(f"Review-Paket-Version: {review['review_package_version']}")
    doc.add_paragraph(f"Snapshot-Hash: {snapshot_hash}")
    doc.add_paragraph(NO_SUBMISSION)

    cov = snapshot["coverage"]
    doc.add_heading(COVERAGE_TITLE, level=1)
    doc.add_paragraph(cov["note"])
    doc.add_paragraph("Exportierte unterstützte Felder:")
    for field_id in cov["supported_field_ids"]:
        doc.add_paragraph(field_id, style=_BULLET)
    doc.add_paragraph("Noch nicht enthaltene Bereiche:")
    for area in cov["deferred_areas"]:
        doc.add_paragraph(area, style=_BULLET)

    doc.add_heading("Portalfelder", level=1)
    for field in snapshot["fields"]:
        doc.add_heading(field["field_name"], level=2)
        doc.add_paragraph(field["text"])
        doc.add_paragraph().add_run(_char_info(field)).italic = True
        active = [
            link for link in field["evidence_links"] if link["status"] == "active"
        ]
        if active:
            doc.add_paragraph(f"Belege: {len(active)} aktive Verknüpfung(en)")

    doc.add_heading("Anhang: Offene Punkte und Review-Hinweise", level=1)
    issues = snapshot["open_issues"]
    open_findings = [
        f for f in snapshot["review_findings"] if f["status"] == "open"
    ]
    if not issues and not open_findings:
        doc.add_paragraph("Keine offenen Punkte erfasst.")
    else:
        for issue in issues:
            doc.add_paragraph(
                f"[{issue['severity']}] {issue['description']}", style=_BULLET
            )
        for finding in open_findings:
            doc.add_paragraph(
                f"[{finding['severity']}] {finding['description']}",
                style=_BULLET,
            )

    doc.add_heading("Anhang: Technische Nachvollziehbarkeit", level=1)
    doc.add_paragraph(f"Run: {meta['run_id']}")
    doc.add_paragraph(f"Review-Paket-Version: {review['review_package_version']}")
    doc.add_paragraph(f"Approval-Scope-Hash: {review['approval_scope_hash']}")
    versions = snapshot["config_versions"]
    doc.add_paragraph(
        "Registries: requirement="
        f"{versions['requirement_registry_version']}, rule="
        f"{versions['rule_registry_version']}, portal_fields="
        f"{versions['portal_field_profile_version']}"
    )

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
