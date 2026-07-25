"""Capabilities router — GET /capabilities."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.registry import get_agent_registry
from app.config.settings import Settings
from app.contracts.capabilities import Capabilities, FeatureReadiness
from app.security.deps import require_session, settings_dep
from app.db.session import get_db

router = APIRouter(tags=["Infrastructure"])


def _field_suggestion_readiness(
    db: Session | None, settings: Settings
) -> FeatureReadiness:
    from app.evaluation.preflight import live_fake_conflict, route_readiness

    if live_fake_conflict(settings):
        return FeatureReadiness(
            status="error", available=False,
            reason_code="live_fake_conflict", retryable=False,
        )
    if settings.ai_eval_mode != "real":
        if settings.agent_fake_provider:
            return FeatureReadiness(
                status="fake", available=True, reason_code="demo_only"
            )
        return FeatureReadiness(
            status="disabled", available=False,
            reason_code="live_eval_mode_disabled",
        )
    registry = get_agent_registry()
    role = (registry.role_routes or {}).get("A2_INNOSUISSE_PROPOSAL_WRITER")
    if role is None:
        return FeatureReadiness(
            status="not_configured", available=False,
            reason_code="live_route_not_configured",
        )
    assessments = [
        route_readiness(db, route_key, settings=settings, registry=registry)
        for route_key in (role.primary, role.fallback)
        if route_key
    ]
    for status in (
        "ready", "degraded", "error", "configured_unverified",
        "not_configured", "disabled",
    ):
        selected = next((item for item in assessments if item.status == status), None)
        if selected is not None:
            return FeatureReadiness(
                status=selected.status,
                available=selected.status == "ready",
                reason_code=selected.reason_code,
                retryable=selected.retryable,
            )
    return FeatureReadiness(
        status="not_configured", available=False,
        reason_code="live_route_not_configured",
    )


@router.get("/capabilities", response_model=Capabilities)
def get_capabilities(
    _: object = Depends(require_session),
    settings: Settings = Depends(settings_dep),
    db: Session | None = Depends(get_db),
) -> Capabilities:
    # Lazy, cost-bounded: while the app is in use, keep the live preflight fresh
    # in the background so KI/Webrecherche don't silently expire (TTL). Non-blocking,
    # fail-closed — the refreshed state is reflected on the next capabilities read.
    from app.evaluation.auto_preflight import maybe_refresh
    maybe_refresh(db, settings)
    from app.evaluation.preflight import firecrawl_readiness
    web_state = firecrawl_readiness(db, settings)
    web_readiness = FeatureReadiness(
        status=web_state.status,
        available=web_state.status in {"ready", "fake"},
        reason_code=web_state.reason_code,
        retryable=web_state.retryable,
    )
    field_readiness = _field_suggestion_readiness(db, settings)
    web_research_available = web_readiness.available
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
        feature_readiness={
            "web_research": web_readiness,
            "market_comparison": web_readiness,
            "field_suggestions": field_readiness,
        },
        generation_mode=generation_mode,
        generation_unavailable_reason=unavailable_reason,
        ai_available=ai_available,
        ai_unavailable_reason=None if ai_available else (
            unavailable_reason or "live_ai_not_enabled"
        ),
    )
