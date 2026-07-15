"""Typed AgentProfile registry loader (Milestone 9A) — fail-closed at startup.

Loads ``agents_v1_1.yaml`` and cross-validates every reference against the tool,
control and schema catalogs. Any corruption (unknown tool/control/schema/model
route, duplicate id, tool-permission mismatch, illegal network access) raises
``AgentRegistryError`` so the app fails closed. Never imported by frontend code.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.registry.loader import RegistryError, _contracts_dir, _read_yaml

logger = logging.getLogger("app.agents.registry")

AGENTS_FILE = "agents_v1_1.yaml"
TOOLS_FILE = "tools_v1_1.yaml"
CONTROLS_FILE = "controls.yaml"
SCHEMA_CATALOG_FILE = "schema_catalog.yaml"


class AgentRegistryError(RegistryError):
    """Raised when the agent registry is missing, malformed or inconsistent."""


@dataclass(frozen=True)
class ModelRoute:
    key: str
    provider: str
    model_id: str
    alias: str
    status: str


@dataclass(frozen=True)
class DataPolicyReq:
    allowed_sensitivity: tuple[str, ...]
    blocked_sensitivity: tuple[str, ...]
    allowed_processing_modes: tuple[str, ...]
    nda_applies: str
    internal_preconditions: tuple[str, ...]


@dataclass(frozen=True)
class AgentProfileDef:
    profile_id: str
    agent_id: str
    name: str
    status: str
    advisory: bool
    allowed_tools: tuple[str, ...]
    input_schema: str
    output_schema: str
    controls: tuple[str, ...]
    primary_model: str
    fallback_model: str | None
    optional_candidate: str | None
    data_policy: DataPolicyReq
    invocation_limits: dict[str, Any]
    failure_policy: dict[str, Any]
    # Ebene E: Skill-Version der Rolle — vom Loader aus den versionierten
    # Prompt-Assets befüllt (eine Quelle der Wahrheit; None nur für
    # Platzhalter-Profile ohne aktivierten Prompt).
    prompt_version: str | None = None

    @property
    def reasoning_effort(self) -> str | None:
        """Optionale Reasoning-/Effort-Konfiguration (invocation_limits.reasoning_effort)."""
        value = self.invocation_limits.get("reasoning_effort")
        return str(value) if value is not None else None

    @property
    def max_cost_chf(self) -> float | None:
        """Optionales Kostenlimit pro Invocation (invocation_limits.max_cost_chf)."""
        value = self.invocation_limits.get("max_cost_chf")
        return float(value) if value is not None else None


@dataclass(frozen=True)
class AgentDef:
    agent_id: str
    name: str
    profiles: tuple[str, ...]
    default_model: str
    fallback_model: str | None
    max_invocations_per_run: int
    max_retries_per_invocation: int
    audit_required: bool


@dataclass(frozen=True)
class AgentRegistry:
    model_routes: dict[str, ModelRoute]
    agents: dict[str, AgentDef]
    profiles: dict[str, AgentProfileDef]

    def profile(self, profile_id: str) -> AgentProfileDef:
        try:
            return self.profiles[profile_id]
        except KeyError as exc:
            raise AgentRegistryError(f"Unknown agent profile: {profile_id}") from exc

    def route(self, key: str) -> ModelRoute:
        try:
            return self.model_routes[key]
        except KeyError as exc:
            raise AgentRegistryError(f"Unknown model route: {key}") from exc


def _profile_permitted(profile_id: str, allowed: list[str]) -> bool:
    """Tool permission honouring agent wildcards like ``A2.*``."""
    prefix = profile_id.split(".")[0]
    return profile_id in allowed or f"{prefix}.*" in allowed


def _data_policy(raw: dict[str, Any], profile_id: str) -> DataPolicyReq:
    if not isinstance(raw, dict):
        raise AgentRegistryError(f"{profile_id}: missing data_policy")
    return DataPolicyReq(
        allowed_sensitivity=tuple(raw.get("allowed_sensitivity", []) or []),
        blocked_sensitivity=tuple(raw.get("blocked_sensitivity", []) or []),
        allowed_processing_modes=tuple(raw.get("allowed_processing_modes", []) or []),
        nda_applies=str(raw.get("nda_applies", "blocked")),
        internal_preconditions=tuple(raw.get("internal_preconditions", []) or []),
    )


def _build(
    agents_raw: dict[str, Any],
    tools_raw: dict[str, Any],
    controls_raw: dict[str, Any],
    schemas_raw: dict[str, Any],
) -> AgentRegistry:
    # Reference sets ---------------------------------------------------------
    tool_index = {
        t["tool_id"]: t for t in tools_raw.get("tools", []) if "tool_id" in t
    }
    control_ids = {c["control_id"] for c in controls_raw.get("controls", [])}
    schema_ids = {s["schema_id"] for s in schemas_raw.get("schemas", [])}

    model_routes: dict[str, ModelRoute] = {}
    for key, entry in (agents_raw.get("model_catalog") or {}).items():
        model_routes[key] = ModelRoute(
            key=key,
            provider=entry["provider"],
            model_id=entry["model_id"],
            alias=entry.get("alias", entry["model_id"]),
            status=entry.get("status", "unknown"),
        )
    if not model_routes:
        raise AgentRegistryError("agents registry has no model_catalog")

    # Profiles ---------------------------------------------------------------
    profiles: dict[str, AgentProfileDef] = {}
    for raw in agents_raw.get("profiles", []):
        pid = raw["profile_id"]
        if pid in profiles:
            raise AgentRegistryError(f"Duplicate profile_id: {pid}")

        in_schema = raw["input_schema"]
        out_schema = raw["output_schema"]
        for sid in (in_schema, out_schema):
            if sid not in schema_ids:
                raise AgentRegistryError(f"{pid}: unknown schema_id {sid}")

        for cid in raw.get("controls", []):
            if cid not in control_ids:
                raise AgentRegistryError(f"{pid}: unknown control_id {cid}")

        for tool_id in raw.get("allowed_tools", []):
            tool = tool_index.get(tool_id)
            if tool is None:
                raise AgentRegistryError(f"{pid}: unknown tool_id {tool_id}")
            if not _profile_permitted(pid, tool.get("allowed_agent_profiles", [])):
                raise AgentRegistryError(
                    f"{pid}: tool {tool_id} does not authorize this profile"
                )
            if tool.get("network_access", "none") != "none":
                raise AgentRegistryError(
                    f"{pid}: tool {tool_id} grants direct network access"
                )

        model = raw.get("model") or {}
        primary = model.get("primary")
        fallback = model.get("fallback")
        optional = model.get("optional_candidate")
        for mk in (primary, fallback, optional):
            if mk is not None and mk not in model_routes:
                raise AgentRegistryError(f"{pid}: unknown model route {mk}")
        if primary is None:
            raise AgentRegistryError(f"{pid}: missing primary model")

        # Ebene E: Skill-Version aus den versionierten Prompt-Assets — die
        # Registry ist damit die eine Quelle der Wahrheit pro Rolle (Profil,
        # Prompt-Version, Provider/Modellroute, Limits). Lazy Import, damit
        # kein Zyklus zwischen registry und prompt_assets entsteht.
        from app.agents.prompt_assets import prompt_version_for

        profiles[pid] = AgentProfileDef(
            profile_id=pid,
            agent_id=raw["agent_id"],
            name=raw.get("name", pid),
            status=raw.get("status", "proposed"),
            advisory=bool(raw.get("advisory", True)),
            allowed_tools=tuple(raw.get("allowed_tools", [])),
            input_schema=in_schema,
            output_schema=out_schema,
            controls=tuple(raw.get("controls", [])),
            primary_model=primary,
            fallback_model=fallback,
            optional_candidate=optional,
            data_policy=_data_policy(raw.get("data_policy"), pid),
            invocation_limits=dict(raw.get("invocation_limits", {})),
            failure_policy=dict(raw.get("failure_policy", {})),
            prompt_version=prompt_version_for(pid),
        )

    # Agents -----------------------------------------------------------------
    agents: dict[str, AgentDef] = {}
    for raw in agents_raw.get("agents", []):
        aid = raw["agent_id"]
        if aid in agents:
            raise AgentRegistryError(f"Duplicate agent_id: {aid}")
        for pid in raw.get("profiles", []):
            if pid not in profiles:
                raise AgentRegistryError(f"{aid}: references unknown profile {pid}")
            if profiles[pid].agent_id != aid:
                raise AgentRegistryError(f"{pid}: agent_id mismatch under {aid}")
        agents[aid] = AgentDef(
            agent_id=aid,
            name=raw.get("name", aid),
            profiles=tuple(raw.get("profiles", [])),
            default_model=raw.get("default_model", ""),
            fallback_model=raw.get("fallback_model"),
            max_invocations_per_run=int(raw.get("max_invocations_per_run", 0)),
            max_retries_per_invocation=int(raw.get("max_retries_per_invocation", 0)),
            audit_required=bool(raw.get("audit_required", True)),
        )
    if not profiles:
        raise AgentRegistryError("agents registry has no profiles")

    return AgentRegistry(model_routes=model_routes, agents=agents, profiles=profiles)


def load_agent_registry() -> AgentRegistry:
    base = _contracts_dir()
    registry = _build(
        _read_yaml(base / AGENTS_FILE),
        _read_yaml(base / TOOLS_FILE),
        _read_yaml(base / CONTROLS_FILE),
        _read_yaml(base / SCHEMA_CATALOG_FILE),
    )
    logger.info(
        "agent registry loaded agents=%d profiles=%d model_routes=%d",
        len(registry.agents), len(registry.profiles), len(registry.model_routes),
    )
    return registry


@lru_cache
def get_agent_registry() -> AgentRegistry:
    return load_agent_registry()
