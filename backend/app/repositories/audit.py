"""Append-only audit events for mutating actions."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models import AuditEvent


def record(
    db: Session,
    *,
    workspace_id: str,
    actor_user_id: str | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )
    db.add(event)
    db.flush()
    return event
