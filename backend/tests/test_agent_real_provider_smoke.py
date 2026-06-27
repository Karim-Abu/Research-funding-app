"""Optional, env-gated real-provider smoke test (Milestone 9A).

Never runs in CI. Skips cleanly without ``RUN_REAL_PROVIDER_SMOKE=true`` or a key.
Public/synthetic text only; no sensitive prompt/output recorded.
"""
from __future__ import annotations

import os

import pytest

from app.agents.gateway import ModelResponse, SafeFailure, default_provider_resolver, invoke
from app.config.settings import get_settings
from app.db.session import SessionLocal
from tests.agent_helpers import base_request, make_run

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_REAL_PROVIDER_SMOKE") != "true",
    reason="set RUN_REAL_PROVIDER_SMOKE=true to run the optional real-provider smoke",
)


def test_real_provider_smoke():
    settings = get_settings()
    if not (settings.anthropic_api_key or settings.openai_api_key):
        pytest.skip("no real provider API key configured")
    db = SessionLocal()
    try:
        run_id = make_run(db, sensitivity="public", processing_mode="cloud_assisted")
        # Public/synthetic only; the default resolver uses the real adapters.
        result = invoke(
            db, base_request(run_id=run_id), provider_resolver=default_provider_resolver
        )
        # A real model rarely returns the exact A1 schema without a tuned prompt,
        # so a safe failure is an acceptable outcome — the point is no crash and
        # no leak. Record only provider/model/latency metadata.
        assert isinstance(result, (ModelResponse, SafeFailure))
    finally:
        db.rollback()
        db.close()
