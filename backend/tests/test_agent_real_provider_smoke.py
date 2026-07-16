"""Optional strict A1 real-provider smoke using only synthetic public data."""
from __future__ import annotations

import os

import pytest

from app.agents.gateway import ModelResponse, default_provider_resolver, invoke
from app.agents.registry import get_agent_registry
from app.config.settings import get_settings
from app.db.models import RunPolicySnapshot
from app.db.session import SessionLocal
from app.evaluation.preflight import persist_route_preflight, preflight_route
from app.evaluation.pricing import resolve_cost
from tests.agent_helpers import base_request, make_run

pytestmark = pytest.mark.skipif(
    bool(os.environ.get("CI")) or os.environ.get("RUN_REAL_PROVIDER_SMOKE") != "true",
    reason="manual only: RUN_REAL_PROVIDER_SMOKE=true outside CI",
)


def test_real_provider_smoke():
    settings = get_settings()
    if settings.ai_eval_mode != "real" or settings.agent_fake_provider:
        pytest.skip("requires AI_EVAL_MODE=real and AGENT_FAKE_PROVIDER=false")
    registry = get_agent_registry()
    role = registry.role_routes["A1_FACT_EVIDENCE_ANALYST"]
    route_key = next((key for key in (role.primary, role.fallback) if key and (
        registry.route(key).requested_model_id(settings)
        and ((registry.route(key).provider == "openai_direct" and settings.openai_api_key)
             or (registry.route(key).provider == "anthropic_direct" and settings.anthropic_api_key))
    )), None)
    if route_key is None:
        pytest.skip("no configured A1 provider route")
    route = registry.route(route_key)
    requested = route.requested_model_id(settings)
    if resolve_cost(
        provider=route.provider, model_id=requested, input_tokens=0, output_tokens=0
    ).cost_status != "priced":
        pytest.skip("no versioned CHF price evidence for selected route")

    db = SessionLocal()
    try:
        run_id = make_run(db, sensitivity="public", processing_mode="cloud_assisted")
        db.add(RunPolicySnapshot(
            run_id=run_id, processing_mode="cloud_assisted", max_cost_chf=5,
            max_llm_calls=2, max_web_calls=0, max_retries=1, max_redrafts=0,
            timeout_seconds=300, allowed_routes=[], policy_version="1.1.0",
        ))
        preflight = preflight_route(route_key, settings=settings, execute_live=True)
        assert preflight.status == "pass"
        persist_route_preflight(db, preflight, settings=settings)
        db.flush()
        result = invoke(
            db, base_request(run_id=run_id, run_confirmation=True),
            provider_resolver=default_provider_resolver,
        )
        # A SafeFailure is a failed smoke, never a successful live proof.
        assert isinstance(result, ModelResponse)
        assert result.actual_model_id and result.skill_version
    finally:
        db.rollback()
        db.close()
