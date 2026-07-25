"""Idempotent re-pricing of frozen ``unknown_price`` usage rows."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.db.models import UsageRecord
from app.db.session import SessionLocal
from app.evaluation.reprice import reprice_incomplete_usage
from tests.agent_helpers import WS


def _unknown_row(db, **overrides) -> str:
    rid = "usage-" + uuid.uuid4().hex[:10]
    fields = dict(
        usage_record_id=rid,
        run_id=None,
        workspace_id=WS,
        provider="openai_direct",
        model="gpt-5.6-luna",
        input_tokens=20_000,
        output_tokens=3_000,
        cached_input_tokens=0,
        cache_write_input_tokens=0,
        cost_usd=None,
        fx_chf_per_usd=None,
        cost_chf=0.0,
        cost_status="unknown_price",
        price_version=None,
        created_at=datetime(2026, 7, 23, 23, 53, tzinfo=timezone.utc),
    )
    fields.update(overrides)
    db.add(UsageRecord(**fields))
    db.flush()
    return rid


def test_reprice_prices_a_pilot_row_with_a_known_model():
    db = SessionLocal()
    try:
        rid = _unknown_row(db)
        db.commit()
        reprice_incomplete_usage(db)
        row = db.get(UsageRecord, rid)
        assert row.cost_status == "priced"
        # (20000 * $1 + 3000 * $6) / 1M = 0.038
        assert row.cost_usd == 0.038
        assert row.cost_chf > 0
        assert row.price_version == "2026-07-24.gpt56-luna"
    finally:
        db.close()


def test_reprice_is_idempotent():
    db = SessionLocal()
    try:
        rid = _unknown_row(db)
        db.commit()
        reprice_incomplete_usage(db)
        first = db.get(UsageRecord, rid).cost_usd
        # A second pass touches no already-priced row.
        reprice_incomplete_usage(db)
        assert db.get(UsageRecord, rid).cost_status == "priced"
        assert db.get(UsageRecord, rid).cost_usd == first
    finally:
        db.close()


def test_reprice_fills_usd_on_a_legacy_chf_only_priced_row():
    # Legacy rows priced under the old CHF scheme carry cost_status='priced' but
    # no USD amount, so the USD-first cost API counts them as unpriced. Reprice
    # must populate the USD amount from the current catalogue.
    db = SessionLocal()
    try:
        rid = _unknown_row(
            db, cost_status="priced", cost_usd=None, cost_chf=0.0237,
            price_version="openai_standard__snb_fx_2026-07-16",
        )
        db.commit()
        reprice_incomplete_usage(db)
        row = db.get(UsageRecord, rid)
        assert row.cost_status == "priced"
        assert row.cost_usd == 0.038
        assert row.price_version == "2026-07-24.gpt56-luna"
    finally:
        db.close()


def test_reprice_leaves_cache_write_rows_unknown_by_design():
    db = SessionLocal()
    try:
        rid = _unknown_row(db, cache_write_input_tokens=100)
        db.commit()
        reprice_incomplete_usage(db)
        row = db.get(UsageRecord, rid)
        assert row.cost_status == "unknown_price"
        assert row.cost_usd is None
    finally:
        db.close()


def test_reprice_leaves_unknown_model_rows_unknown():
    db = SessionLocal()
    try:
        rid = _unknown_row(db, model="provider-alias-not-in-catalogue")
        db.commit()
        reprice_incomplete_usage(db)
        assert db.get(UsageRecord, rid).cost_status == "unknown_price"
    finally:
        db.close()
