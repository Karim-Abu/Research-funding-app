"""Minimal deterministic ControlResult persistence (distinct from AuditEvent)."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models import ControlResult


def record(
    db: Session,
    *,
    workspace_id: str,
    control_id: str,
    status: str,
    project_id: str | None = None,
    source_id: str | None = None,
    source_version_id: str | None = None,
    detail: str | None = None,
    run_id: str | None = None,
    tool_invocation_id: str | None = None,
    agent_invocation_id: str | None = None,
    research_task_id: str | None = None,
) -> ControlResult:
    result = ControlResult(
        control_result_id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        project_id=project_id,
        source_id=source_id,
        source_version_id=source_version_id,
        control_id=control_id,
        status=status,
        detail=detail,
        run_id=run_id,
        tool_invocation_id=tool_invocation_id,
        agent_invocation_id=agent_invocation_id,
        research_task_id=research_task_id,
    )
    db.add(result)
    db.flush()
    return result
