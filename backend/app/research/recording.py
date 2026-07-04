"""Audit / control / tool-invocation recording for public web research (M9I-A).

Every web tool call (search/fetch) and every policy decision is recorded as a
ToolInvocation + ControlResult + AuditEvent scoped to ``research_task_id`` (never to a
run). No API keys, raw provider payloads or query secrets are ever written here.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import ToolInvocation
from app.repositories import audit, controls


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_control(
    db: Session,
    *,
    workspace_id: str,
    project_id: str | None,
    research_task_id: str,
    control_id: str,
    status: str,
    detail: str | None = None,
    tool_invocation_id: str | None = None,
) -> None:
    controls.record(
        db,
        workspace_id=workspace_id,
        project_id=project_id,
        control_id=control_id,
        status=status,
        detail=detail,
        research_task_id=research_task_id,
        tool_invocation_id=tool_invocation_id,
    )


def record_audit(
    db: Session,
    *,
    workspace_id: str,
    actor_user_id: str | None,
    action: str,
    research_task_id: str,
    detail: dict | None = None,
) -> None:
    audit.record(
        db,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type="research_task",
        target_id=research_task_id,
        detail=detail,
    )


def record_tool(
    db: Session,
    *,
    workspace_id: str,
    research_task_id: str,
    tool_id: str,
    caller: str,
    input_hash: str,
    output_hash: str | None,
    status: str,
    latency_ms: int | None = None,
    error_class: str | None = None,
) -> str:
    invocation_id = str(uuid.uuid4())
    db.add(
        ToolInvocation(
            invocation_id=invocation_id,
            workspace_id=workspace_id,
            run_id=None,
            research_task_id=research_task_id,
            tool_id=tool_id,
            caller=caller,
            input_hash=input_hash,
            output_hash=output_hash,
            status=status,
            started_at=_now(),
            finished_at=_now(),
            duration_ms=latency_ms,
            error_class=error_class,
        )
    )
    return invocation_id
