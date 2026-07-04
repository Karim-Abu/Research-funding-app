"""Research-task-scoped CostGuard (Milestone 9I-A, binding correction 4).

Web search/fetch and A1 public-research limits are counted by ``research_task_id`` only.
Null ``run_id`` is NEVER used as an aggregation key, so unrelated tasks never pool.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ToolInvocation

# ToolInvocation statuses that count against the per-task limit.
_COUNTED_STATUSES = ("queued", "running", "succeeded", "failed")


@dataclass(frozen=True)
class CostDecision:
    allowed: bool
    reason: str


def tool_calls_used(db: Session, *, research_task_id: str, tool_id: str) -> int:
    return db.scalar(
        select(func.count(ToolInvocation.invocation_id)).where(
            ToolInvocation.research_task_id == research_task_id,
            ToolInvocation.tool_id == tool_id,
            ToolInvocation.status.in_(_COUNTED_STATUSES),
        )
    ) or 0


def pre_check_tool(
    db: Session, *, research_task_id: str, tool_id: str, max_calls: int
) -> CostDecision:
    """Block before a web tool call if the per-task limit for that tool is reached."""
    used = tool_calls_used(db, research_task_id=research_task_id, tool_id=tool_id)
    if used >= max_calls:
        return CostDecision(False, f"max_calls_per_task({tool_id},{max_calls})")
    return CostDecision(True, "")
