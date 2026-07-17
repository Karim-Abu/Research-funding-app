"""Lead-admin live-system status and explicit synthetic preflight."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.registry import get_agent_registry
from app.config.settings import Settings
from app.contracts.live_system import (
    LiveFirecrawlStatus,
    LivePreflightResponse,
    LiveRouteStatus,
    LiveSystemStatus,
)
from app.db.session import get_db
from app.evaluation.preflight import (
    firecrawl_mode,
    firecrawl_preflight_reason,
    generation_mode_status,
    latest_route_preflight,
    persist_route_preflight,
    preflight_firecrawl,
    preflight_route,
    route_configuration_reason,
    route_preflight_reason,
)
from app.evaluation.pricing import resolve_cost
from app.security.deps import (
    AuthContext, require_roles, require_unsafe_guards, settings_dep,
)

router = APIRouter(prefix="/admin", tags=["Administration"])
_CORE_ROLES = {
    "A1_FACT_EVIDENCE_ANALYST",
    "A2_INNOSUISSE_PROPOSAL_WRITER",
    "A3_INNOSUISSE_CRITICAL_REVIEWER",
    "RESEARCH_EVIDENCE_SYNTHESIZER",
}


def _status(db: Session, settings: Settings) -> LiveSystemStatus:
    registry = get_agent_registry()
    rows: list[LiveRouteStatus] = []
    seen: set[tuple[str, str]] = set()
    for role_id, role in sorted((registry.role_routes or {}).items()):
        if role.execution_kind != "model_gateway" or role_id not in _CORE_ROLES:
            continue
        for route_key in (role.primary, role.fallback, role.comparison):
            if not route_key or (role_id, route_key) in seen:
                continue
            seen.add((role_id, route_key))
            route = registry.route(route_key)
            requested = route.requested_model_id(settings)
            latest = latest_route_preflight(db, route_key)
            evaluation_disabled = route.evaluation_only and not settings.agent_quality_ceiling_enabled
            configuration_reason = route_configuration_reason(
                route_key, settings=settings, registry=registry
            )
            readiness_reason = route_preflight_reason(
                db, route_key, settings=settings, registry=registry
            )
            configured = configuration_reason is None
            cost = resolve_cost(
                provider=route.provider, model_id=requested,
                input_tokens=0, output_tokens=0,
                settings=settings,
            ) if requested else None
            effective_preflight_status = (
                "pass" if readiness_reason is None
                else "not_run" if latest is None
                else "fail"
            )
            rows.append(LiveRouteStatus(
                role_id=role_id, route_key=route_key, route_alias=route.alias,
                provider=route.provider, requested_model_id=requested,
                actual_model_id=latest.actual_model_id if latest else None,
                configuration_status=(
                    "evaluation_disabled" if evaluation_disabled
                    else "configured" if configured else "not_configured"
                ),
                preflight_status=effective_preflight_status,
                checked_at=latest.checked_at if latest else None,
                expires_at=latest.expires_at if latest else None,
                latency_ms=latest.latency_ms if latest else None,
                error_class=readiness_reason or (
                    latest.error_class if latest else None
                ),
                capabilities=route.capabilities or {},
                cost_status=cost.cost_status if cost else "unknown_price",
                readiness_reason=readiness_reason,
                checks=list(latest.checks_json or []) if latest else [],
            ))
    core_primary = [
        row for row in rows
        if row.role_id in _CORE_ROLES
        and (registry.role_routes or {})[row.role_id].primary == row.route_key
    ]
    generation_mode, generation_reason = generation_mode_status(
        db, settings, registry=registry
    )
    passed = sum(row.preflight_status == "pass" for row in core_primary)
    overall = (
        "available" if generation_mode == "real_eval"
        else "degraded"
        if settings.ai_eval_mode == "real" and passed
        else "unavailable"
    )
    firecrawl_latest = latest_route_preflight(db, "firecrawl")
    firecrawl_reason = firecrawl_preflight_reason(db, settings)
    firecrawl_status = (
        "pass" if firecrawl_reason is None
        else "not_run" if firecrawl_latest is None
        else "fail"
    )
    return LiveSystemStatus(
        overall_status=overall,
        registry_version=settings.agent_registry_version,
        generation_mode=generation_mode,
        generation_unavailable_reason=generation_reason,
        routes=rows,
        firecrawl=LiveFirecrawlStatus(
            mode=firecrawl_mode(settings),
            available=(
                firecrawl_mode(settings) == "fake"
                or firecrawl_reason is None
            ),
            preflight_status=firecrawl_status,
            checked_at=firecrawl_latest.checked_at if firecrawl_latest else None,
            expires_at=firecrawl_latest.expires_at if firecrawl_latest else None,
            latency_ms=firecrawl_latest.latency_ms if firecrawl_latest else None,
            error_class=firecrawl_reason or (
                firecrawl_latest.error_class if firecrawl_latest else None
            ),
            checks=list(firecrawl_latest.checks_json or [])
            if firecrawl_latest else [],
        ),
    )


@router.get("/live-system-status", response_model=LiveSystemStatus)
def get_live_system_status(
    _: AuthContext = Depends(require_roles("lead_admin")),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> LiveSystemStatus:
    return _status(db, settings)


@router.post("/live-system-status/preflight", response_model=LivePreflightResponse)
def run_live_system_preflight(
    context: AuthContext = Depends(require_unsafe_guards),
    _: AuthContext = Depends(require_roles("lead_admin")),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> LivePreflightResponse:
    registry = get_agent_registry()
    route_keys: list[str] = []
    for role_id in sorted(_CORE_ROLES):
        role = (registry.role_routes or {}).get(role_id)
        if role is None:
            continue
        candidates = [role.primary, role.fallback]
        if settings.agent_quality_ceiling_enabled:
            candidates.append(role.comparison)
        for route_key in candidates:
            if route_key and route_key not in route_keys:
                route_keys.append(route_key)
    for route_key in route_keys:
        route = registry.route(route_key)
        if route.evaluation_only and not settings.agent_quality_ceiling_enabled:
            continue
        result = preflight_route(
            route_key, settings=settings, registry=registry, execute_live=True
        )
        persist_route_preflight(
            db, result, triggered_by=context.user.id, settings=settings
        )
    firecrawl = preflight_firecrawl(settings=settings, execute_live=True)
    persist_route_preflight(
        db, firecrawl, triggered_by=context.user.id, settings=settings
    )
    db.commit()
    return LivePreflightResponse(status=_status(db, settings))
