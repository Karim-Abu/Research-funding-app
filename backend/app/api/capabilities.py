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
        # Milestone 9I-A: public web research. Truthful — true only when enabled AND a
        # provider (real Firecrawl or the dedicated web fake) is configured. url_import
        # stays false: web import is an internal Research path, not free-form URL import.
        "web_research": settings.web_research_enabled
        and (settings.web_research_fake_provider or bool(settings.firecrawl_api_key)),
        # Milestone 9I-B: market/competitor comparison (beta-internal) — available with
        # web research (it is built from imported public sources).
        "market_comparison": settings.web_research_enabled
        and (settings.web_research_fake_provider or bool(settings.firecrawl_api_key)),
        # Milestone 9K: deterministic MAS reliability & value assurance (beta-internal) —
        # available whenever the review layer is (no provider dependency).
        "reliability": True,
        # Slice 3 (E2-A): the Innolink copy view logs a server-side CopyEvent
        # per copy. False → the UI skips the call (endpoint stays active).
        "copy_events": settings.copy_events_enabled,
    }
    return Capabilities(
        api_version=settings.api_version,
        polling_interval_seconds=settings.polling_interval_seconds,
        max_upload_bytes=settings.max_upload_bytes,
        supported_source_types=settings.supported_source_types,
        features=features,
    )
