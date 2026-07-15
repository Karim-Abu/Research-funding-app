"""Agent registry loading + fail-closed validation (Milestone 9A)."""
from __future__ import annotations

import copy

import pytest

from app.agents.registry import (
    AgentRegistryError,
    _build,
    get_agent_registry,
    load_agent_registry,
)


def _raws():
    agents = {
        "model_catalog": {
            "m1": {"provider": "anthropic_direct", "model_id": "x1", "alias": "x1", "status": "active"},
            "m2": {"provider": "openai_direct", "model_id": "x2", "alias": "x2", "status": "active"},
        },
        "agents": [
            {
                "agent_id": "A1", "name": "A1", "profiles": ["A1.p"],
                "default_model": "x1", "fallback_model": "x2",
                "max_invocations_per_run": 1, "max_retries_per_invocation": 1,
                "audit_required": True,
            }
        ],
        "profiles": [
            {
                "profile_id": "A1.p", "agent_id": "A1", "name": "P",
                "input_schema": "In@v1", "output_schema": "Out@v1",
                "controls": ["CTRL.X"], "allowed_tools": ["tool_a"],
                "model": {"primary": "m1", "fallback": "m2"},
                "data_policy": {
                    "allowed_sensitivity": ["public"], "blocked_sensitivity": ["confidential"],
                    "allowed_processing_modes": ["cloud_assisted"], "nda_applies": "blocked",
                },
                "invocation_limits": {"max_per_run": 1, "max_retries": 1, "timeout_seconds": 60},
            }
        ],
    }
    tools = {"tools": [{"tool_id": "tool_a", "allowed_agent_profiles": ["A1.*"], "network_access": "none"}]}
    controls = {"controls": [{"control_id": "CTRL.X"}]}
    schemas = {"schemas": [{"schema_id": "In@v1"}, {"schema_id": "Out@v1"}]}
    return agents, tools, controls, schemas


def test_real_registry_loads_and_validates():
    reg = load_agent_registry()
    assert set(reg.agents) == {"A1", "A2", "A3"}
    assert len(reg.profiles) == 13
    pfe = reg.profile("A1.project_fact_extraction")
    assert pfe.primary_model == "anthropic_haiku_45"
    assert pfe.output_schema == "ProjectFactExtractionResult@v1"
    assert reg.route(pfe.primary_model).provider == "anthropic_direct"


def test_get_agent_registry_is_cached():
    assert get_agent_registry() is get_agent_registry()


def test_activated_profiles_carry_prompt_version():
    """Ebene E: die Registry ist die eine Quelle der Wahrheit je Rolle —
    aktivierte Profile tragen ihre Skill-/Prompt-Version aus den
    versionierten Prompt-Assets (nie None)."""
    reg = load_agent_registry()
    pfe = reg.profile("A1.project_fact_extraction")
    assert pfe.prompt_version is not None
    assert pfe.prompt_version.startswith("a1_project_fact_extraction_v")


def test_reasoning_effort_and_cost_limit_default_none_and_parse():
    """Optionale Live-Konfiguration je Rolle (Ebene E): ohne YAML-Eintrag
    None (keine Verhaltensänderung); gesetzte Werte werden typisiert."""
    reg = _build(*_raws())
    profile = reg.profile("A1.p")
    assert profile.reasoning_effort is None
    assert profile.max_cost_chf is None

    agents, tools, controls, schemas = _raws()
    agents["profiles"][0]["invocation_limits"].update(
        {"reasoning_effort": "medium", "max_cost_chf": 0.5}
    )
    configured = _build(agents, tools, controls, schemas).profile("A1.p")
    assert configured.reasoning_effort == "medium"
    assert configured.max_cost_chf == 0.5


def test_minimal_valid_build():
    assert _build(*_raws()).profile("A1.p").agent_id == "A1"


def test_duplicate_profile_id_fails():
    agents, tools, controls, schemas = _raws()
    agents["profiles"].append(copy.deepcopy(agents["profiles"][0]))
    with pytest.raises(AgentRegistryError, match="Duplicate profile_id"):
        _build(agents, tools, controls, schemas)


def test_unknown_tool_id_fails():
    agents, tools, controls, schemas = _raws()
    agents["profiles"][0]["allowed_tools"] = ["does_not_exist"]
    with pytest.raises(AgentRegistryError, match="unknown tool_id"):
        _build(agents, tools, controls, schemas)


def test_unknown_schema_id_fails():
    agents, tools, controls, schemas = _raws()
    agents["profiles"][0]["output_schema"] = "Missing@v1"
    with pytest.raises(AgentRegistryError, match="unknown schema_id"):
        _build(agents, tools, controls, schemas)


def test_unknown_control_id_fails():
    agents, tools, controls, schemas = _raws()
    agents["profiles"][0]["controls"] = ["CTRL.NOPE"]
    with pytest.raises(AgentRegistryError, match="unknown control_id"):
        _build(agents, tools, controls, schemas)


def test_unknown_model_route_fails():
    agents, tools, controls, schemas = _raws()
    agents["profiles"][0]["model"]["primary"] = "missing_model"
    with pytest.raises(AgentRegistryError, match="unknown model route"):
        _build(agents, tools, controls, schemas)


def test_tool_permission_mismatch_fails():
    agents, tools, controls, schemas = _raws()
    tools["tools"][0]["allowed_agent_profiles"] = ["A2.*"]  # A1.p not permitted
    with pytest.raises(AgentRegistryError, match="does not authorize this profile"):
        _build(agents, tools, controls, schemas)


def test_network_access_violation_fails():
    agents, tools, controls, schemas = _raws()
    tools["tools"][0]["network_access"] = "firecrawl_cloud"
    with pytest.raises(AgentRegistryError, match="direct network access"):
        _build(agents, tools, controls, schemas)
