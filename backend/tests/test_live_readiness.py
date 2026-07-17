"""Live-Readiness-Vertrag (Ebene E) — Modi, Preflight, Artefakt-Versionen.

Pins:
1. Live wird nie still fake: nicht verfügbare Provider ⇒ SafeFailure, nie ein
   FakeProvider-Ersatz; Capabilities mit Live-Absicht ⇒ ``live_unavailable``,
   nie ``fake_demo``.
2. ``not_run`` erscheint nie als bestanden (Preflight-Status + Report).
3. Tatsächliches Modell (``actual_model_id``) und Skill-Version
   (``prompt_version``) stehen im Technical-Evidence-Artefakt.
4. Preflight-/Report-Pfade tragen keine Rohprompts/Keys.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.agents import gateway
from app.agents.gateway import ModelResponse, SafeFailure, invoke
from app.agents.providers import FakeProvider
from app.agents.providers.base import ProviderResult, ProviderUsage
from app.agents.registry import get_agent_registry
from app.api.capabilities import get_capabilities
from app.config.settings import Settings
from app.db.models import AgentInvocation, AgentInvocationAttempt
from app.db.session import SessionLocal
from app.evaluation.preflight import (
    FAIL,
    NOT_RUN,
    PASS,
    PING_PROMPT,
    classify_provider_error,
    firecrawl_mode,
    preflight_agent_provider,
    preflight_route,
    persist_route_preflight,
    route_preflight_passed,
    render_report,
    run_preflight,
)
from app.exports.snapshot import _technical_trace
from tests.agent_helpers import base_request, fake_resolver, make_run

PROFILE = "A1.project_fact_extraction"


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# --- 1. Live wird nie still fake ---------------------------------------------

def test_unavailable_provider_yields_safe_failure_never_fake(db):
    """Kein Adapter auflösbar ⇒ ehrlicher Fehler; nie ein Fake-Ersatz."""
    response = invoke(db, base_request(), provider_resolver=lambda _route: None)
    assert isinstance(response, SafeFailure)
    assert response.status == "failed"
    assert response.safe_detail == "provider_unavailable"
    inv = db.get(AgentInvocation, response.invocation_id)
    assert (inv.context_meta or {}).get("actual_adapter") != "fake"


class _UnavailableAdapter(FakeProvider):
    name = "openai_direct"

    def available(self) -> bool:  # Live-Route konfiguriert, aber ohne Key.
        return False


def test_configured_but_unavailable_live_route_never_falls_back_to_fake(db):
    adapter = _UnavailableAdapter()
    response = invoke(db, base_request(), provider_resolver=fake_resolver(adapter))
    assert isinstance(response, SafeFailure)
    assert response.safe_detail == "provider_unavailable"
    assert adapter.calls == 0  # nie generiert — auch nicht als "Demo"


def test_capabilities_live_intent_yields_live_unavailable_not_fake_demo():
    """ai_eval_mode=real ohne Key ⇒ live_unavailable — auch wenn der
    Fake-Provider aktiviert wäre (Live fällt nie still auf Demo zurück)."""
    settings = Settings(
        ai_eval_mode="real", agent_fake_provider=True,
        openai_api_key=None, anthropic_api_key=None,
    )
    caps = get_capabilities(_=object(), settings=settings)
    assert caps.generation_mode == "live_unavailable"
    assert caps.generation_unavailable_reason == "live_fake_conflict"


def test_capabilities_modes_are_distinct():
    fake = Settings(ai_eval_mode="off", agent_fake_provider=True)
    assert get_capabilities(_=object(), settings=fake).generation_mode == "fake_demo"
    off = Settings(ai_eval_mode="off", agent_fake_provider=False)
    assert get_capabilities(_=object(), settings=off).generation_mode == "unavailable"
    live = Settings(
        ai_eval_mode="real", agent_fake_provider=False,
        openai_api_key="sk-test-not-real",
    )
    caps = get_capabilities(_=object(), settings=live)
    assert caps.generation_mode == "live_unavailable"
    assert caps.generation_unavailable_reason == "live_model_id_missing"


def test_firecrawl_tri_state_is_explicit():
    assert firecrawl_mode(Settings(web_research_enabled=False)) == "disabled"
    assert firecrawl_mode(
        Settings(web_research_enabled=True, web_research_fake_provider=True)
    ) == "fake"
    assert firecrawl_mode(
        Settings(
            web_research_enabled=True, web_research_fake_provider=False,
            firecrawl_api_key="fc-test-not-real",
        )
    ) == "live"
    assert firecrawl_mode(
        Settings(
            web_research_enabled=True, web_research_fake_provider=False,
            firecrawl_api_key=None,
        )
    ) == "not_configured"


# --- 2. not_run erscheint nie als bestanden ----------------------------------

def test_preflight_without_key_is_not_run_never_passed():
    class _NoKey:
        name = "openai_direct"

        def available(self) -> bool:
            return False

        def generate(self, request):  # pragma: no cover — darf nie aufgerufen werden
            raise AssertionError("no network call without key")

    result = preflight_agent_provider(
        "openai",
        settings=Settings(ai_eval_mode="real", agent_fake_provider=False),
        adapter=_NoKey(),
        execute_live=True,
    )
    assert result.status == FAIL  # key_present ist ehrlich fail …
    by_name = {check.name: check for check in result.checks}
    assert by_name["key_present"].status == FAIL
    # … und alle nicht ausgeführten Checks sind not_run — nie bestanden.
    for name in ("api_reachable", "model_available", "structured_output"):
        assert by_name[name].status == NOT_RUN


def test_preflight_without_opt_in_is_not_run():
    class _Keyed(FakeProvider):
        name = "openai_direct"

    result = preflight_agent_provider(
        "openai",
        settings=Settings(ai_eval_mode="real", agent_fake_provider=False),
        adapter=_Keyed(),
        execute_live=False,
    )
    assert result.status == NOT_RUN
    assert all(
        check.status in (PASS, NOT_RUN) for check in result.checks
    )
    report = render_report([result])
    assert "not_run" in report
    # Ein Sammel-Grün gibt es nicht: not_run wird wörtlich berichtet.
    assert "Gesamtstatus: bestanden" not in report


def test_preflight_pass_path_with_injected_adapter():
    class _Echo(FakeProvider):
        name = "openai_direct"

        def generate(self, request):
            return ProviderResult(
                raw_output='{"pong": true}',
                usage=ProviderUsage(1, 1),
                model="gpt-echo-resolved",
            )

    result = preflight_agent_provider(
        "openai",
        settings=Settings(
            ai_eval_mode="real",
            agent_fake_provider=False,
            agent_model_gpt_56_luna_id="requested-hermetic-model",
        ),
        adapter=_Echo(),
        execute_live=True,
    )
    assert result.status == PASS
    by_name = {check.name: check for check in result.checks}
    assert "gpt-echo-resolved" in by_name["model_available"].detail
    report = render_report([result])
    # Kein Rohprompt im Report (Whitelist: Status, Codes, Modell-IDs).
    assert PING_PROMPT not in report


def test_route_preflight_requires_environment_model_resolution():
    result = preflight_route(
        "openai_gpt_56_luna_candidate",
        settings=Settings(
            ai_eval_mode="real",
            agent_fake_provider=False,
            agent_model_gpt_56_luna_id=None,
        ),
        adapter=FakeProvider(), execute_live=True,
    )
    assert result.status == FAIL
    assert result.error_class == "model_unavailable"


def test_route_preflight_fails_closed_on_live_fake_conflict():
    adapter = FakeProvider()
    result = preflight_route(
        "openai_gpt_56_luna_candidate",
        settings=Settings(
            ai_eval_mode="real",
            agent_fake_provider=True,
            agent_model_gpt_56_luna_id="must-not-be-called",
        ),
        adapter=adapter,
        execute_live=True,
    )
    assert result.status == FAIL
    assert result.error_class == "live_fake_conflict"
    assert adapter.calls == 0


def test_fresh_persisted_route_preflight_expires(db):
    class _Echo(FakeProvider):
        name = "openai_direct"

        def generate(self, request):
            return ProviderResult(
                raw_output='{"pong": true}', usage=ProviderUsage(1, 1),
                model="actual-hermetic-model",
            )

    settings = Settings(
        ai_eval_mode="real",
        agent_fake_provider=False,
        openai_api_key="sk-hermetic",
        agent_model_gpt_56_luna_id="requested-hermetic-model",
        agent_model_pricing_chf_per_million={
            "requested-hermetic-model": {
                "input_chf_per_million": 1,
                "output_chf_per_million": 2,
                "price_version": "test-v1",
                "source_url": "https://prices.example.test",
                "checked_at": "2026-07-16",
            }
        },
        provider_preflight_ttl_seconds=60,
    )
    result = preflight_route(
        "openai_gpt_56_luna_candidate", settings=settings,
        adapter=_Echo(), execute_live=True,
    )
    assert result.status == PASS
    row = persist_route_preflight(db, result, settings=settings)
    assert row.requested_model_id == "requested-hermetic-model"
    assert row.actual_model_id == "actual-hermetic-model"
    assert route_preflight_passed(db, result.route_key, settings=settings)
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.flush()
    assert not route_preflight_passed(db, result.route_key, settings=settings)


def test_rate_limit_and_quota_errors_are_understandable():
    code, text = classify_provider_error("openai http 429")
    assert code == "rate_limited"
    assert "Kontingent" in text or "Rate-Limit" in text
    code, text = classify_provider_error("anthropic http 401")
    assert code == "auth_failed"
    code, text = classify_provider_error("openai http 404")
    assert code == "model_unavailable"


def test_run_preflight_without_opt_in_makes_no_network_calls():
    results = run_preflight(
        settings=Settings(), registry=get_agent_registry(), execute_live=False
    )
    assert {result.provider for result in results} == {
        "openai", "anthropic", "firecrawl"
    }
    assert all(result.status != PASS for result in results)


# --- 3. Modell + Skill-Version im Artefakt ------------------------------------

def test_fake_call_records_actual_model_fake(db):
    response = invoke(
        db, base_request(), provider_resolver=fake_resolver(FakeProvider())
    )
    assert isinstance(response, ModelResponse)
    assert response.actual_model_id == "fake"
    inv = db.get(AgentInvocation, response.invocation_id)
    assert inv.actual_model_id == "fake"
    assert inv.prompt_version


def test_technical_trace_carries_actual_model_and_prompt_version(db):
    run_id = make_run(db)
    from app.db.models import AnalysisRun

    run = db.get(AnalysisRun, run_id)
    invocation_id = "inv-" + uuid.uuid4().hex[:8]
    db.add(
        AgentInvocation(
            invocation_id=invocation_id,
            run_id=run_id, workspace_id=run.workspace_id,
            agent_id="A2", profile_id="A2.solution_innovation",
            model_route="m1", provider="openai_direct",
            model_id="gpt-route", requested_model_id="gpt-requested",
            actual_model_id="gpt-route-2026-06",
            input_schema_id="In@v1", output_schema_id="Out@v1",
            prompt_version="a2_solution_innovation_v3", status="succeeded",
            role_id="A2_INNOSUISSE_PROPOSAL_WRITER",
            skill_id="a2.novelty_4_2", skill_version="a2_novelty_skill_v2",
            retry_count=1, termination_reason="stop",
            context_meta={
                "actual_adapter": "openai_direct",
                "generation_kind": "model_generated",
                "model_call_attempted": True,
            },
        )
    )
    now = datetime.now(timezone.utc)
    db.add(AgentInvocationAttempt(
        attempt_id="att-" + uuid.uuid4().hex[:8], invocation_id=invocation_id,
        attempt_index=0, retry_index=0, route_key="m1", route_alias="candidate",
        provider="openai_direct", requested_model_id="gpt-requested",
        actual_model_id="gpt-route-2026-06", status="succeeded",
        termination_reason="stop", started_at=now, finished_at=now,
    ))
    db.flush()
    trace = _technical_trace(db, run)
    item = next(
        entry for entry in trace["agent_invocations"]
        if entry["profile_id"] == "A2.solution_innovation"
    )
    assert item["model_id"] == "gpt-route"
    assert item["actual_model_id"] == "gpt-route-2026-06"
    assert item["prompt_version"] == "a2_solution_innovation_v3"
    assert item["skill_version"] == "a2_novelty_skill_v2"
    assert item["requested_model_id"] == "gpt-requested"
    assert item["retry_count"] == 1
    assert item["attempts"][0]["actual_model_id"] == "gpt-route-2026-06"


def test_run_snapshot_versions_include_prompt_and_model_versions():
    """Ebene E: Neue Runs frieren Prompt-Versionen + Modellrouten ein
    (→ config_versions im Technical Evidence)."""
    from app.runs.service import _agent_config_versions

    versions = _agent_config_versions()
    assert versions["prompt_versions"][PROFILE].startswith(
        "a1_project_fact_extraction_v"
    )
    assert versions["model_routes"][PROFILE]


def test_registry_is_single_source_for_role_configuration():
    """Jede Rolle trägt Skill-Version, Provider/Modellroute, Timeout, Retries
    (und optional reasoning_effort/max_cost_chf) in der Registry."""
    registry = get_agent_registry()
    profile = registry.profile(PROFILE)
    route = registry.route(profile.primary_model)
    assert profile.prompt_version  # Skill-Version aus den Prompt-Assets
    assert route.provider and route.model_id
    assert profile.invocation_limits.get("timeout_seconds")
    assert profile.invocation_limits.get("max_retries") is not None
    assert profile.reasoning_effort is None or isinstance(
        profile.reasoning_effort, str
    )
    assert profile.max_cost_chf is None or isinstance(profile.max_cost_chf, float)
