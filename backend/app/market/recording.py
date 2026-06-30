"""Comparison-scoped control + audit recording (Milestone 9I-B).

ControlResults are recorded with the comparison id embedded in the detail (the
ControlResult table has no comparison column); AuditEvents target the comparison. No API
keys, raw provider payloads, model names or query secrets are ever written here.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories import audit, controls


def record_control(
    db: Session,
    *,
    workspace_id: str,
    project_id: str | None,
    comparison_id: str,
    control_id: str,
    status: str,
    detail: str | None = None,
) -> None:
    suffix = f"comparison={comparison_id}"
    full = f"{detail}; {suffix}" if detail else suffix
    controls.record(
        db, workspace_id=workspace_id, project_id=project_id,
        control_id=control_id, status=status, detail=full[:200],
    )


def record_audit(
    db: Session,
    *,
    workspace_id: str,
    actor_user_id: str | None,
    action: str,
    comparison_id: str,
    detail: dict | None = None,
) -> None:
    audit.record(
        db, workspace_id=workspace_id, actor_user_id=actor_user_id, action=action,
        target_type="market_comparison", target_id=comparison_id, detail=detail,
    )
