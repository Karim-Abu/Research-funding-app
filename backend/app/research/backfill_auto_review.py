"""One-off, idempotent backfill for research results imported before the manual
"Stützt/Teilweise/Stützt nicht" review step was removed (2026-07-26).

Since that change, ``import_service.import_result`` auto-marks a newly imported,
non-quarantined result as reviewed/supporting. Rows imported *before* the change
were left at their old ``unreviewed``/``not_checked`` defaults, and with the
review buttons gone there is no UI path left to move them forward — they get
permanently stuck out of the market-comparison source scope
(``app.market.source_scope.imported_public_sources``).

This backfill applies the same rule retroactively: any already-imported result
whose current source version is not quarantined becomes reviewed/supporting.
Quarantined content is left untouched — it still requires the explicit human
safety release ("Ausdrücklich geprüft und unterstützend").

Run from backend/: ``python -m app.research.backfill_auto_review``

Safe to run repeatedly.
"""
from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.db.models import ResearchResult, SourceDocument
from app.db.session import SessionLocal
from app.research.import_service import _auto_review_if_safe

logger = logging.getLogger(__name__)


def backfill_stuck_imported_results(db: Session) -> int:
    """Auto-review already-imported results left over from the manual-review
    era. Returns the number of rows changed."""
    rows = list(db.scalars(
        select(ResearchResult).where(
            ResearchResult.status == "imported",
            ResearchResult.source_document_id.is_not(None),
            ResearchResult.content_review_status != "reviewed",
        )
    ))
    changed = 0
    for result in rows:
        document = db.get(SourceDocument, result.source_document_id)
        if document is None:
            continue
        before = result.content_review_status
        _auto_review_if_safe(db, result=result, document=document)
        if result.content_review_status != before:
            changed += 1
    if changed:
        db.commit()
    return changed


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    configure_logging(get_settings().log_level)
    db = SessionLocal()
    try:
        changed = backfill_stuck_imported_results(db)
    except Exception as exc:  # noqa: BLE001
        logger.error("backfill failed: %s", exc)
        return 1
    finally:
        db.close()
    logger.info("auto-reviewed %s stuck research result(s)", changed)
    print(f"Auto-reviewed {changed} stuck research result(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
