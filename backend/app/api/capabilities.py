"""Capabilities router — GET /capabilities."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.contracts.capabilities import Capabilities
from app.security.deps import require_session, settings_dep
from app.db.session import get_db

router = APIRouter(tags=["Infrastructure"])


@router.get("/capabilities", response_model=Capabilities)
def get_capabilities(
    _: object = Depends(require_session),
    settings: Settings = Depends(settings_dep),
    db: Session | None = Depends(get_db),
) -> Capabilities:
    from app.evaluation.preflight import firecrawl_preflight_reason
    web_research_available = settings.web_research_enabled and (
        settings.web_research_fake_provider
        or firecrawl_preflight_reason(db, settings) is None
    )
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
        "web_research": web_research_available,
        # Milestone 9I-B: market/competitor comparison (beta-internal) — available with
        # web research (it is built from imported public sources).
        "market_comparison": web_research_available,
        # Milestone 9K: deterministic MAS reliability & value assurance (beta-internal) —
        # available whenever the review layer is (no provider dependency).
        "reliability": True,
        # Slice 3 (E2-A): the Innolink copy view logs a server-side CopyEvent
        # per copy. False → the UI skips the call (endpoint stays active).
        "copy_events": settings.copy_events_enabled,
    }
    # Ebene E: Live-ABSICHT (ai_eval_mode=real) gewinnt. Ist Live konfiguriert,
    # aber kein Provider-Schlüssel vorhanden, ist der Status ausdrücklich
    # ``live_unavailable`` — nie ein stiller Abstieg auf den Demo-Generator.
    from app.evaluation.preflight import generation_mode_status
    generation_mode, unavailable_reason = generation_mode_status(db, settings)
    ai_available = generation_mode == "real_eval"
    return Capabilities(
        api_version=settings.api_version,
        polling_interval_seconds=settings.polling_interval_seconds,
        max_upload_bytes=settings.max_upload_bytes,
        supported_source_types=settings.supported_source_types,
        features=features,
        generation_mode=generation_mode,
        generation_unavailable_reason=unavailable_reason,
        ai_available=ai_available,
        ai_unavailable_reason=None if ai_available else (
            unavailable_reason or "live_ai_not_enabled"
        ),
    )
