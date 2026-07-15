"""ModelGateway behaviour with the fake provider (Milestone 9A)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import gateway
from app.agents.gateway import ModelResponse, SafeFailure, invoke
from app.config.settings import get_settings
from app.agents.providers import FakeProvider
from app.agents.providers.base import ProviderUsage
from app.agents.registry import (
    AgentDef,
    AgentProfileDef,
    AgentRegistry,
    DataPolicyReq,
    ModelRoute,
)
from app.agents.schemas import ProjectFactExtractionResult
from app.db.models import AgentInvocation, AuditEvent, ControlResult, UsageRecord
from app.db.session import SessionLocal
from tests.agent_helpers import (
    base_request,
    fake_resolver,
    make_run,
    per_route_resolver,
)

PROFILE = "A1.project_fact_extraction"


class _RealEvalStub(FakeProvider):
    """Network-free adapter double classified exactly like the direct OpenAI route."""

    name = "openai_direct"


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _no_fallback_registry() -> AgentRegistry:
    route = ModelRoute("m1", "anthropic_direct", "x1", "x1", "active")
    dp = DataPolicyReq(("public",), ("confidential",), ("cloud_assisted",), "blocked", ())
    prof = AgentProfileDef(
        profile_id=PROFILE, agent_id="A1", name="P", status="beta_active", advisory=True,
        allowed_tools=(), input_schema="ProjectFactExtractionInput@v1",
        output_schema="ProjectFactExtractionResult@v1", controls=("CTRL.DATA_POLICY",),
        primary_model="m1", fallback_model=None, optional_candidate=None, data_policy=dp,
        invocation_limits={"max_per_run": 1, "max_retries": 1, "timeout_seconds": 60},
        failure_policy={},
    )
    agent = AgentDef("A1", "A1", (PROFILE,), "m1", None, 1, 1, True)
    return AgentRegistry({"m1": route}, {"A1": agent}, {PROFILE: prof})


def test_successful_structured_call(db):
    resp = invoke(db, base_request(), provider_resolver=fake_resolver(FakeProvider()))
    assert isinstance(resp, ModelResponse)
    assert resp.status == "succeeded"
    assert isinstance(resp.output, ProjectFactExtractionResult)
    inv = db.get(AgentInvocation, resp.invocation_id)
    assert inv.status == "succeeded" and inv.input_hash and inv.output_hash
    assert inv.provider == "anthropic_direct" and inv.prompt_version
    assert (inv.role_id, inv.role_version) == (
        "A1_FACT_EVIDENCE_ANALYST", "a1_fact_evidence_analyst_v2"
    )
    assert (inv.skill_id, inv.skill_version, inv.contract_version) == (
        "a1.fact_extraction", "a1_fact_extraction_skill_v2", "2.0.0"
    )
    assert inv.input_artifact_refs == [
        {"kind": "run_input_snapshot", "fragment_ids": ["frag-1"]}
    ]
    assert resp.role_id == inv.role_id and resp.skill_id == inv.skill_id
    assert resp.generation_kind == "fake_demo"
    assert inv.context_meta["model_call_attempted"] is False


def test_fake_provider_never_unlocks_local_only(db):
    adapter = FakeProvider()
    response = invoke(
        db,
        base_request(
            processing_mode="local_only",
            classification={
                "sensitivity": "internal",
                "origin": "real_project",
                "nda_applies": False,
            },
            run_confirmation=True,
        ),
        provider_resolver=fake_resolver(adapter),
    )
    assert isinstance(response, SafeFailure)
    assert response.status == "blocked"
    assert response.safe_detail == "processing_mode_local_only"
    assert adapter.calls == 0


def test_real_eval_adapter_sets_model_metadata_only_after_confirmed_call(db, monkeypatch):
    settings = get_settings().model_copy(update={"ai_eval_mode": "real"})
    monkeypatch.setattr(gateway, "get_settings", lambda: settings)
    adapter = _RealEvalStub()
    response = invoke(
        db,
        base_request(run_confirmation=True),
        provider_resolver=fake_resolver(adapter),
    )
    assert isinstance(response, ModelResponse)
    assert response.generation_kind == "model_generated"
    assert response.actual_adapter_name == "openai_direct"
    assert response.prompt_version
    assert adapter.calls == 1
    invocation = db.get(AgentInvocation, response.invocation_id)
    assert invocation.context_meta["model_call_attempted"] is True
    assert invocation.context_meta["generation_kind"] == "model_generated"


@pytest.mark.parametrize(
    ("origin", "confirmed"),
    [("synthetic", False), ("real_project", True)],
)
def test_real_eval_gate_blocks_before_adapter_call(db, monkeypatch, origin, confirmed):
    settings = get_settings().model_copy(update={"ai_eval_mode": "real"})
    monkeypatch.setattr(gateway, "get_settings", lambda: settings)
    adapter = _RealEvalStub()
    response = invoke(
        db,
        base_request(
            classification={
                "sensitivity": "public",
                "origin": origin,
                "nda_applies": False,
            },
            run_confirmation=confirmed,
        ),
        provider_resolver=fake_resolver(adapter),
    )
    assert isinstance(response, SafeFailure)
    assert response.status == "blocked"
    assert adapter.calls == 0


def test_malformed_output_is_safe_failure(db):
    resp = invoke(db, base_request(), provider_resolver=fake_resolver(FakeProvider(mode="malformed")))
    assert isinstance(resp, SafeFailure)
    assert resp.status == "failed" and resp.error_code == "agent_invocation_failed"
    assert resp.output is None


def test_invalid_evidence_reference_fails(db):
    # A fact citing a fragment not in the allowed run-snapshot set is rejected.
    payload = {
        "facts": [{"fact_id": "f1", "statement": "x", "source_fragment_ids": ["HALLUCINATED"]}],
        "conflicts": [], "missing_information": [],
    }
    resp = invoke(
        db, base_request(allowed_fragment_ids=frozenset({"frag-1"})),
        provider_resolver=fake_resolver(FakeProvider(payload=payload)),
    )
    assert isinstance(resp, SafeFailure) and resp.status == "failed"


def test_fallback_used_when_primary_fails(db):
    fakes = {
        "anthropic_direct": FakeProvider(mode="error"),  # primary
        "openai_direct": FakeProvider(),                 # fallback succeeds
    }
    resp = invoke(db, base_request(), provider_resolver=per_route_resolver(fakes))
    assert isinstance(resp, ModelResponse)
    assert resp.provider == "openai_direct"  # served by the fallback route


def test_fallback_not_allowed_blocks(db):
    resp = invoke(
        db, base_request(), provider_resolver=fake_resolver(FakeProvider(mode="error")),
        registry=_no_fallback_registry(),
    )
    assert isinstance(resp, SafeFailure) and resp.status == "failed"


def test_provider_unavailable(db):
    resp = invoke(db, base_request(), provider_resolver=lambda _route: None)
    assert isinstance(resp, SafeFailure)
    assert resp.safe_detail == "provider_unavailable"


def test_retry_once_only_on_schema_failure(db):
    primary = FakeProvider(mode="malformed")
    fakes = {"anthropic_direct": primary, "openai_direct": FakeProvider(mode="malformed")}
    resp = invoke(db, base_request(), provider_resolver=per_route_resolver(fakes))
    assert isinstance(resp, SafeFailure)
    assert primary.calls == 2  # one attempt + exactly one retry


def test_timeout_is_timed_out(db):
    resp = invoke(db, base_request(), provider_resolver=fake_resolver(FakeProvider(mode="timeout")))
    assert isinstance(resp, SafeFailure) and resp.status == "timed_out"


def test_persists_invocation_controls_usage_and_audit(db):
    run_id = make_run(db, processing_mode="cloud_assisted", sensitivity="public")
    fake = FakeProvider(usage=ProviderUsage(input_tokens=11, output_tokens=22))
    resp = invoke(db, base_request(run_id=run_id), provider_resolver=fake_resolver(fake))
    assert isinstance(resp, ModelResponse)

    inv = db.get(AgentInvocation, resp.invocation_id)
    assert inv.status == "succeeded" and inv.run_id == run_id

    controls = db.scalars(
        select(ControlResult).where(ControlResult.agent_invocation_id == inv.invocation_id)
    ).all()
    control_ids = {c.control_id for c in controls}
    assert {"CTRL.DATA_POLICY", "CTRL.COST_GUARD", "CTRL.OUTPUT_SCHEMA", "CTRL.AUDIT_WRITE"} <= control_ids
    assert all(c.run_id == run_id for c in controls)  # also traceable to the run

    usage = db.get(UsageRecord, inv.usage_record_id)
    assert usage.input_tokens == 11 and usage.output_tokens == 22
    assert usage.cost_chf == 0.0  # placeholder only — no pricing config

    audit = db.scalars(
        select(AuditEvent).where(AuditEvent.target_id == inv.invocation_id)
    ).all()
    assert any(a.action == "agent.invocation_succeeded" for a in audit)
