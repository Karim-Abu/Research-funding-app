"""Web-research Data Policy (Milestone 9I-A).

Implements the ``web_research_controls`` matrix from ``data_policy_v1_1.yaml`` for the
public-web-research tool boundary (search/fetch). Deny-by-default; most-restrictive
input wins; never a silent up/down-grade. Beta scope is **public/synthetic only**
(binding correction 7): internal/confidential/NDA/missing are blocked and no
internal-confirmation path is built.

This is distinct from ``app.agents.data_policy.evaluate`` (which gates model-route
calls); the two share the ``PolicyDecision`` shape but enforce different matrices.
"""
from __future__ import annotations

from app.agents.data_policy import PolicyDecision, effective_sensitivity
from app.config.settings import Settings

_ALLOWED_ORIGINS = {"public_source", "synthetic"}


def evaluate_web_research(
    *,
    classification: dict,
    processing_mode: str,
    settings: Settings,
    internal_public_confirmation_id: str | None = None,
) -> PolicyDecision:
    """Decide whether a public web search/fetch is allowed for this project.

    Returns a ``PolicyDecision`` (outcome ``allowed`` | ``blocked``; ``blocked`` always
    carries a stable reason). Every caller MUST persist a ``CTRL.DATA_POLICY``
    ControlResult + AuditEvent from the result.
    """
    cls = classification or {}
    sensitivity = effective_sensitivity(cls)
    origin = cls.get("origin")
    web_mode = cls.get("web_research_mode")
    nda = bool(cls.get("nda_applies"))

    # local_only never permits an external call. (deterministic_only is permitted iff
    # web_research_mode is validated_public — see the data_policy STEP 2 matrix.)
    if processing_mode == "local_only":
        return PolicyDecision("blocked", "blocked", "processing_mode_local_only")

    # Web research must be explicitly enabled on the classification.
    if web_mode != "validated_public":
        return PolicyDecision("blocked", "blocked", "web_research_mode_off")

    # NDA content is never part of an external query.
    if nda:
        return PolicyDecision("blocked", "blocked", "nda_applies")

    # Beta scope: public/synthetic only. Internal/confidential/missing are blocked and
    # no internal-confirmation web-research path exists (binding correction 7).
    if sensitivity != "public":
        return PolicyDecision(
            "blocked", "blocked", f"sensitivity_{sensitivity}_blocked_in_beta"
        )
    if origin not in _ALLOWED_ORIGINS:
        return PolicyDecision("blocked", "blocked", "origin_not_public_or_synthetic")

    return PolicyDecision("allowed", "passed", "public_validated_web_research_allowed")
