"""Health schema."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    api_version: str
    policy_version: str
    agent_registry_version: str
    rule_registry_version: str | None = None
    tool_registry_version: str | None = None
