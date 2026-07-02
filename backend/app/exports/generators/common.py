"""Shared export-generator helpers: filenames, disclaimers, labels (M8)."""
from __future__ import annotations

import re
import unicodedata

from app.exports import EXPORT_EXTENSIONS

# Fixed wording (truthful; never implies submission/funding approval).
NO_SUBMISSION = (
    "Dies ist keine Einreichfreigabe. Die Einreichung erfolgt durch die "
    "verantwortlichen Personen im Innosuisse-Portal."
)
DRAFT_HEADER = "ENTWURF – Nicht zur Einreichung"
DRAFT_BODY = (
    "Dieser Export ist nicht review-freigegeben oder wurde ausdrücklich als "
    "Entwurf erzeugt."
)
APPROVED_STATUS = "Review-freigegebener Arbeitsstand"
COVERAGE_TITLE = "Abdeckung / Coverage"

_TYPE_LABEL = {
    "docx": "Arbeitsdokument",
    "markdown": "Zusammenfassung",
    "technical_evidence": "Technischer_Nachweis",
}

# M10.2 — user-facing heading labels for the DOCX/Markdown exports. The
# snapshot's ``field_name`` mirrors the registry ``label_or_question`` (e.g.
# "Open Editor (Editor für Business Targets & Business Model)"), which reads
# technical in an applicant-facing document. Display mapping only: snapshot,
# contracts and the technical_evidence export are untouched; unknown ids fall
# back to the stored field_name.
EXPORT_FIELD_LABELS: dict[str, str] = {
    "INTRO.APP.NAME": "Projekttitel (Application name)",
    "INTRO.APP.NAME_EN": "Projekttitel (Englisch)",
    "INTRO.APP.ABSTRACT": "Abstract (wird in Aramis publiziert)",
    "INTRO.APP.EXECUTIVE_SUMMARY": "Executive Summary (wird nicht publiziert)",
    "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS": (
        "Erläuterungen zur finanziellen Unabhängigkeit"
    ),
    "VC.BUSINESS_TARGETS_MODEL.EDITOR": "Business Targets & Business Model",
    "SOL.INNOVATION_SOLUTION.EDITOR": "Innovation & Lösung",
    "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION": (
        "Erläuterung zur Verteilung der Management-Stunden"
    ),
}

UNASSIGNED_GROUP = "Weitere offene Punkte"


def field_label(field: dict) -> str:
    return EXPORT_FIELD_LABELS.get(
        field.get("field_id", ""), field.get("field_name", "")
    )


def grouped_open_points(snapshot: dict) -> list[tuple[str, list[str]]]:
    """Open issues + open review findings grouped by portal-field label, with
    identical descriptions deduplicated as "N × …" (M10.2 readability only —
    same underlying items as before, deterministic order: snapshot field order,
    then the unassigned group)."""
    label_by_field = {
        f["field_id"]: field_label(f) for f in snapshot["fields"]
    }
    order: list[str] = [label_by_field[f["field_id"]] for f in snapshot["fields"]]
    order.append(UNASSIGNED_GROUP)

    grouped: dict[str, dict[str, int]] = {}

    def add(group: str, severity: str, description: str) -> None:
        line = f"[{severity}] {description}"
        bucket = grouped.setdefault(group, {})
        bucket[line] = bucket.get(line, 0) + 1

    for issue in snapshot["open_issues"]:
        group = (
            label_by_field.get(issue.get("target_id", ""), UNASSIGNED_GROUP)
            if issue.get("target_type") == "portal_field"
            else UNASSIGNED_GROUP
        )
        add(group, issue["severity"], issue["description"])
    for finding in snapshot["review_findings"]:
        if finding["status"] != "open":
            continue
        group = label_by_field.get(finding.get("field_id") or "", UNASSIGNED_GROUP)
        add(group, finding["severity"], finding["description"])

    out: list[tuple[str, list[str]]] = []
    for group in order:
        bucket = grouped.pop(group, None)
        if not bucket:
            continue
        lines = [
            (f"{count} × {line}" if count > 1 else line)
            for line, count in bucket.items()
        ]
        out.append((group, lines))
    # Any remaining groups (defensive; deterministic by name).
    for group in sorted(grouped):
        bucket = grouped[group]
        lines = [
            (f"{count} × {line}" if count > 1 else line)
            for line, count in bucket.items()
        ]
        out.append((group, lines))
    return out


def slugify(title: str) -> str:
    """ASCII-safe, traversal-safe filename slug (CTRL.FILENAME_NORMALIZATION)."""
    normalized = unicodedata.normalize("NFKD", title or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_only).strip("_")
    return slug[:60] or "Export"


def build_filename(snapshot: dict) -> str:
    meta = snapshot["meta"]
    label = _TYPE_LABEL[meta["export_type"]]
    suffix = "_ENTWURF" if meta["draft_marked"] else ""
    ext = EXPORT_EXTENSIONS[meta["export_type"]]
    return f"{slugify(meta['project_title'])}_{label}{suffix}{ext}"


def review_status_line(snapshot: dict) -> str:
    return DRAFT_HEADER if snapshot["meta"]["draft_marked"] else APPROVED_STATUS
