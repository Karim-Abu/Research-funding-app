"""Deterministic export layer (Milestone 8).

From a completed run's frozen artifacts, generate DOCX / Markdown / technical
evidence exports. Truthfully marks review-approved vs draft (ENTWURF). No LLM /
provider / network / cloud / portal submission.
"""
from __future__ import annotations

TECHNICAL_EVIDENCE_SCHEMA = "technical-evidence-1"
EXPORT_SNAPSHOT_SCHEMA = "export-snapshot-1"

# Public file extension + MIME per export type (download is always octet-stream;
# the type lives in the filename extension).
EXPORT_EXTENSIONS = {
    "docx": ".docx",
    "markdown": ".md",
    "technical_evidence": ".json",
}
EXPORT_MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "markdown": "text/markdown; charset=utf-8",
    "technical_evidence": "application/json; charset=utf-8",
}
