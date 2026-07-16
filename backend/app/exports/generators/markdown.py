"""Compact, human-readable working summary from the frozen export snapshot."""
from __future__ import annotations

from app.exports.generators.common import (
    DRAFT_HEADER, NO_SUBMISSION, composite_parts, field_label, field_working_text,
    grouped_open_points,
)


def _money(value: object) -> str:
    if value is None:
        return "Nicht angegeben"
    if isinstance(value, (int, float)):
        return f"CHF {value:,.2f}".replace(",", "’")
    return str(value)


def _char_info(field: dict) -> str:
    return f"{field['character_count']} / {field['character_limit']} Zeichen" if field.get("character_limit") else f"{field['character_count']} Zeichen"


def _cell(value: object) -> str:
    return str(value or "Nicht angegeben").replace("|", "\\|").replace("\n", " ")


def generate_markdown(snapshot: dict, snapshot_hash: str) -> bytes:  # noqa: ARG001
    meta = snapshot["meta"]
    structured = snapshot["structured"]
    project = structured.get("project", {})
    lines = [
        f"# {meta['project_title']}", "", f"**{DRAFT_HEADER}**", "",
        "Diese Zusammenfassung ist eine bearbeitbare Arbeitskopie für die manuelle Übertragung nach Innolink.",
        "", f"> {NO_SUBMISSION}", "",
        "## Projektmetadaten", "",
        f"- Förderinstrument: {project.get('instrument', 'Nicht angegeben')}",
        f"- Dauer: {project.get('duration_months')} Monate" if project.get("duration_months") is not None else "- Dauer: Nicht angegeben",
        "- Antragssprache: noch in Innolink festlegen", "",
    ]
    if structured.get("stale_message"):
        lines.extend([f"> **Stale-Hinweis:** {structured['stale_message']}", ""])
    if not structured.get("snapshot_available"):
        lines.extend(["> **Snapshot-Mangel:** Partner, Budget und Dauer wurden nicht aus aktuellen Projektdaten ersetzt.", ""])

    lines.extend(["## Partner", ""])
    partners = structured.get("partners", [])
    if not partners:
        lines.extend(["Keine Partner im Run-Snapshot vorhanden.", ""])
    else:
        lines.extend(["| Partner | Typ | Rolle | Schweiz-Bezug | Eligibility-Prüfstatus | Provenienz |", "|---|---|---|---|---|---|"])
        for p in partners:
            swiss = "Ja" if p.get("swiss_value_creation") is True else "Nein" if p.get("swiss_value_creation") is False else "Nicht angegeben"
            lines.append("| " + " | ".join(_cell(v) for v in (p["name"], p.get("partner_type_label", p["partner_type"]), p["project_role"], swiss, p.get("eligibility_status_label", p["eligibility_status"]), p["provenance"])) + " |")
        lines.append("")

    lines.extend(["## Budgetübersicht", ""])
    values = structured.get("budget", {}).get("values", [])
    if values:
        lines.extend(["| Position | Wert | Provenienz |", "|---|---:|---|"])
        lines.extend(f"| {_cell(v['label'])} | {_money(v.get('value'))} | {_cell(v['provenance'])} |" for v in values)
    else:
        lines.append("Budgetwerte sind im Run-Snapshot nicht vorhanden.")
    lines.append("")
    for ratio in structured.get("budget", {}).get("ratios", []):
        lines.append(f"- {ratio['label']}: {ratio['value']:.1%}")
    for rule in structured.get("budget", {}).get("rules", []):
        lines.append(f"- Regelstatus: {rule.get('status_label', rule['status'])}")
    lines.append("")

    lines.extend(["## Narrative Innolink-Felder", ""])
    for field in snapshot["fields"]:
        lines.extend([f"### {field_label(field)}", ""])
        text, notice = field_working_text(snapshot, field)
        parts, structure_warning = composite_parts(field)
        if parts and text == field.get("text", ""):
            for marker, label, section_text in parts:
                lines.extend([f"#### {marker} {label}", "", section_text, ""])
        else:
            lines.extend([text, ""])
        if notice:
            lines.extend([f"_{notice}_", ""])
        if structure_warning:
            lines.extend([f"_{structure_warning}_", ""])
        lines.extend([f"_{_char_info(field)}_", ""])

    lines.extend(["## Offene Aufgaben", ""])
    groups = grouped_open_points(snapshot)
    if not groups:
        lines.append("Keine offenen Aufgaben erfasst.")
    for group, entries in groups:
        lines.extend([f"### {group}", ""])
        lines.extend(f"- {entry}" for entry in entries)
        lines.append("")
    lines.append("")

    lines.extend(["## Quellenverzeichnis", ""])
    sources = {s["source_id"]: s for s in structured.get("sources", [])}
    anchors = snapshot.get("evidence_anchors", [])
    if not sources:
        lines.append("Keine run-gebundenen Quellen vorhanden.")
    for source_id, source in sources.items():
        source_anchors = [a for a in anchors if a.get("source_id") == source_id]
        if not source_anchors:
            lines.append(f"- {source['title']} — {source.get('url') or 'Kein öffentlicher Link'}; Fundstelle: nicht erfasst; inhaltliche Stützung: nicht beurteilt")
        for anchor in source_anchors:
            location = anchor.get("section") or (f"S. {anchor['page']}" if anchor.get("page") is not None else "ohne Seitenangabe")
            lines.append(f"- {source['title']} — {source.get('url') or 'Kein öffentlicher Link'}; {location}; Fundstelle: {anchor.get('verification_status', 'unverified')}; inhaltliche Stützung: {anchor.get('support_status') or 'nicht beurteilt'}")
    lines.append("")

    lines.extend(["## Noch manuell in Innolink zu erfassen", ""])
    lines.extend(f"- {task}" for task in structured.get("manual_portal_tasks", []))
    lines.extend(["- Antragssprache festlegen", "- Übertragung und Einreichung erfolgen nie automatisch.", ""])
    return ("\n".join(lines) + "\n").encode("utf-8")
