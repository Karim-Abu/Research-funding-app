"""Optional, env-gated A1 real-provider smoke (Milestone 9B).

Never runs in CI. Public/synthetic source only; records provider/model/latency/
usage/schema-validity via the normal pipeline. Skips cleanly without the env or key.
"""
from __future__ import annotations

import os

import pytest

from app.agents import fact_extraction
from app.config.settings import get_settings
from app.db.session import SessionLocal
from tests.a1_helpers import build_run

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_REAL_PROVIDER_SMOKE") != "true",
    reason="set RUN_REAL_PROVIDER_SMOKE=true to run the optional real-provider smoke",
)


def test_a1_real_provider_smoke():
    settings = get_settings()
    if not (settings.anthropic_api_key or settings.openai_api_key):
        pytest.skip("no real provider API key configured")
    db = SessionLocal()
    try:
        run, _frags, _ = build_run(
            db, fragments=["Synthetic public project summary for smoke testing."],
            processing_mode="cloud_assisted", sensitivity="public", origin="synthetic",
        )
        db.commit()
        # Uses the default (real) resolver. A real model may legitimately return a
        # safe failure without a tuned prompt — the point is no crash and no leak.
        outcome = fact_extraction.run_a1_fact_extraction(db, run)
        assert outcome.status in ("succeeded", "failed", "skipped", "blocked")
    finally:
        db.rollback()
        db.close()
