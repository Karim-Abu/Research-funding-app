"""ModelGateway behaviour with the fake provider (Milestone 9A)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import gateway
from app.agents.gateway import ModelResponse, SafeFailure, invoke
from app.config.settings import get_settings
from app.agents.providers import FakeProvider
from app.agents.providers.base import ProviderError, ProviderUsage
from app.agents.registry import (
    AgentDef,
    AgentProfileDef,
    AgentRegistry,
    DataPolicyReq,
    ModelRoute,
)
from app.agents.schemas import ProjectFactExtractionResult
from app.db.models import (
    AgentInvocation, AgentInvocationAttempt, AuditEvent, ControlResult, UsageRecord,
)
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
    settings = get_settings().model_copy(update={
        "ai_eval_mode": "real",
        "agent_model_gpt_56_luna_id": "hermetic-openai-model",
    })
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
    assert invocation.requested_model_id == "hermetic-openai-model"
    attempts = db.scalars(select(AgentInvocationAttempt).where(
        AgentInvocationAttempt.invocation_id == invocation.invocation_id
    )).all()
    assert len(attempts) == 1
    assert attempts[0].requested_model_id == "hermetic-openai-model"
    assert attempts[0].actual_model_id == "fake"


@pytest.mark.parametrize(
    ("origin", "confirmed"),
    [("synthetic", False), ("real_project", True)],
)
def test_real_eval_gate_blocks_before_adapter_call(db, monkeypatch, origin, confirmed):
    settings = get_settings().model_copy(update={
        "ai_eval_mode": "real",
        "agent_model_gpt_56_luna_id": "hermetic-openai-model",
    })
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
    attempts = db.scalars(select(AgentInvocationAttempt).where(
        AgentInvocationAttempt.invocation_id == resp.invocation_id
    ).order_by(AgentInvocationAttempt.attempt_index)).all()
    assert [attempt.status for attempt in attempts] == ["failed", "succeeded"]
    assert [attempt.provider for attempt in attempts] == [
        "anthropic_direct", "openai_direct",
    ]


def test_refusal_stops_without_fallback(db):
    class Refusing(FakeProvider):
        def generate(self, request):
            self.calls += 1
            raise ProviderError("refusal", code="refusal")

    adapter = Refusing()
    response = invoke(db, base_request(), provider_resolver=fake_resolver(adapter))
    assert isinstance(response, SafeFailure)
    assert response.safe_detail == "refusal"
    assert adapter.calls == 1


def test_fallback_not_allowed_blocks(db):
    resp = invoke(
        db, base_request(), provider_resolver=fake_resolver(FakeProvider(mode="error")),
        registry=_no_fallback_registry(),
    )
    assert isinstance(resp, SafeFailure) and resp.status == "failed"


# --- route_preference (Demo-Slice 2026-07-17): kein stiller Fallback ---------


def test_primary_only_never_falls_back_silently(db):
    fakes = {
        "anthropic_direct": FakeProvider(mode="error"),  # primary fails
        "openai_direct": FakeProvider(),                 # fallback would succeed
    }
    resp = invoke(
        db, base_request(route_preference="primary_only"),
        provider_resolver=per_route_resolver(fakes),
    )
    assert isinstance(resp, SafeFailure) and resp.status == "failed"
    assert fakes["openai_direct"].calls == 0
    attempts = db.scalars(select(AgentInvocationAttempt).where(
        AgentInvocationAttempt.invocation_id == resp.invocation_id
    )).all()
    assert {a.provider for a in attempts} == {"anthropic_direct"}


def test_fallback_only_serves_and_records_the_alternative_route(db):
    fakes = {
        "anthropic_direct": FakeProvider(),  # primary must stay untouched
        "openai_direct": FakeProvider(),     # explicit alternative
    }
    resp = invoke(
        db, base_request(route_preference="fallback_only"),
        provider_resolver=per_route_resolver(fakes),
    )
    assert isinstance(resp, ModelResponse)
    assert resp.provider == "openai_direct"
    assert fakes["anthropic_direct"].calls == 0
    inv = db.get(AgentInvocation, resp.invocation_id)
    # Wahrheit der Metadaten: die Alternativroute ist die angefragte Route.
    assert inv.provider == "openai_direct"


def test_fallback_only_without_alternative_route_fails_honestly(db):
    adapter = FakeProvider()
    resp = invoke(
        db, base_request(route_preference="fallback_only"),
        provider_resolver=fake_resolver(adapter),
        registry=_no_fallback_registry(),
    )
    assert isinstance(resp, SafeFailure) and resp.status == "failed"
    assert resp.safe_detail == "no_alternative_route"
    assert adapter.calls == 0


# --- Live-Gate: public_source (Demo-Slice 2026-07-17) ------------------------


def _live_settings(monkeypatch):
    settings = get_settings().model_copy(update={
        "ai_eval_mode": "real",
        "agent_model_gpt_56_luna_id": "hermetic-openai-model",
    })
    monkeypatch.setattr(gateway, "get_settings", lambda: settings)


def test_real_eval_gate_allows_public_source_with_confirmation(db, monkeypatch):
    _live_settings(monkeypatch)
    adapter = _RealEvalStub()
    resp = invoke(
        db,
        base_request(
            classification={
                "sensitivity": "public", "origin": "public_source",
                "nda_applies": False,
            },
            run_confirmation=True,
        ),
        provider_resolver=fake_resolver(adapter),
    )
    assert isinstance(resp, ModelResponse)
    assert resp.generation_kind == "model_generated"
    assert adapter.calls == 1


def test_real_eval_gate_blocks_public_source_without_confirmation(db, monkeypatch):
    _live_settings(monkeypatch)
    adapter = _RealEvalStub()
    resp = invoke(
        db,
        base_request(
            classification={
                "sensitivity": "public", "origin": "public_source",
                "nda_applies": False,
            },
            run_confirmation=False,
        ),
        provider_resolver=fake_resolver(adapter),
    )
    assert isinstance(resp, SafeFailure) and resp.status == "blocked"
    assert resp.safe_detail == "real_eval_gate_blocked"
    assert adapter.calls == 0


def test_real_eval_gate_blocks_internal_public_source(db, monkeypatch):
    _live_settings(monkeypatch)
    adapter = _RealEvalStub()
    resp = invoke(
        db,
        base_request(
            classification={
                "sensitivity": "internal", "origin": "public_source",
                "nda_applies": False,
            },
            run_confirmation=True,
        ),
        provider_resolver=fake_resolver(adapter),
    )
    assert isinstance(resp, SafeFailure) and resp.status == "blocked"
    assert adapter.calls == 0


def test_real_eval_gate_still_blocks_real_project_origin(db, monkeypatch):
    _live_settings(monkeypatch)
    adapter = _RealEvalStub()
    resp = invoke(
        db,
        base_request(
            classification={
                "sensitivity": "public", "origin": "real_project",
                "nda_applies": False,
            },
            run_confirmation=True,
        ),
        provider_resolver=fake_resolver(adapter),
    )
    assert isinstance(resp, SafeFailure) and resp.status == "blocked"
    assert adapter.calls == 0


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
    invocation = db.get(AgentInvocation, resp.invocation_id)
    assert invocation.retry_count == 2  # je ein Retry auf zwei sichtbaren Routen


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
