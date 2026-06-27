"""CostGuard for model invocations (Milestone 9A).

Enforces call-count / retry / timeout / token limits from the AgentProfile.
No pricing or token-cost formula exists in any contract, so CHF cost is NEVER
invented — ``UsageRecord.cost_chf`` is a non-nullable technical placeholder (0.0)
and is never surfaced or claimed as an actual cost.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.registry import AgentProfileDef
from app.agents.providers.base import ProviderUsage
from app.db.models import AgentInvocation, UsageRecord

# Statuses that count as an accepted (non-idempotent) call against the run limit.
_COUNTED_STATUSES = ("queued", "running", "succeeded", "failed", "timed_out")


@dataclass(frozen=True)
class CostDecision:
    allowed: bool
    reason: str


def _max_per_run(profile: AgentProfileDef) -> int | None:
    limits = profile.invocation_limits
    for key in ("max_per_run", "max_per_run_bundle", "max_per_research_task"):
        if key in limits:
            return int(limits[key])
    return None


def pre_check(
    db: Session,
    *,
    profile: AgentProfileDef,
    run_id: str | None,
    exclude_invocation_id: str | None = None,
) -> CostDecision:
    """Block before invocation if the per-run call limit is already reached.
    The current (just-created) invocation is excluded from the count."""
    limit = _max_per_run(profile)
    if run_id is not None and limit is not None:
        used = db.scalar(
            select(func.count(AgentInvocation.invocation_id)).where(
                AgentInvocation.run_id == run_id,
                AgentInvocation.profile_id == profile.profile_id,
                AgentInvocation.status.in_(_COUNTED_STATUSES),
                AgentInvocation.invocation_id != exclude_invocation_id,
            )
        ) or 0
        if used >= limit:
            return CostDecision(False, f"max_invocations_per_run({limit})")
    return CostDecision(True, "")


def max_retries(profile: AgentProfileDef) -> int:
    return int(profile.invocation_limits.get("max_retries", 0))


def timeout_seconds(profile: AgentProfileDef) -> int:
    return int(profile.invocation_limits.get("timeout_seconds", 120))


def output_within_limit(profile: AgentProfileDef, usage: ProviderUsage) -> bool:
    cap = profile.invocation_limits.get("max_output_tokens")
    return cap is None or usage.output_tokens <= int(cap)


def record_usage(
    db: Session,
    *,
    run_id: str | None,
    workspace_id: str,
    provider: str,
    model_id: str,
    usage: ProviderUsage,
) -> UsageRecord:
    """Persist token usage. cost_chf=0.0 is a placeholder (no pricing config)."""
    record = UsageRecord(
        usage_record_id=str(uuid.uuid4()),
        run_id=run_id,
        workspace_id=workspace_id,
        provider=provider,
        model=model_id,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_chf=0.0,  # placeholder only — never displayed as an actual cost
    )
    db.add(record)
    db.flush()
    return record
