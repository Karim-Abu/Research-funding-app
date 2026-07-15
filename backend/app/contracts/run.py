"""Run / AsyncOperation schemas (exact openapi-v1_1.yaml shapes)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.problem import Problem

RunStatus = Literal[
    "created",
    "running",
    "paused_for_review",
    "completed",
    "stopped",
    "failed",
    "cancelled",
]
RunStage = Literal[
    "initialize",
    "validate_source_snapshot",
    "extract_facts_and_map_evidence",
    "verify_evidence",
    "evaluate_requirements_and_rules",
    "draft_fields",
    "create_template_drafts",
    "critic_review",
    "aggregate_review",
    "human_review",
    "targeted_recheck",
    "finalize_run",
]
ProcessingMode = Literal["deterministic_only", "cloud_assisted", "local_only"]
OperationStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class RunSettings(BaseModel):
    processing_mode: ProcessingMode
    max_cost_chf: float = Field(ge=0)
    max_llm_calls: int = Field(ge=0)
    max_web_calls: int = Field(ge=0)
    source_version_ids: list[str] | None = None
    internal_cloud_confirmation_id: str | None = None


class RunCreate(BaseModel):
    settings: RunSettings


class IssueCounts(BaseModel):
    blocker: int = 0
    warning: int = 0
    info: int = 0


class AnalysisRun(BaseModel):
    run_id: str
    project_id: str
    status: RunStatus
    current_stage: RunStage
    progress_percent: int = Field(ge=0, le=100)
    processing_mode: ProcessingMode
    created_at: datetime
    recheck_required: bool
    semantic_findings_stale: bool
    started_at: datetime | None = None
    ended_at: datetime | None = None
    estimated_cost_chf: float | None = None
    actual_cost_chf: float | None = None
    stop_reason: str | None = None
    issue_counts: IssueCounts | None = None
    review_package_version: str | None = None
    approval_scope_hash: str | None = None
    live_execution_status: Literal[
        "completed_live", "partial_live", "live_unavailable",
        "blocked_by_policy", "failed_live",
    ] | None = None
    live_status_reason: str | None = None


class RunList(BaseModel):
    items: list[AnalysisRun]
    next_cursor: str | None = None


class AsyncAccepted(BaseModel):
    operation_id: str
    resource_type: str
    resource_id: str
    status: Literal["queued", "running"]
    poll_url: str


class AsyncOperation(BaseModel):
    operation_id: str
    resource_type: str
    resource_id: str
    status: OperationStatus
    created_at: datetime
    updated_at: datetime | None = None
    progress_percent: int | None = None
    result: dict[str, Any] | None = None
    error: Problem | None = None


class ResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str
    expected_checkpoint_version: str
    expected_review_package_version: str
