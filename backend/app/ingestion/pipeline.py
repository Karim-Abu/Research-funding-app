"""Source processing pipeline: parse → normalize → fragment → persist.

Runs in a FastAPI BackgroundTask (acceptable for this local single-instance
beta) with its own DB session and a bounded, configurable concurrency limit.
Failures always land on a terminal status (`failed`/`needs_manual_input`) — a
source is never silently left `processed` after a parser error.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.config.settings import get_settings
from app.db.models import SourceDocument, SourceFragment, SourceVersion
from app.db.session import SessionLocal
from app.ingestion import CHUNKER_VERSION, NORMALIZER_VERSION, PARSER_VERSION
from app.ingestion.normalize import normalize_text
from app.ingestion.parsers import ParsedBlock, ParserError, parse
from app.repositories import controls as controls_repo
from app.storage import get_storage

logger = logging.getLogger("app.ingestion")

_FRAGMENT_SEPARATOR = "\n\n"
_parse_semaphore = threading.BoundedSemaphore(get_settings().max_parsing_concurrency)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_fragments(
    blocks: list[ParsedBlock], version_id: str
) -> tuple[str, str, list[SourceFragment]]:
    norm_parts: list[str] = []
    original_parts: list[str] = []
    fragments: list[SourceFragment] = []
    cursor = 0
    for block in blocks:
        normalized = normalize_text(block.text)
        if not normalized:
            continue
        if norm_parts:
            cursor += len(_FRAGMENT_SEPARATOR)
        start = cursor
        end = start + len(normalized)
        fragments.append(
            SourceFragment(
                fragment_id=uuid.uuid4().hex,
                source_version_id=version_id,
                ordinal=len(fragments),
                original_text=block.text,
                normalized_text=normalized,
                page=block.page,
                section=block.section,
                start_offset=start,
                end_offset=end,
                content_hash=_sha256_text(normalized),
            )
        )
        norm_parts.append(normalized)
        original_parts.append(block.text)
        cursor = end
    return (
        _FRAGMENT_SEPARATOR.join(original_parts),
        _FRAGMENT_SEPARATOR.join(norm_parts),
        fragments,
    )


def _control(db, doc, version, status: str, detail: str) -> None:
    controls_repo.record(
        db,
        workspace_id=doc.workspace_id if doc else "",
        project_id=doc.project_id if doc else None,
        source_id=doc.source_id if doc else None,
        source_version_id=version.source_version_id,
        control_id="source.processing",
        status=status,
        detail=detail,
    )


def _finish_failed(db, version, doc, code: str, message: str) -> None:
    version.processing_status = "failed"
    version.last_error_code = code
    version.processing_finished_at = _now()
    if doc:
        doc.status = "failed"
        doc.error_message = message


def process_source_version(source_version_id: str) -> None:
    with _parse_semaphore:
        db = SessionLocal()
        try:
            version = db.get(SourceVersion, source_version_id)
            if version is None:
                return
            doc = db.get(SourceDocument, version.source_document_id)
            source_type = doc.type if doc else "txt"

            version.processing_status = "processing"
            version.processing_started_at = _now()
            version.processing_attempt += 1
            if doc:
                doc.status = "processing"
            db.commit()

            data = get_storage().open(version.storage_ref)
            try:
                result = parse(source_type, data)
            except ParserError:
                _finish_failed(
                    db, version, doc, "SOURCE_PARSE_FAILED",
                    "Die Datei konnte nicht verarbeitet werden. Bitte prüfen Sie "
                    "das Format oder laden Sie sie erneut hoch.",
                )
                _control(db, doc, version, "failed", "parse_failed")
                db.commit()
                return

            version.parser_version = PARSER_VERSION
            version.parsing_warnings = result.warnings

            if result.needs_manual_input:
                version.processing_status = "needs_manual_input"
                version.processing_finished_at = _now()
                if doc:
                    doc.status = "needs_manual_input"
                    doc.error_message = None
                _control(db, doc, version, "warning", "needs_manual_input")
                db.commit()
                return

            original_full, normalized_full, fragments = _build_fragments(
                result.blocks, version.source_version_id
            )
            for fragment in fragments:
                db.add(fragment)
            version.normalized_text = normalized_full
            version.normalized_content_hash = _sha256_text(normalized_full)
            version.normalizer_version = NORMALIZER_VERSION
            version.chunker_version = CHUNKER_VERSION
            version.processing_status = "processed"
            version.processing_finished_at = _now()
            if doc:
                doc.status = "processed"
                doc.error_message = None
            _control(db, doc, version, "passed", f"fragments={len(fragments)}")
            db.commit()
        except Exception:  # noqa: BLE001 — never leak internals; mark failed safely
            logger.exception("source processing crashed")
            db.rollback()
            try:
                version = db.get(SourceVersion, source_version_id)
                doc = (
                    db.get(SourceDocument, version.source_document_id)
                    if version
                    else None
                )
                if version:
                    _finish_failed(
                        db, version, doc, "SOURCE_PROCESSING_ERROR",
                        "Die Verarbeitung ist fehlgeschlagen. Bitte versuchen Sie "
                        "es erneut.",
                    )
                    db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
        finally:
            db.close()


def recover_interrupted() -> int:
    """On startup mark rows left mid-processing as failed (single-instance beta)."""
    db = SessionLocal()
    count = 0
    try:
        stale = db.scalars(
            select(SourceVersion).where(
                SourceVersion.processing_status.in_(("uploaded", "processing"))
            )
        ).all()
        for version in stale:
            doc = db.get(SourceDocument, version.source_document_id)
            _finish_failed(
                db, version, doc, "SOURCE_PROCESSING_INTERRUPTED",
                "Die Verarbeitung wurde unterbrochen. Bitte laden Sie die Quelle "
                "erneut hoch.",
            )
            count += 1
        if count:
            db.commit()
        return count
    finally:
        db.close()
