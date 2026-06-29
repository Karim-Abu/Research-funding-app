"""PDF / DOCX / TXT parsers. Deterministic; no OCR, no network.

Each returns a ParseResult of ordered blocks (with page/section) plus warnings.
`needs_manual_input=True` signals a document with no usable text (e.g. scanned /
image-only PDF, encrypted PDF) — never silently treated as processed.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

from app.ingestion.signatures import looks_binary


@dataclass
class ParsedBlock:
    text: str
    page: int | None = None
    section: str | None = None


@dataclass
class ParseResult:
    blocks: list[ParsedBlock]
    warnings: list[str] = field(default_factory=list)
    needs_manual_input: bool = False


class ParserError(Exception):
    """Corrupted/unreadable input → source becomes `failed` (never `processed`)."""


def parse_txt(data: bytes) -> ParseResult:
    warnings: list[str] = []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        # No unconditional Latin-1 fallback: reject implausibly-binary content.
        if looks_binary(data):
            raise ParserError("text source is not valid UTF-8 text")
        text = data.decode("cp1252", errors="replace")
        warnings.append("decoded_with_fallback_encoding:cp1252")
    if looks_binary(data):
        raise ParserError("text source contains binary content")
    return ParseResult(
        blocks=[ParsedBlock(text=text, section="body")], warnings=warnings
    )


def parse_pdf(data: bytes) -> ParseResult:
    from pypdf import PdfReader

    warnings: list[str] = []
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 — corrupted PDF
        raise ParserError("unreadable PDF") from exc

    if reader.is_encrypted:
        try:
            opened = reader.decrypt("")
        except Exception:  # noqa: BLE001
            opened = 0
        if not opened:
            return ParseResult(
                blocks=[], warnings=["encrypted_pdf"], needs_manual_input=True
            )

    blocks: list[ParsedBlock] = []
    total_chars = 0
    try:
        pages = list(reader.pages)
    except Exception as exc:  # noqa: BLE001
        raise ParserError("unreadable PDF pages") from exc

    for index, page in enumerate(pages):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            warnings.append(f"page_extract_failed:{index + 1}")
            text = ""
        text = text.strip()
        if text:
            blocks.append(ParsedBlock(text=text, page=index + 1, section="body"))
            total_chars += len(text)

    if total_chars == 0:
        # Scanned / image-only PDF — requires manual input, not OCR.
        warnings.append("no_extractable_text")
        return ParseResult(blocks=[], warnings=warnings, needs_manual_input=True)
    return ParseResult(blocks=blocks, warnings=warnings)


def parse_docx(data: bytes) -> ParseResult:
    from docx import Document

    warnings: list[str] = []
    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise ParserError("unreadable DOCX") from exc

    blocks: list[ParsedBlock] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            blocks.append(ParsedBlock(text=text, section="body"))

    for table in document.tables:
        rows = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            line = " | ".join(cells).strip(" |")
            if line:
                rows.append(line)
        table_text = "\n".join(rows)
        if table_text.strip():
            blocks.append(ParsedBlock(text=table_text, section="table"))

    # Unsupported structures are surfaced as warnings, never silently dropped.
    try:
        if document.inline_shapes and len(document.inline_shapes) > 0:
            warnings.append("inline_images_not_extracted")
    except Exception:  # noqa: BLE001
        pass

    if not blocks:
        warnings.append("no_extractable_text")
        return ParseResult(blocks=[], warnings=warnings, needs_manual_input=True)
    return ParseResult(blocks=blocks, warnings=warnings)


def parse(source_type: str, data: bytes) -> ParseResult:
    if source_type == "pdf":
        return parse_pdf(data)
    if source_type == "docx":
        return parse_docx(data)
    # Milestone 9I-A: imported public web sources store provider-extracted page text
    # (UTF-8); they are parsed as text like any other textual source.
    if source_type in ("txt", "url"):
        return parse_txt(data)
    raise ParserError(f"unsupported source type: {source_type}")
