"""Run policy: the immutable RunPolicySnapshot. The cloud-processing gate lives in
``app/runs/cloud_policy.py`` (Milestone 9D.2)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.config.settings import Settings
from app.contracts.run import RunSettings
from app.db.models import RunPolicySnapshot

if TYPE_CHECKING:
    from app.runs.cloud_policy import CloudDecision

POLICY_VERSION = "1.1.0"


def build_policy_snapshot(
    run_id: str,
    settings: RunSettings,
    app_settings: Settings,
    cloud_decision: "CloudDecision | None" = None,
) -> RunPolicySnapshot:
    confirmation = cloud_decision.confirmation if cloud_decision else None
    route_class = cloud_decision.provider_route_class if cloud_decision else None
    return RunPolicySnapshot(
        run_id=run_id,
        processing_mode=settings.processing_mode,
        max_cost_chf=settings.max_cost_chf,
        max_llm_calls=settings.max_llm_calls,
        max_web_calls=settings.max_web_calls,
        max_retries=app_settings.run_default_max_retries,
        max_redrafts=app_settings.run_default_max_redrafts,
        timeout_seconds=app_settings.run_default_timeout_seconds,
        allowed_routes=[route_class] if route_class else [],
        policy_version=POLICY_VERSION,
        cloud_confirmation_id=confirmation.confirmation_id if confirmation else None,
        provider_route_class=route_class,
    )
