"""Lead-admin live provider status; metadata only."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

LiveReadinessStatus = Literal[
    "disabled",
    "fake",
    "not_configured",
    "configured_unverified",
    "ready",
    "degraded",
    "error",
]


class LiveRouteStatus(BaseModel):
    role_id: str
    route_key: str
    route_alias: str
    provider: str
    requested_model_id: str | None = None
    actual_model_id: str | None = None
    configuration_status: Literal["configured", "not_configured", "evaluation_disabled"]
    readiness_status: LiveReadinessStatus
    reason_code: str | None = None
    retryable: bool = False
    preflight_status: Literal["pass", "fail", "not_run"]
    checked_at: datetime | None = None
    expires_at: datetime | None = None
    latency_ms: int | None = None
    error_class: str | None = None
    capabilities: dict[str, Any] = Field(default_factory=dict)
    cost_status: str
    readiness_reason: str | None = None
    checks: list[dict[str, Any]] = Field(default_factory=list)


class LiveFirecrawlStatus(BaseModel):
    mode: Literal["disabled", "fake", "live", "not_configured"]
    available: bool
    readiness_status: LiveReadinessStatus
    reason_code: str | None = None
    retryable: bool = False
    preflight_status: Literal["pass", "fail", "not_run"]
    checked_at: datetime | None = None
    expires_at: datetime | None = None
    latency_ms: int | None = None
    error_class: str | None = None
    checks: list[dict[str, Any]] = Field(default_factory=list)


class LiveSystemStatus(BaseModel):
    overall_status: Literal["available", "degraded", "unavailable"]
    registry_version: str
    generation_mode: Literal[
        "unavailable", "fake_demo", "real_eval", "live_unavailable"
    ]
    generation_unavailable_reason: str | None = None
    routes: list[LiveRouteStatus]
    firecrawl: LiveFirecrawlStatus


class LivePreflightResponse(BaseModel):
    status: LiveSystemStatus

