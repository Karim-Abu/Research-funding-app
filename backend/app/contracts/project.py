"""Project schemas — ``ProjectCreate``, ``ProjectPatch``, ``Project``, ``ProjectList``.

``Project`` is ``allOf(ProjectCreate, …)`` in the contract, modelled here by
inheritance so the created fields stay in sync.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

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
    description: str | None = Field(default=None, min_length=1)
    innovation_field: str | None = None
    budget_framework_chf: float | None = Field(default=None, ge=0)


class Project(ProjectCreate):
    project_id: str
    workspace_id: str
    status: Literal["draft", "active", "archived"]
    created_at: datetime
    updated_at: datetime
    active_run_id: str | None = None
    # WorkflowSummary is optional in the contract; null in Milestone 1.
    workflow_summary: dict[str, Any] | None = None


class ProjectList(BaseModel):
    items: list[Project]
    next_cursor: str | None = None
