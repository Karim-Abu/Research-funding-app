"""Search Query Firewall approval service (Milestone 9J).

Runs the firewall, persists a **single-use** decision/approval record (never the raw
query — only its hash + the sanitized query + a category-only redaction summary), and
lets the web-research chokepoint consume an approved sanitized query exactly once.

Every decision writes a metadata-only ``CTRL.QUERY_FIREWALL`` ControlResult + AuditEvent.
Cross-workspace access is impossible: every read is workspace-scoped.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Project, SearchQueryApproval
from app.repositories import audit, controls
from app.security.data_class import DataClass, derive_data_class
from app.security.redaction import assert_no_raw_query
from app.security.search_query_firewall import FirewallResult, evaluate_query

CTRL_QUERY_FIREWALL = "CTRL.QUERY_FIREWALL"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalError(Exception):
    """Raised when an approval cannot be created/consumed. ``status`` maps to HTTP."""

    def __init__(self, code: str, detail: str, *, status: int = 422) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class PreviewOutcome:
    result: FirewallResult
    approval: SearchQueryApproval | None  # created only for require_human_approval


def _record_decision(
    db: Session,
    *,
    project: Project,
    actor_user_id: str,
    data_class: DataClass,
    result: FirewallResult,
    approval_id: str | None,
    raw_query: str,
) -> None:
    """Metadata-only control + audit. NEVER writes the raw query (only the hash)."""
    status = {
        "allow": "passed", "require_human_approval": "warning", "block": "blocked",
    }.get(result.decision, "blocked")
    control_detail = f"{data_class}:{result.decision}:risk{result.risk_score}"
    audit_detail = {
        "data_class": str(data_class),
        "decision": result.decision,
        "risk_score": result.risk_score,
        "detected_categories": result.detected_sensitive_categories,
        "raw_query_hash": result.raw_query_hash,
    }
    # Defensive no-raw-logging backstop (dev/test-fatal; no-op in production).
    assert_no_raw_query(control_detail, raw_query=raw_query)
    assert_no_raw_query(audit_detail, raw_query=raw_query)
    controls.record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.project_id,
        control_id=CTRL_QUERY_FIREWALL,
        status=status,
        detail=control_detail,
    )
    audit.record(
        db,
        workspace_id=project.workspace_id,
        actor_user_id=actor_user_id,
        action="search_query.firewall_decision",
        target_type="search_query_approval",
        target_id=approval_id,
        detail=audit_detail,
    )


def run_preview(
    db: Session,
    *,
    project: Project,
    actor_user_id: str,
    raw_query: str,
    intended_tool: str = "firecrawl",
    purpose: str | None = None,
    source_context_ids: list[str] | None = None,
) -> PreviewOutcome:
    """Screen a query. For ``require_human_approval`` persist a ``pending`` approval so
    the user can approve the sanitized query; for ``allow``/``block`` persist no approval
    (D0 allow needs none; block cannot proceed)."""
    data_class = derive_data_class(project.data_classification)
    result = evaluate_query(
        db,
        project_id=project.project_id,
        workspace_id=project.workspace_id,
        actor_user_id=actor_user_id,
        raw_query=raw_query,
        data_class=data_class,
        intended_tool=intended_tool,
        purpose=purpose,
        source_context_ids=source_context_ids,
    )

    approval: SearchQueryApproval | None = None
    if result.decision == "require_human_approval":
        approval = SearchQueryApproval(
            approval_id=str(uuid.uuid4()),
            project_id=project.project_id,
            workspace_id=project.workspace_id,
            actor_user_id=actor_user_id,
            intended_tool=intended_tool,
            purpose=purpose,
            data_class=str(data_class),
            raw_query_hash=result.raw_query_hash,
            sanitized_query=result.sanitized_query,
            risk_score=result.risk_score,
            decision=result.decision,
            reasons=list(result.reasons),
            redaction_summary=list(result.redaction_summary),
            status="pending",
        )
        db.add(approval)

    _record_decision(
        db, project=project, actor_user_id=actor_user_id, data_class=data_class,
        result=result, approval_id=approval.approval_id if approval else None,
        raw_query=raw_query,
    )
    return PreviewOutcome(result=result, approval=approval)


def get_scoped(
    db: Session, approval_id: str, workspace_id: str
) -> SearchQueryApproval | None:
    return db.scalar(
        select(SearchQueryApproval).where(
            SearchQueryApproval.approval_id == approval_id,
            SearchQueryApproval.workspace_id == workspace_id,
        )
    )


def decide(
    db: Session, *, approval: SearchQueryApproval, actor_user_id: str, approve: bool
) -> SearchQueryApproval:
    """Approve or reject a pending approval. Only ``pending`` may transition."""
    if approval.status != "pending":
        raise ApprovalError(
            "approval_not_pending",
            "Diese Freigabe kann nicht mehr geändert werden.",
            status=409,
        )
    approval.status = "approved" if approve else "rejected"
    approval.decided_at = _now()
    audit.record(
        db,
        workspace_id=approval.workspace_id,
        actor_user_id=actor_user_id,
        action="search_query.approval_decided",
        target_type="search_query_approval",
        target_id=approval.approval_id,
        detail={"status": approval.status, "raw_query_hash": approval.raw_query_hash},
    )
    return approval


def consume_for_task(
    db: Session,
    *,
    approval_id: str,
    workspace_id: str,
    project_id: str,
    raw_query_hash: str,
    research_task_id: str,
) -> str:
    """Validate + single-use-consume an approved sanitized query. Returns the sanitized
    query. Raises ``ApprovalError`` on any mismatch (changed query, wrong project, not
    approved, already used, rejected/expired)."""
    approval = get_scoped(db, approval_id, workspace_id)
    if approval is None or approval.project_id != project_id:
        raise ApprovalError("approval_not_found", "Freigabe nicht gefunden.", status=404)
    if approval.status == "used":
        raise ApprovalError(
            "approval_already_used", "Diese Freigabe wurde bereits verwendet.", status=409
        )
    if approval.status != "approved":
        raise ApprovalError(
            "approval_not_approved",
            "Für diese Suchanfrage liegt keine gültige Freigabe vor.",
            status=422,
        )
    if approval.raw_query_hash != raw_query_hash:
        # Changing the query invalidates the approval.
        approval.status = "expired"
        approval.decided_at = _now()
        raise ApprovalError(
            "approval_query_changed",
            "Die Suchanfrage wurde geändert; bitte erneut prüfen lassen.",
            status=409,
        )
    approval.status = "used"
    approval.used_by_research_task_id = research_task_id
    approval.decided_at = _now()
    return approval.sanitized_query
