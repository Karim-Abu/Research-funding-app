"""Deterministic UTF-8 Markdown export (Milestone 8).

Byte-deterministic for an identical frozen snapshot: current draft text only,
canonical field order, stable `\\n` line endings, no HTML, no AI prose.
"""
from __future__ import annotations

from app.exports.generators.common import (
    APPROVED_STATUS,
    COVERAGE_TITLE,
    DRAFT_BODY,
    DRAFT_HEADER,
    NO_SUBMISSION,
)


def _char_info(field: dict) -> str:
    limit = field.get("character_limit")
    count = field.get("character_count", 0)
    return f"{count} / {limit} Zeichen" if limit else f"{count} Zeichen"


def generate_markdown(snapshot: dict, snapshot_hash: str) -> bytes:
    meta = snapshot["meta"]
    review = snapshot["review"]
    draft = meta["draft_marked"]
    lines: list[str] = []

    lines.append(f"# {meta['project_title']}")
    lines.append("")
    if draft:
        lines.append(f"**{DRAFT_HEADER}**")
        lines.append("")
        lines.append(DRAFT_BODY)
    else:
        lines.append(f"**{APPROVED_STATUS}**")
    lines.append("")
    lines.append(f"- Förderinstrument: {meta['funding_profile_id']}")
    lines.append(f"- Run: {meta['run_id']}")
    lines.append("- Export-Status: available")
    lines.append(
        "- Review-Status: "
        + ("ENTWURF" if draft else "review-freigegeben")
    )
    lines.append(f"- Review-Paket-Version: {review['review_package_version']}")
    lines.append(f"- Erstellt am: {meta['frozen_at']}")
    lines.append(f"- Snapshot-Hash: {snapshot_hash}")
    lines.append("")
    lines.append(f"> {NO_SUBMISSION}")
    lines.append("")

    cov = snapshot["coverage"]
    lines.append(f"## {COVERAGE_TITLE}")
    lines.append("")
    lines.append(cov["note"])
    lines.append("")
    lines.append("Exportierte unterstützte Felder:")
    for field_id in cov["supported_field_ids"]:
        lines.append(f"- {field_id}")
    lines.append("")
    lines.append("Noch nicht enthaltene Bereiche:")
    for area in cov["deferred_areas"]:
        lines.append(f"- {area}")
    lines.append("")

    lines.append("## Portalfelder")
    lines.append("")
    for field in snapshot["fields"]:
        lines.append(f"### {field['field_name']}")
        lines.append("")
        lines.append(field["text"])
        lines.append("")
        lines.append(f"_{_char_info(field)}_")
        active = [
            link for link in field["evidence_links"] if link["status"] == "active"
        ]
        if active:
            lines.append("")
            lines.append(f"Belege: {len(active)} aktive Verknüpfung(en)")
        lines.append("")

    lines.append("## Offene Punkte")
    lines.append("")
    issues = snapshot["open_issues"]
    open_findings = [
        f for f in snapshot["review_findings"] if f["status"] == "open"
    ]
    if not issues and not open_findings:
        lines.append("Keine offenen Punkte erfasst.")
        lines.append("")
    else:
        for issue in issues:
            lines.append(
                f"- [{issue['severity']}] {issue['description']}"
            )
        for finding in open_findings:
            lines.append(
                f"- [{finding['severity']}] {finding['description']}"
            )
        lines.append("")

    lines.append("## Evidenzübersicht")
    lines.append("")
    if not snapshot["evidence_anchors"]:
        lines.append("Keine Fundstellen erfasst.")
        lines.append("")
    else:
        for anchor in snapshot["evidence_anchors"]:
            loc = anchor.get("page")
            loc_str = f", S. {loc}" if loc is not None else ""
            lines.append(
                f"- {anchor['source_name']}{loc_str} "
                f"[{anchor['verification_status']}]: „{anchor['quote']}“"
            )
        lines.append("")

    return ("\n".join(lines) + "\n").encode("utf-8")
