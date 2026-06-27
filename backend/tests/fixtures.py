"""Deterministic in-memory document fixtures for source-ingestion tests."""
from __future__ import annotations

import io


def _build_pdf(content_stream: bytes) -> bytes:
    """Build a minimal single-page PDF with a correct xref table."""
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
        b"/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length " + str(len(content_stream)).encode() + b">>\nstream\n"
        + content_stream + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    count = len(objects) + 1
    out += b"xref\n0 " + str(count).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += b"trailer\n<</Size " + str(count).encode() + b"/Root 1 0 R>>\n"
    out += b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF"
    return bytes(out)


def make_text_pdf(text: str = "Hello PDF Source") -> bytes:
    stream = b"BT /F1 24 Tf 72 700 Td (" + text.encode("latin-1") + b") Tj ET"
    return _build_pdf(stream)


def make_image_only_pdf() -> bytes:
    # A graphics-only content stream (filled rectangle) with no text operators.
    return _build_pdf(b"0 0 1 rg 72 72 200 200 re f")


def make_docx(
    paragraphs: list[str] | None = None, with_table: bool = False
) -> bytes:
    from docx import Document

    document = Document()
    for paragraph in paragraphs or ["Hello DOCX Source", "Second paragraph."]:
        document.add_paragraph(paragraph)
    if with_table:
        table = document.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Header A"
        table.cell(0, 1).text = "Header B"
        table.cell(1, 0).text = "Value 1"
        table.cell(1, 1).text = "Value 2"
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


TXT_BYTES = b"Hello text source.\nThis is the second line.\n"
CORRUPTED_PDF = b"%PDF-1.4\nthis is not a real pdf body %%EOF"
EXECUTABLE_BYTES = b"MZ\x90\x00\x03" + b"\x00" * 64  # PE/DOS signature
