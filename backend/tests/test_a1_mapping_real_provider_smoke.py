"""Optional, env-gated A1 evidence-mapping real-provider smoke (Milestone 9C).

Never runs in CI. Public/synthetic source only; schema-valid output or safe failure.
Skips cleanly without ``RUN_REAL_PROVIDER_SMOKE=true`` or a key.
"""
from __future__ import annotations

import os

import pytest

from app.agents import evidence_mapping
from app.config.settings import get_settings
from app.db.session import SessionLocal
from tests.a1_mapping_helpers import build_run

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_REAL_PROVIDER_SMOKE") != "true",
    reason="set RUN_REAL_PROVIDER_SMOKE=true to run the optional real-provider smoke",
)


def test_a1_mapping_real_provider_smoke():
    settings = get_settings()
    if not (settings.anthropic_api_key or settings.openai_api_key):
        pytest.skip("no real provider API key configured")
    db = SessionLocal()
    try:
        run, _frags, _ = build_run(
            db, fragments=["The consortium has a Swiss implementation partner."],
            processing_mode="cloud_assisted", sensitivity="public", origin="synthetic",
        )
        db.commit()
        outcome = evidence_mapping.run_a1_evidence_mapping(db, run)
        assert outcome.status in ("succeeded", "failed", "skipped", "blocked", "reused")
    finally:
        db.rollback()
        db.close()
