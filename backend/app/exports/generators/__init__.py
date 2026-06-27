"""Deterministic export generators (Milestone 8): docx, markdown, technical_evidence.

Each generator is a pure function of the frozen snapshot dict (+ its hash) and
produces bytes. No DB access, no system clock, no network/LLM.
"""
from __future__ import annotations

from app.exports.generators.docx import generate_docx
from app.exports.generators.markdown import generate_markdown
from app.exports.generators.technical_evidence import generate_technical_evidence

GENERATORS = {
    "docx": generate_docx,
    "markdown": generate_markdown,
    "technical_evidence": generate_technical_evidence,
}

__all__ = [
    "GENERATORS",
    "generate_docx",
    "generate_markdown",
    "generate_technical_evidence",
]
