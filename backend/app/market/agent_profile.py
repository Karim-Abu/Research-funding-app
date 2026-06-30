"""Beta-internal market-comparison structuring agent profile (Milestone 9I-B).

No finalized contract is modified: the profile is injected into the in-memory agent
registry at runtime and its I/O schemas live only in ``app.agents.schemas.SCHEMA_MODELS``
(code), not in the finalized ``schema_catalog.yaml`` / ``agents_v1_1.yaml``. The profile
has NO tools (``allowed_tools=()``) — it cannot search, fetch, or access the network; it
only structures already-imported public fragments passed in its input payload.
"""
from __future__ import annotations

from app.agents import gateway
from app.agents.registry import AgentProfileDef, DataPolicyReq

PROFILE_ID = "MC.market_comparison"
INPUT_SCHEMA = "MarketComparisonInput@v1"
OUTPUT_SCHEMA = "MarketComparisonResult@v1"

_PROFILE = AgentProfileDef(
    profile_id=PROFILE_ID,
    agent_id="MC",
    name="Market & Competitor Comparison (beta-internal)",
    status="beta_internal_active_m9i_b",
    advisory=True,
    allowed_tools=(),  # no tools: structures provided public fragments only
    input_schema=INPUT_SCHEMA,
    output_schema=OUTPUT_SCHEMA,
    controls=(
        "CTRL.DATA_POLICY", "CTRL.INPUT_SCHEMA", "CTRL.PROMPT_INJECTION",
        "CTRL.SOURCE_TRUST", "CTRL.COST_GUARD", "CTRL.OUTPUT_SCHEMA", "CTRL.AUDIT_WRITE",
    ),
    primary_model="anthropic_haiku_45",
    fallback_model="openai_gpt_54_mini",
    optional_candidate=None,
    data_policy=DataPolicyReq(
        allowed_sensitivity=("public",),
        blocked_sensitivity=("confidential",),
        allowed_processing_modes=("cloud_assisted",),
        nda_applies="blocked",
        internal_preconditions=(),
    ),
    invocation_limits={
        "max_per_comparison": 1,
        "max_retries": 1,
        "timeout_seconds": 180,
        "max_output_tokens": 4000,
    },
    failure_policy={"schema_failure": "retry_once_then_skip",
                    "provider_failure": "fallback_then_skip"},
)


def market_profile() -> AgentProfileDef:
    return _PROFILE


def ensure_registered() -> None:
    """Idempotently inject the beta profile into the cached agent registry."""
    registry = gateway.get_agent_registry()
    if PROFILE_ID not in registry.profiles:
        registry.profiles[PROFILE_ID] = _PROFILE
