"""Deterministic Project.workflow_summary read model."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contracts.project import WorkflowSummary
from app.db.models import (
    AnalysisRun,
    DraftVersion,
    OpenIssue,
    PortalFieldDraft,
    RequirementAssessment,
    SourceDocument,
)
from app.runs.constants import ACTIVE_RUN_STATUSES, TERMINAL_RUN_STATUSES

WORKFLOW_SUMMARY_VERSION = "workflow-summary-v1"

STEP_LABELS = {
    1: "Intake",
    2: "Quellen",
    3: "Anforderungen",
    4: "Evidenz",
    5: "Entwurf",
    6: "Review",
    7: "Abschluss",
    8: "Export",
}

STAGE_TO_STEP = {
    "initialize": 2,
    "validate_source_snapshot": 2,
    "extract_facts_and_map_evidence": 4,
    "verify_evidence": 4,
    "evaluate_requirements_and_rules": 3,
    "draft_fields": 5,
    "create_template_drafts": 5,
    "finalize_run": 5,
}


def _summary(
    *,
    percent: int,
    step: int,
    next_action: str,
    warning_badge: str | None = None,
    latest_run_id: str | None = None,
) -> WorkflowSummary:
    return WorkflowSummary(
        bearbeitungsstand_percent=max(0, min(100, percent)),
        current_step=step,
        current_step_label=STEP_LABELS[step],
        next_action=next_action,  # type: ignore[arg-type]
        warning_badge=warning_badge,  # type: ignore[arg-type]
        latest_run_id=latest_run_id,
    )


def calculate(db: Session, project_id: str, workspace_id: str) -> WorkflowSummary:
    processed_sources = db.scalar(
        select(func.count(SourceDocument.source_id)).where(
            SourceDocument.project_id == project_id,
            SourceDocument.workspace_id == workspace_id,
            SourceDocument.status == "processed",
        )
    ) or 0
    if processed_sources == 0:
        return _summary(percent=12, step=2, next_action="upload_sources")

    latest_run = db.scalar(
        select(AnalysisRun)
        .where(
            AnalysisRun.project_id == project_id,
            AnalysisRun.workspace_id == workspace_id,
        )
        .order_by(AnalysisRun.created_at.desc())
    )
    if latest_run is None:
        return _summary(percent=25, step=2, next_action="start_analysis")

    if latest_run.status in ACTIVE_RUN_STATUSES:
        return _summary(
            percent=latest_run.progress_percent,
            step=STAGE_TO_STEP.get(latest_run.current_stage, 2),
            next_action="view_progress",
            latest_run_id=latest_run.run_id,
        )

    if latest_run.status in TERMINAL_RUN_STATUSES and latest_run.status != "completed":
        return _summary(
            percent=latest_run.progress_percent,
            step=STAGE_TO_STEP.get(latest_run.current_stage, 2),
            next_action="resume_analysis",
            warning_badge="run_stopped",
            latest_run_id=latest_run.run_id,
        )

    unresolved_requirements = db.scalar(
        select(func.count(RequirementAssessment.assessment_id)).where(
            RequirementAssessment.run_id == latest_run.run_id,
            RequirementAssessment.status.in_(("blocked", "open", "needs_input")),
        )
    ) or 0
    blocker_issues = db.scalar(
        select(func.count(OpenIssue.issue_id)).where(
            OpenIssue.run_id == latest_run.run_id,
            OpenIssue.status == "open",
            OpenIssue.severity == "blocker",
        )
    ) or 0
    user_drafts = db.scalar(
        select(func.count(DraftVersion.draft_version_id))
        .join(PortalFieldDraft, DraftVersion.draft_id == PortalFieldDraft.draft_id)
        .where(
            PortalFieldDraft.run_id == latest_run.run_id,
            DraftVersion.created_by == "user",
        )
    ) or 0
    draft_issues = db.scalar(
        select(func.coalesce(func.sum(PortalFieldDraft.open_issue_count), 0)).where(
            PortalFieldDraft.run_id == latest_run.run_id
        )
    ) or 0

    if user_drafts:
        return _summary(
            percent=72 if draft_issues else 78,
            step=5,
            next_action="continue_draft",
            latest_run_id=latest_run.run_id,
        )

    if blocker_issues or unresolved_requirements:
        return _summary(
            percent=45,
            step=3,
            next_action="review_analysis",
            latest_run_id=latest_run.run_id,
        )

    if draft_issues:
        return _summary(
            percent=72,
            step=5,
            next_action="continue_draft",
            latest_run_id=latest_run.run_id,
        )

    return _summary(
        percent=62,
        step=3,
        next_action="review_analysis",
        latest_run_id=latest_run.run_id,
    )
