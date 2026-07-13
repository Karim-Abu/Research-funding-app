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


def make_text_pages_pdf(pages: list[list[str]]) -> bytes:
    """Build a deterministic multi-page text PDF without external fixtures."""

    def esc(text: str) -> bytes:
        raw = text.encode("cp1252", errors="replace")
        return raw.replace(b"\\", rb"\\").replace(b"(", rb"\(").replace(b")", rb"\)")

    objects: dict[int, bytes] = {
        3: (
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding >>"
        )
    }
    page_ids: list[int] = []
    next_id = 4
    for lines in pages:
        body = b"\n".join(b"(" + esc(line) + b") Tj T*" for line in lines)
        content = b"BT\n/F1 10 Tf\n72 760 Td\n12 TL\n" + body + b"\nET"
        content_id, page_id = next_id, next_id + 1
        next_id += 2
        objects[content_id] = (
            b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n"
            + content + b"\nendstream"
        )
        objects[page_id] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents "
            + f"{content_id} 0 R >>".encode()
        )
        page_ids.append(page_id)

    kids = b" ".join(f"{page_id} 0 R".encode() for page_id in page_ids)
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = (
        b"<< /Type /Pages /Kids [" + kids + b"] /Count "
        + str(len(page_ids)).encode() + b" >>"
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for object_id in sorted(objects):
        offsets[object_id] = len(out)
        out += f"{object_id} 0 obj\n".encode() + objects[object_id] + b"\nendobj\n"
    xref_pos = len(out)
    size = max(objects) + 1
    out += f"xref\n0 {size}\n".encode() + b"0000000000 65535 f \n"
    for object_id in range(1, size):
        out += f"{offsets[object_id]:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size " + str(size).encode() + b" /Root 1 0 R >>\n"
        b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF"
    )
    return bytes(out)


def make_image_only_pdf() -> bytes:
    # A graphics-only content stream (filled rectangle) with no text operators.
    return _build_pdf(b"0 0 1 rg 72 72 200 200 re f")


def make_encrypted_pdf(password: str = "secret") -> bytes:
    """Passwortgeschütztes PDF: der Parser kann es ohne Passwort nicht öffnen
    (→ needs_manual_input mit Warnung ``encrypted_pdf``)."""
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(make_text_pdf("Encrypted content."))))
    writer.encrypt(user_password=password)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


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
