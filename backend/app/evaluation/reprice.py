"""One-off, idempotent re-pricing of stored usage rows.

Provider costs are resolved once at write time and frozen onto each
``UsageRecord`` (see ``app.agents.cost_guard.record_usage``); the costs API only
reads those frozen values, and it only counts a row as priced when a USD amount
is present. Two kinds of stored rows show as unpriced in the USD-first cost UI:

* ``unknown_price`` rows written before their model's catalogue entry became
  effective; and
* legacy ``priced`` rows carrying only a CHF amount (``cost_usd`` is NULL) from
  an earlier CHF-based pricing scheme.

This module re-resolves both kinds against the current USD catalogue using their
real tokens and their own event date, and rewrites the frozen cost fields only
when a real USD price now applies. It never downgrades a row: if the current
catalogue cannot price a row, the row is left exactly as it was.

Run from backend/: ``python -m app.evaluation.reprice``

Safe to run repeatedly.
"""
from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.db.models import UsageRecord
from app.db.session import SessionLocal
from app.evaluation.pricing import COST_STATUS_PRICED, COST_STATUS_UNKNOWN, resolve_cost

logger = logging.getLogger(__name__)


def reprice_incomplete_usage(db: Session) -> int:
    """Re-resolve stored rows that read as unpriced in the USD UI.

    Covers ``unknown_price`` rows and legacy ``priced`` rows without a USD
    amount. Rewrites a row only when the current catalogue yields a USD price;
    never downgrades. Returns the number of rows rewritten.
    """
    rows = list(db.scalars(
        select(UsageRecord).where(
            UsageRecord.model.is_not(None),
            or_(
                UsageRecord.cost_status == COST_STATUS_UNKNOWN,
                and_(UsageRecord.cost_status == COST_STATUS_PRICED, UsageRecord.cost_usd.is_(None)),
            ),
        )
    ))
    changed = 0
    for record in rows:
        resolution = resolve_cost(
            provider=record.provider,
            model_id=record.model,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            cached_input_tokens=record.cached_input_tokens,
            cache_write_input_tokens=record.cache_write_input_tokens,
            occurred_at=record.created_at,
        )
        if resolution.cost_status != COST_STATUS_PRICED or resolution.cost_usd is None:
            continue
        record.cost_usd = resolution.cost_usd
        record.fx_chf_per_usd = resolution.fx_chf_per_usd
        record.cost_chf = resolution.cost_chf
        record.cost_status = resolution.cost_status
        record.price_version = resolution.price_version
        changed += 1
    if changed:
        db.commit()
    return changed


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    configure_logging(get_settings().log_level)
    db = SessionLocal()
    try:
        changed = reprice_incomplete_usage(db)
    except Exception as exc:  # noqa: BLE001
        logger.error("reprice failed: %s", exc)
        return 1
    finally:
        db.close()
    logger.info("repriced %s usage record(s)", changed)
    print(f"Repriced {changed} usage record(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
