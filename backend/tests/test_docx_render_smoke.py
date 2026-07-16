"""Explicit Word -> PDF -> PNG smoke test for the working-copy DOCX.

This test intentionally does not skip when Microsoft Word is unavailable: a
clean visual render is an acceptance criterion, not an optional enhancement.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import fitz

from tests.export_helpers import download, make_export
from tests.review_helpers import setup_completed_run


def _word_executable() -> Path:
    roots = [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
    candidates = [Path(root) / "Microsoft Office" / "root" / "Office16" / "WINWORD.EXE" for root in roots]
    found = next((item for item in candidates if item.exists()), None)
    assert found is not None, "Microsoft Word is required for the explicit DOCX render smoke test."
    return found


def _word_to_pdf(docx_path: Path, pdf_path: Path) -> None:
    _word_executable()
    helper = Path(__file__).with_name("word_render_helper.py")
    result = subprocess.run(
        [sys.executable, str(helper), str(docx_path.resolve()), str(pdf_path.resolve())],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert result.returncode == 0, result.stderr or "Word PDF conversion failed."


def _assert_words_are_visible_without_relevant_overlap(page: fitz.Page) -> None:
    rect = page.rect
    words = page.get_text("words")
    for x0, y0, x1, y1, *_ in words:
        assert x0 >= rect.x0 - 1 and y0 >= rect.y0 - 1
        assert x1 <= rect.x1 + 1 and y1 <= rect.y1 + 1
    for index, first in enumerate(words):
        ax0, ay0, ax1, ay1, _aword, ablock, aline, *_ = first
        for second in words[index + 1 :]:
            bx0, by0, bx1, by1, _bword, bblock, bline, *_ = second
            # A Word text block can wrap over adjacent PDF lines whose glyph
            # boxes touch. That is normal line layout, not overlaid content.
            if ablock == bblock:
                continue
            overlap = max(0, min(ax1, bx1) - max(ax0, bx0)) * max(0, min(ay1, by1) - max(ay0, by0))
            # Word's glyph boxes may touch across adjacent table lines by a
            # fraction of a point. Larger intersections are visual overlap.
            assert overlap <= 4.0, (
                f"Overlapping word boxes on page {page.number + 1}: "
                f"{_aword!r} ({ablock}/{aline}) vs {_bword!r} ({bblock}/{bline})"
            )


def test_docx_render_smoke_all_pages(client):
    csrf, _project_id, run_id = setup_completed_run(client, title="Render Smoke Project")
    artifact = make_export(client, csrf, run_id, "docx")
    backend_root = Path(__file__).resolve().parents[1]
    workdir = Path(tempfile.mkdtemp(prefix="render-smoke-", dir=backend_root))
    try:
        docx_path = workdir / "working-copy.docx"
        pdf_path = workdir / "working-copy.pdf"
        docx_path.write_bytes(download(client, artifact["export_id"]).content)
        _word_to_pdf(docx_path, pdf_path)
        assert pdf_path.exists() and pdf_path.stat().st_size > 0
        pdf = fitz.open(pdf_path)
        try:
            assert pdf.page_count >= 2
            text = "\n".join(page.get_text() for page in pdf)
            for marker in ("Partner", "Budgetübersicht", "Narrative Innolink-Felder", "Quellenverzeichnis"):
                assert marker in text
            for index, page in enumerate(pdf):
                png_path = workdir / f"page-{index + 1}.png"
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                pixmap.save(png_path)
                assert png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
                _assert_words_are_visible_without_relevant_overlap(page)
        finally:
            pdf.close()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
