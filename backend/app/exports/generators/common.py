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
