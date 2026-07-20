"""Project schemas — ``ProjectCreate``, ``ProjectPatch``, ``Project``, ``ProjectList``.

``Project`` is ``allOf(ProjectCreate, …)`` in the contract, modelled here by
inheritance so the created fields stay in sync.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.classification import DataClassification


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    innovation_field: str | None = None
    funding_instrument_profile_id: str
    data_classification: DataClassification
    budget_framework_chf: float | None = Field(default=None, ge=0)


class ProjectPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    title_en: str | None = Field(default=None, min_length=1)
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = Field(default=None, min_length=1)
    innovation_field: str | None = None
    budget_framework_chf: float | None = Field(default=None, ge=0)
    # Structured budget inputs (Slice 1, additive).
    direct_total_project_costs_excluding_overhead: float | None = Field(
        default=None, ge=0
    )
    implementation_own_contribution: float | None = Field(default=None, ge=0)
    cash_contribution: float | None = Field(default=None, ge=0)
    total_requested_funding: float | None = Field(default=None, ge=0)
    total_requested_funding_including_overhead: float | None = Field(
        default=None, ge=0
    )
    budget_exception_basis: str | None = None
    # Compatibility input member only. Presence is rejected by the central
    # mutation service with the stable ``duration_read_only`` problem code.
    duration_months: int | None = None
    # Status transitions (e.g. archivieren) — same enum as the Project contract.
    status: Literal["draft", "active", "archived"] | None = None


class WorkflowSummary(BaseModel):
    bearbeitungsstand_percent: int = Field(ge=0, le=100)
    current_step: int = Field(ge=1, le=8)
    current_step_label: str | None = None
    next_action: Literal[
        "upload_sources",
        "start_analysis",
        "review_analysis",
        "continue_draft",
        "approve_review",
        "create_export",
        "resume_analysis",
        "view_progress",
    ]
    warning_badge: Literal["run_stopped"] | None = None
    latest_run_id: str | None = None


class Project(ProjectCreate):
    project_id: str
    workspace_id: str
    title_en: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    # Structured budget inputs (Slice 1, additive; set via ProjectPatch).
    direct_total_project_costs_excluding_overhead: float | None = None
    implementation_own_contribution: float | None = None
    cash_contribution: float | None = None
    total_requested_funding: float | None = None
    total_requested_funding_including_overhead: float | None = None
    budget_exception_basis: str | None = None
    duration_months: int | None = None
    duration_status: Literal["derived", "not_derivable", "review_required"]
    duration_reason_code: Literal[
        "duration_derived",
        "duration_dates_missing",
        "duration_boundary_conflict",
    ]
    status: Literal["draft", "active", "archived"]
    created_at: datetime
    updated_at: datetime
    active_run_id: str | None = None
    workflow_summary: WorkflowSummary | None = None


class ProjectList(BaseModel):
    items: list[Project]
    next_cursor: str | None = None
