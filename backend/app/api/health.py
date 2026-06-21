"""Health router — GET /health (public)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config.settings import Settings
from app.contracts.health import Health
from app.security.deps import settings_dep

router = APIRouter(tags=["Infrastructure"])


@router.get("/health", response_model=Health)
def get_health(settings: Settings = Depends(settings_dep)) -> Health:
    return Health(
        status="ok",
        api_version=settings.api_version,
        policy_version=settings.policy_version,
        agent_registry_version=settings.agent_registry_version,
        rule_registry_version=settings.rule_registry_version,
        tool_registry_version=settings.tool_registry_version,
    )
