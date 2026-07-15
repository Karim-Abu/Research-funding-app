"""AnalysisRun persistence (workspace+project scoped) + ORM→contract mapping."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.run import AnalysisRun as AnalysisRunSchema
from app.contracts.run import IssueCounts
from app.db.models import AnalysisRun
from app.runs.constants import ACTIVE_RUN_STATUSES


def get_scoped(db: Session, run_id: str, workspace_id: str) -> AnalysisRun | None:
    return db.scalar(
        select(AnalysisRun).where(
            AnalysisRun.run_id == run_id,
            AnalysisRun.workspace_id == workspace_id,
        )
    )


def list_by_project(
    db: Session, project_id: str, workspace_id: str
) -> list[AnalysisRun]:
    return list(
        db.scalars(
            select(AnalysisRun)
            .where(
                AnalysisRun.project_id == project_id,
                AnalysisRun.workspace_id == workspace_id,
            )
            .order_by(AnalysisRun.created_at.desc())
        )
    )


def active_run(db: Session, project_id: str) -> AnalysisRun | None:
    return db.scalar(
        select(AnalysisRun).where(
            AnalysisRun.project_id == project_id,
            AnalysisRun.status.in_(ACTIVE_RUN_STATUSES),
        )
    )


def to_contract(run: AnalysisRun) -> AnalysisRunSchema:
    return AnalysisRunSchema(
        run_id=run.run_id,
        project_id=run.project_id,
        status=run.status,
        current_stage=run.current_stage,
        progress_percent=run.progress_percent,
        processing_mode=run.processing_mode,
        created_at=run.created_at,
        recheck_required=run.recheck_required,
        semantic_findings_stale=run.semantic_findings_stale,
        started_at=run.started_at,
        ended_at=run.ended_at,
        estimated_cost_chf=run.estimated_cost_chf,
        actual_cost_chf=run.actual_cost_chf,
        stop_reason=run.stop_reason,
        issue_counts=IssueCounts(blocker=0, warning=0, info=0),
        review_package_version=run.review_package_version,
        approval_scope_hash=run.approval_scope_hash,
        live_execution_status=run.live_execution_status,
        live_status_reason=run.live_status_reason,
    )
