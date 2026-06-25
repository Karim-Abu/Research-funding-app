"""Capabilities router — GET /capabilities."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config.settings import Settings
from app.contracts.capabilities import Capabilities
from app.security.deps import require_session, settings_dep

router = APIRouter(tags=["Infrastructure"])


@router.get("/capabilities", response_model=Capabilities)
def get_capabilities(
    _: object = Depends(require_session),
    settings: Settings = Depends(settings_dep),
) -> Capabilities:
    # Truthful feature flags — only fully-implemented slices are advertised.
    # Milestone 4 activates the deterministic formal-eligibility precheck:
    # partner management + run + live requirement assessments. Semantic
    # assessment, evidence, drafting, review and export remain unavailable.
    features = {
        "projects": True,
        "sources": True,
        "source_parsing": True,
        "url_import": settings.url_import_enabled,
        "partners": True,
        "runs": True,
        "requirements": True,
        # Milestone 5: deterministic evidence baseline (no AI/cloud).
        "evidence": True,
        # Milestone 6: deterministic template drafts + versioned field workspace.
        "drafts": True,
        # Milestone 7: deterministic review, recheck and approval (no AI/cloud).
        "review": True,
        # Milestone 8: deterministic DOCX/Markdown/technical-evidence exports.
        "export": True,
        "web_research": False,
    }
    return Capabilities(
        api_version=settings.api_version,
        polling_interval_seconds=settings.polling_interval_seconds,
        max_upload_bytes=settings.max_upload_bytes,
        supported_source_types=settings.supported_source_types,
        features=features,
    )
