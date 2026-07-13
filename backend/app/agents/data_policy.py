"""Data Policy enforcement for model invocations (Milestone 9A).

Implements the active ``evaluation_beta`` matrix from ``data_policy_v1_1.yaml``:
policy is checked before every external model call; deny-by-default; most
restrictive input wins; never a silent up/down-grade of the processing mode.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.agents.registry import AgentProfileDef
from app.config.settings import Settings
from app.security.data_class import DataClass, derive_data_class

# Order from data_policy classification_resolution.effective_sensitivity_order.
_SENSITIVITY_RANK = {"public": 0, "internal": 1, "confidential": 2}
_NO_EXTERNAL_CALL_MODES = {"deterministic_only", "local_only"}


@dataclass(frozen=True)
class PolicyDecision:
    outcome: str  # allowed | allowed_with_confirmation | blocked
    status: str   # passed | warning | blocked  (ControlResult status)
    reason: str

    @property
    def blocked(self) -> bool:
        return self.outcome == "blocked"


def effective_sensitivity(classification: dict) -> str:
    """Most restrictive sensitivity; missing → confidential (deny-by-default)."""
    value = (classification or {}).get("sensitivity")
    if value not in _SENSITIVITY_RANK:
        return "confidential"
    return value


def evaluate(
    *,
    profile: AgentProfileDef,
    classification: dict,
    processing_mode: str,
    settings: Settings,
    run_confirmation: bool = False,
    local_provider: bool = False,
) -> PolicyDecision:
    sensitivity = effective_sensitivity(classification)
    nda = bool((classification or {}).get("nda_applies"))

    # Reserved for a future approved local/institutional model adapter. The
    # current gateway never sets this flag for FakeProvider. D1/D2 would still
    # require explicit confirmation; D3/UNKNOWN remain blocked.
    if processing_mode == "local_only" and local_provider:
        data_class = derive_data_class(classification or {})
        if data_class in (DataClass.D3_NDA_BLOCKED, DataClass.UNKNOWN):
            reason = "nda_applies" if nda else "unknown_classification_blocked"
            return PolicyDecision("blocked", "blocked", reason)
        if data_class == DataClass.D0_PUBLIC:
            return PolicyDecision("allowed", "passed", "public_local_allowed")
        if run_confirmation:
            return PolicyDecision(
                "allowed_with_confirmation", "warning",
                f"{sensitivity}_local_confirmed",
            )
        return PolicyDecision(
            "blocked", "blocked", f"{sensitivity}_local_requires_confirmation"
        )

    # Processing mode: deterministic_only / local_only never make an external call.
    if processing_mode in _NO_EXTERNAL_CALL_MODES:
        return PolicyDecision("blocked", "blocked", f"processing_mode_{processing_mode}")
    if processing_mode != "cloud_assisted":
        return PolicyDecision("blocked", "blocked", "processing_mode_not_cloud_assisted")
    if processing_mode not in profile.data_policy.allowed_processing_modes:
        return PolicyDecision("blocked", "blocked", "processing_mode_not_in_profile")

    # NDA → blocked for external processing.
    if nda:
        return PolicyDecision("blocked", "blocked", "nda_applies")

    # Explicit real-provider evaluation path. This is deliberately narrower
    # than ProviderPolicy and cannot override it: only synthetic/anonymized
    # origins, AI_EVAL_MODE=real and a one-run confirmation may pass here.
    origin = (classification or {}).get("origin")
    if origin in ("synthetic", "anonymized") and settings.ai_eval_mode == "real":
        if run_confirmation:
            return PolicyDecision(
                "allowed_with_confirmation", "warning", "real_eval_confirmed"
            )
        return PolicyDecision(
            "blocked", "blocked", "real_eval_requires_confirmation"
        )

    # Sensitivity gates (evaluation_beta matrix).
    if sensitivity in profile.data_policy.blocked_sensitivity or sensitivity == "confidential":
        return PolicyDecision("blocked", "blocked", "sensitivity_confidential_blocked")
    if sensitivity not in profile.data_policy.allowed_sensitivity:
        return PolicyDecision("blocked", "blocked", "sensitivity_not_allowed")

    if sensitivity == "public":
        return PolicyDecision("allowed", "passed", "public_cloud_allowed")

    if sensitivity == "internal":
        # Direct provider routes are institutionally not approved in the beta, so
        # internal real-project content is operationally blocked unless an
        # institutional route is approved AND the user confirms per run.
        if settings.agent_institutional_route_approved and run_confirmation:
            return PolicyDecision(
                "allowed_with_confirmation", "warning", "internal_approved_with_confirmation"
            )
        return PolicyDecision(
            "blocked", "blocked", "internal_requires_institutional_approval_and_confirmation"
        )

    return PolicyDecision("blocked", "blocked", "default_deny")
