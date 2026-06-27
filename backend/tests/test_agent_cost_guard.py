"""CostGuard enforcement (Milestone 9A)."""
from __future__ import annotations

import pytest

from app.agents import cost_guard
from app.agents.gateway import ModelResponse, SafeFailure, invoke
from app.agents.providers import FakeProvider
from app.agents.providers.base import ProviderUsage
from app.agents.registry import get_agent_registry
from app.db.session import SessionLocal
from tests.agent_helpers import base_request, fake_resolver, make_run

PROFILE = "A1.project_fact_extraction"


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def test_profile_limits_resolved():
    profile = get_agent_registry().profile(PROFILE)
    assert cost_guard.max_retries(profile) == 1
    assert cost_guard.timeout_seconds(profile) == 120


def test_max_call_count_enforced(db):
    run_id = make_run(db)
    first = invoke(db, base_request(run_id=run_id), provider_resolver=fake_resolver(FakeProvider()))
    assert isinstance(first, ModelResponse)
    # Second call on the same run+profile exceeds max_per_run=1 → blocked safely.
    second = invoke(db, base_request(run_id=run_id), provider_resolver=fake_resolver(FakeProvider()))
    assert isinstance(second, SafeFailure)
    assert second.status == "blocked" and second.error_code == "cost_guard_blocked"


def test_fake_provider_cost_is_zero(db):
    run_id = make_run(db)
    rec = cost_guard.record_usage(
        db, run_id=run_id, workspace_id="ws-demo", provider="fake", model_id="x",
        usage=ProviderUsage(input_tokens=5, output_tokens=7),
    )
    assert rec.cost_chf == 0.0  # no pricing config → placeholder only
    assert rec.input_tokens == 5 and rec.output_tokens == 7


def test_output_token_cap(db):
    from app.agents.registry import (
        AgentProfileDef,
        DataPolicyReq,
    )

    dp = DataPolicyReq(("public",), ("confidential",), ("cloud_assisted",), "blocked", ())
    profile = AgentProfileDef(
        profile_id="x", agent_id="A1", name="x", status="x", advisory=True,
        allowed_tools=(), input_schema="In", output_schema="Out", controls=(),
        primary_model="m", fallback_model=None, optional_candidate=None, data_policy=dp,
        invocation_limits={"max_output_tokens": 10}, failure_policy={},
    )
    assert cost_guard.output_within_limit(profile, ProviderUsage(0, 5)) is True
    assert cost_guard.output_within_limit(profile, ProviderUsage(0, 50)) is False
