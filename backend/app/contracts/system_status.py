"""Small, user-facing system status without route or model internals."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


SystemServiceState = Literal["available", "attention", "unavailable"]


class SystemServiceStatus(BaseModel):
    id: Literal["ai", "web"]
    label: str
    state: SystemServiceState
    message: str
    next_step: str
    checked_at: datetime | None = None


class SystemStatusView(BaseModel):
    services: list[SystemServiceStatus]
    can_run_connection_check: bool
