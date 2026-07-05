"""Project persistence (always workspace-scoped) + ORM→contract mapping."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.project import Project as ProjectSchema
from app.contracts.project import ProjectCreate, ProjectPatch
from app.db.models import Project
from app.workflow_summary import calculate as calculate_workflow_summary


def create(
    db: Session,
    *,
    workspace_id: str,
    created_by: str,
    data: ProjectCreate,
    project_id: str | None = None,
) -> Project:
    project = Project(
        project_id=project_id or str(uuid.uuid4()),
        workspace_id=workspace_id,
        title=data.title,
        description=data.description,
        innovation_field=data.innovation_field,
        funding_instrument_profile_id=data.funding_instrument_profile_id,
        data_classification=data.data_classification.model_dump(),
        budget_framework_chf=data.budget_framework_chf,
        status="draft",
        created_by=created_by,
    )
    db.add(project)
    db.flush()
    return project


def list_by_workspace(db: Session, workspace_id: str) -> list[Project]:
    return list(
        db.scalars(
            select(Project)
            .where(Project.workspace_id == workspace_id)
            .order_by(Project.created_at.desc())
        )
    )


def get_scoped(
    db: Session, project_id: str, workspace_id: str
) -> Project | None:
    return db.scalar(
        select(Project).where(
            Project.project_id == project_id,
            Project.workspace_id == workspace_id,
        )
    )


_PATCHABLE_FIELDS = (
    "title",
    "description",
    "innovation_field",
    "budget_framework_chf",
    "direct_total_project_costs_excluding_overhead",
    "implementation_own_contribution",
    "cash_contribution",
    "total_requested_funding",
    "budget_exception_basis",
    "duration_months",
)


def apply_patch(db: Session, project: Project, patch: ProjectPatch) -> Project:
    data = patch.model_dump(exclude_unset=True)
    for field in _PATCHABLE_FIELDS:
        if field in data:
            setattr(project, field, data[field])
    db.add(project)
    db.flush()
    return project


def to_contract(db: Session, project: Project) -> ProjectSchema:
    return ProjectSchema(
        project_id=project.project_id,
        workspace_id=project.workspace_id,
        title=project.title,
        description=project.description,
        innovation_field=project.innovation_field,
        funding_instrument_profile_id=project.funding_instrument_profile_id,
        data_classification=project.data_classification,
        budget_framework_chf=project.budget_framework_chf,
        direct_total_project_costs_excluding_overhead=(
            project.direct_total_project_costs_excluding_overhead
        ),
        implementation_own_contribution=project.implementation_own_contribution,
        cash_contribution=project.cash_contribution,
        total_requested_funding=project.total_requested_funding,
        budget_exception_basis=project.budget_exception_basis,
        duration_months=project.duration_months,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
        active_run_id=project.active_run_id,
        workflow_summary=calculate_workflow_summary(
            db, project.project_id, project.workspace_id
        ),
    )
