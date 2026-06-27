"""Run policy: processing_mode validation + immutable RunPolicySnapshot."""
from __future__ import annotations

from app.api.errors import ProblemException
from app.config.settings import Settings
from app.contracts.run import RunSettings
from app.db.models import RunPolicySnapshot

POLICY_VERSION = "1.1.0"


def validate_processing_mode(mode: str) -> None:
    """Honest handling — never silently downgrade cloud_assisted.

    M3 performs no external provider calls. `deterministic_only` and
    `local_only` are accepted. `cloud_assisted` requires an approved provider
    route, which is not available in the evaluation beta (Data Policy), so it is
    rejected with a contract 403.
    """
    if mode == "cloud_assisted":
        raise ProblemException(
            status=403,
            code="cloud_processing_unavailable",
            title="Forbidden",
            detail="Cloud-assisted processing is not available in this deployment.",
        )


def build_policy_snapshot(
    run_id: str, settings: RunSettings, app_settings: Settings
) -> RunPolicySnapshot:
    return RunPolicySnapshot(
        run_id=run_id,
        processing_mode=settings.processing_mode,
        max_cost_chf=settings.max_cost_chf,
        max_llm_calls=settings.max_llm_calls,
        max_web_calls=settings.max_web_calls,
        max_retries=app_settings.run_default_max_retries,
        max_redrafts=app_settings.run_default_max_redrafts,
        timeout_seconds=app_settings.run_default_timeout_seconds,
        allowed_routes=[],
        policy_version=POLICY_VERSION,
    )
