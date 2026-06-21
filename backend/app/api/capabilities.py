"""Capabilities router — GET /capabilities."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config.settings import Settings
from app.contracts.capabilities import Capabilities
from app.security.deps import require_session, settings_dep

router = APIRouter(tags=["Infrastructure"])

# Milestone 1 feature flags — only the session/projects slice is live.
_FEATURES = {
    "projects": True,
    "sources": False,
    "runs": False,
    "review": False,
    "export": False,
    "web_research": False,
}


@router.get("/capabilities", response_model=Capabilities)
def get_capabilities(
    _: object = Depends(require_session),
    settings: Settings = Depends(settings_dep),
) -> Capabilities:
    return Capabilities(
        api_version=settings.api_version,
        polling_interval_seconds=settings.polling_interval_seconds,
        max_upload_bytes=settings.max_upload_bytes,
        supported_source_types=settings.supported_source_types,
        features=_FEATURES,
    )
