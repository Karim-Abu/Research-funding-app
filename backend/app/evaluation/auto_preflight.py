"""Lazy, cost-bounded auto-refresh of the live provider preflight.

When the app is in use (a ``/capabilities`` read happens) and the live preflight
is expired, near expiry, or never run, this kicks ONE background refresh so live
features (KI suggestions + web research) become available again without a manual
Live-System-Status trigger.

Design guarantees:
- Fail-closed: a failed refresh persists the real failure; readiness is never faked.
- Cost-bounded: only fires while a user is active (a capabilities read), guarded by
  an in-flight lock and a per-process cooldown, so it never burns provider budget
  unattended and never stampedes on repeated polls.
- Non-blocking: the capabilities response returns immediately; the refreshed state
  is picked up by the next poll.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.agents.registry import AgentRegistry, get_agent_registry
from app.config.settings import Settings
from app.db.session import SessionLocal
from app.evaluation.preflight import (
    CORE_LIVE_ROLE_IDS,
    latest_route_preflight,
    live_fake_conflict,
    persist_route_preflight,
    preflight_firecrawl,
    preflight_route,
)

logger = logging.getLogger("app.evaluation.auto_preflight")

_TRIGGERED_BY = "auto-refresh"
# Anti-Stampede: nach einem Versuch (auch einem fehlgeschlagenen) mindestens so
# lange warten, bevor ein weiterer Auto-Versuch startet.
_MIN_INTERVAL_SECONDS = 300

_lock = threading.Lock()
_state: dict = {"running": False, "last_attempt": None}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _core_route_keys(settings: Settings, registry: AgentRegistry) -> list[str]:
    keys: list[str] = []
    for role_id in CORE_LIVE_ROLE_IDS:
        role = (registry.role_routes or {}).get(role_id)
        if role is None:
            continue
        candidates = [role.primary, role.fallback]
        if settings.agent_quality_ceiling_enabled:
            candidates.append(role.comparison)
        for key in candidates:
            if key and key not in keys:
                keys.append(key)
    return keys


def _required_route_keys(settings: Settings, registry: AgentRegistry) -> list[str]:
    keys = _core_route_keys(settings, registry)
    if settings.web_research_enabled and not settings.web_research_fake_provider:
        keys.append("firecrawl")
    return keys


def _expires(row) -> datetime:
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp


def refresh_needed(
    db: Session, settings: Settings, registry: AgentRegistry
) -> bool:
    """True if any required live route lacks a preflight valid beyond the margin."""
    threshold = _now() + timedelta(
        seconds=settings.provider_preflight_refresh_margin_seconds
    )
    for route_key in _required_route_keys(settings, registry):
        row = latest_route_preflight(db, route_key)
        if row is None or _expires(row) <= threshold:
            return True
    return False


def maybe_refresh(
    db: Session | None,
    settings: Settings,
    *,
    registry: AgentRegistry | None = None,
    runner=None,
) -> bool:
    """Kick a one-off background preflight refresh if warranted. Non-blocking.

    Returns True iff a refresh was started. Safe to call on every capabilities
    read: guarded by mode/flag/conflict, an in-flight lock, a cooldown, and the
    actual expiry check.
    """
    if settings.ai_eval_mode != "real" or not settings.provider_preflight_auto_refresh:
        return False
    if live_fake_conflict(settings):
        return False
    if db is None or not hasattr(db, "scalar"):
        return False
    registry = registry or get_agent_registry()
    now = _now()
    with _lock:
        if _state["running"]:
            return False
        last = _state["last_attempt"]
        if last is not None and (now - last).total_seconds() < _MIN_INTERVAL_SECONDS:
            return False
        if not refresh_needed(db, settings, registry):
            return False
        _state["running"] = True
        _state["last_attempt"] = now
    (runner or _spawn)(settings)
    return True


def _spawn(settings: Settings) -> None:
    threading.Thread(
        target=_run_refresh, args=(settings,), name="auto-preflight", daemon=True
    ).start()


def _run_refresh(settings: Settings) -> None:
    db = SessionLocal()
    try:
        registry = get_agent_registry()
        for route_key in _core_route_keys(settings, registry):
            route = registry.route(route_key)
            if route.evaluation_only and not settings.agent_quality_ceiling_enabled:
                continue
            result = preflight_route(
                route_key, settings=settings, registry=registry, execute_live=True
            )
            persist_route_preflight(
                db, result, triggered_by=_TRIGGERED_BY, settings=settings
            )
        if settings.web_research_enabled and not settings.web_research_fake_provider:
            firecrawl = preflight_firecrawl(settings=settings, execute_live=True)
            persist_route_preflight(
                db, firecrawl, triggered_by=_TRIGGERED_BY, settings=settings
            )
        db.commit()
        logger.info("auto preflight refresh complete")
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("auto preflight refresh failed")
    finally:
        db.close()
        with _lock:
            _state["running"] = False


def _reset_state_for_tests() -> None:
    with _lock:
        _state["running"] = False
        _state["last_attempt"] = None
