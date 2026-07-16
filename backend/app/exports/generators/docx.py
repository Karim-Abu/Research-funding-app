"""Editable, snapshot-only Word working copy.

The document deliberately contains no run, field, hash, model or audit ids.
Those belong solely to ``technical-evidence-2``.
"""
from __future__ import annotations

import io
from datetime import datetime

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches

from app.exports.generators.common import (
    DRAFT_HEADER, NO_SUBMISSION, composite_parts, field_label, field_working_text,
    grouped_open_points,
)


_BULLET = "List Bullet"


def _char_info(field: dict) -> str:
    limit = field.get("character_limit")
    count = field.get("character_count", 0)
    return f"{count} / {limit} Zeichen" if limit else f"{count} Zeichen"


def _repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    tr_pr.append(header)


def _table(doc: Document, headings: list[str], rows: list[list[str]]):
    table = doc.add_table(rows=1, cols=len(headings))
    table.style = "Table Grid"
    table.autofit = False
    width = Inches(6.4 / len(headings))
    header = table.rows[0]
    _repeat_header(header)
    for cell, text in zip(header.cells, headings, strict=True):
        cell.width = width
        cell.text = text
    for values in rows:
        cells = table.add_row().cells
        for cell, text in zip(cells, values, strict=True):
            cell.width = width
            cell.text = text
    return table


def _money(value: object) -> str:
    if value is None:
        return "Nicht angegeben"
    if isinstance(value, (int, float)):
        return f"CHF {value:,.2f}".replace(",", "’")
    return str(value)


def _yes_no_unknown(value: object) -> str:
    if value is True:
        return "Ja"
    if value is False:
        return "Nein"
    return "Nicht angegeben"


def _main_chapter(doc: Document, title: str) -> None:
    doc.add_page_break()
    doc.add_heading(title, level=1)


def _source_rows(snapshot: dict) -> list[list[str]]:
    sources = {s["source_id"]: s for s in snapshot["structured"].get("sources", [])}
    by_source: dict[str, list[dict]] = {}
    for anchor in snapshot.get("evidence_anchors", []):
        if anchor.get("source_id") in sources:
            by_source.setdefault(anchor["source_id"], []).append(anchor)
    rows: list[list[str]] = []
    for source_id, source in sources.items():
        anchors = by_source.get(source_id, [])
        if not anchors:
            rows.append([source["title"], source.get("url") or "Kein öffentlicher Link", "Keine Fundstelle", "Nicht beurteilt"])
            continue
        for anchor in anchors:
            location = anchor.get("section") or (f"S. {anchor['page']}" if anchor.get("page") is not None else "Fundstelle ohne Seitenangabe")
            rows.append([
                source["title"], source.get("url") or "Kein öffentlicher Link",
                f"{location}; Fundstelle: {anchor.get('verification_status', 'unverified')}",
                f"Inhaltliche Stützung: {anchor.get('support_status') or 'nicht beurteilt'}",
            ])
    return rows


def generate_docx(snapshot: dict, snapshot_hash: str) -> bytes:  # noqa: ARG001 - technical hash is intentionally excluded
    meta = snapshot["meta"]
    review = snapshot["review"]
    structured = snapshot["structured"]
    doc = Document()
    styles = doc.styles
    styles["Normal"].font.name = "Aptos"
    styles["Normal"]._element.rPr.rFonts.set(qn("w:eastAsia"), "Aptos")
    if "Export Note" not in styles:
        styles.add_style("Export Note", WD_STYLE_TYPE.PARAGRAPH)
        styles["Export Note"].font.italic = True

    frozen = datetime.fromisoformat(meta["frozen_at"]).replace(tzinfo=None)
    cp = doc.core_properties
    cp.title = meta["project_title"]
    cp.author = "Evidenzbasierte Proposal-Unterstützung"
    cp.last_modified_by = "export"
    cp.created = frozen
    cp.modified = frozen
    cp.revision = 1

    # Page 1: the work instruction and every formal risk are visible before text.
    doc.add_heading(meta["project_title"], level=0)
    doc.add_paragraph().add_run(DRAFT_HEADER).bold = True
    doc.add_paragraph("Arbeitsanweisung: Inhalte prüfen, in Innolink manuell übertragen und dort vollständig ergänzen.")
    doc.add_paragraph(NO_SUBMISSION)
    if structured.get("stale_message"):
        doc.add_paragraph(structured["stale_message"], style="Export Note")
    if not structured.get("snapshot_available"):
        doc.add_paragraph("Formaler Hinweis: Der strukturierte Run-Snapshot fehlt. Partner, Budget und Dauer sind nicht exportiert.", style="Export Note")
    blockers = review.get("blocker_count", 0)
    warnings = review.get("warning_count", 0)
    if blockers or warnings:
        doc.add_paragraph(f"Formale Prüfhinweise: {blockers} Blocker, {warnings} Warnungen. Diese Arbeitskopie bleibt dennoch bearbeitbar.", style="Export Note")
    else:
        doc.add_paragraph("Formaler Status: Keine gezählten Blocker oder Warnungen im eingefrorenen Reviewstand. Dies ist dennoch keine Einreichfreigabe.", style="Export Note")

    _main_chapter(doc, "Projektmetadaten")
    project = structured.get("project", {})
    doc.add_paragraph(f"Förderinstrument: {project.get('instrument', 'Nicht angegeben')}")
    duration = project.get("duration_months")
    doc.add_paragraph(f"Dauer: {duration} Monate" if duration is not None else "Dauer: Nicht angegeben")
    doc.add_paragraph("Antragssprache: noch in Innolink festlegen")

    _main_chapter(doc, "Partner")
    partners = structured.get("partners", [])
    if not partners:
        doc.add_paragraph("Keine Partner im Run-Snapshot vorhanden.")
    else:
        _table(doc, ["Partner", "Typ", "Rolle", "Schweiz-Bezug", "Eligibility-Prüfstatus", "Provenienz"], [
            [p["name"], p.get("partner_type_label", p["partner_type"]), p["project_role"], _yes_no_unknown(p.get("swiss_value_creation")), p.get("eligibility_status_label", p["eligibility_status"]), p["provenance"]]
            for p in partners
        ])

    _main_chapter(doc, "Budgetübersicht")
    budget = structured.get("budget", {})
    values = budget.get("values", [])
    if values:
        _table(doc, ["Position", "Wert", "Provenienz"], [[v["label"], _money(v.get("value")), v["provenance"]] for v in values])
    else:
        doc.add_paragraph("Budgetwerte sind im Run-Snapshot nicht vorhanden.")
    if budget.get("ratios"):
        doc.add_heading("Relevante Quoten", level=2)
        for ratio in budget["ratios"]:
            doc.add_paragraph(f"{ratio['label']}: {ratio['value']:.1%}", style=_BULLET)
    if budget.get("rules"):
        doc.add_heading("Status der eingefrorenen Regeln", level=2)
        for rule in budget["rules"]:
            doc.add_paragraph(rule.get("status_label", rule["status"]), style=_BULLET)

    _main_chapter(doc, "Narrative Innolink-Felder")
    for field in snapshot["fields"]:
        doc.add_heading(field_label(field), level=2)
        text, notice = field_working_text(snapshot, field)
        parts, structure_warning = composite_parts(field)
        if parts and text == field.get("text", ""):
            for marker, label, section_text in parts:
                doc.add_heading(f"{marker} {label}", level=3)
                doc.add_paragraph(section_text)
        else:
            doc.add_paragraph(text)
        if notice:
            doc.add_paragraph(notice, style="Export Note")
        if structure_warning:
            doc.add_paragraph(structure_warning, style="Export Note")
        doc.add_paragraph(_char_info(field), style="Export Note")

    _main_chapter(doc, "Offene Aufgaben")
    groups = grouped_open_points(snapshot)
    if not groups:
        doc.add_paragraph("Keine offenen Aufgaben erfasst.")
    else:
        for group, entries in groups:
            doc.add_heading(group, level=2)
            for entry in entries:
                doc.add_paragraph(entry, style=_BULLET)

    _main_chapter(doc, "Quellenverzeichnis")
    source_rows = _source_rows(snapshot)
    if source_rows:
        _table(doc, ["Titel", "Link", "Fundstellen-Prüfstatus", "Inhaltlicher Stützstatus"], source_rows)
    else:
        doc.add_paragraph("Keine run-gebundenen Quellen vorhanden.")

    _main_chapter(doc, "Noch manuell in Innolink zu erfassen")
    for task in structured.get("manual_portal_tasks", []):
        doc.add_paragraph(task, style=_BULLET)
    doc.add_paragraph("Antragssprache festlegen", style=_BULLET)
    doc.add_paragraph("Die Übertragung erfolgt manuell; dieser Export synchronisiert oder reicht nichts ein.")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
