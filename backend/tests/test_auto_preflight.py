"""Lazy Auto-Preflight (2026-07-24): kickt einen Hintergrund-Refresh nur, wenn
er soll — real-Modus, aktiviert, kein Live/Fake-Konflikt, nichts in-flight, kein
Cooldown, und tatsächlich abgelaufen/fehlend. Keine Live-Calls (Runner injiziert).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.agents.providers import FakeProvider
from app.agents.registry import get_agent_registry
from app.config.settings import Settings
from app.db.session import SessionLocal
from app.evaluation import auto_preflight
from app.evaluation.preflight import persist_route_preflight, preflight_route

ONE_KEY = ["openai_gpt_56_luna_candidate"]


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def _reset_state():
    auto_preflight._reset_state_for_tests()
    yield
    auto_preflight._reset_state_for_tests()


def _live_settings(**overrides) -> Settings:
    base = dict(
        ai_eval_mode="real",
        agent_fake_provider=False,
        openai_api_key="sk-hermetic",
        anthropic_api_key="sk-hermetic",
        web_research_enabled=False,
        provider_preflight_auto_refresh=True,
        agent_model_gpt_56_luna_id="hermetic-model",
    )
    base.update(overrides)
    return Settings(**base)


def _spy():
    calls: list = []
    return calls, (lambda settings: calls.append(settings))


# --- Guards ------------------------------------------------------------------

def test_skips_when_eval_mode_not_real(db):
    calls, runner = _spy()
    assert auto_preflight.maybe_refresh(db, _live_settings(ai_eval_mode="off"), runner=runner) is False
    assert calls == []


def test_skips_when_auto_refresh_disabled(db):
    calls, runner = _spy()
    settings = _live_settings(provider_preflight_auto_refresh=False)
    assert auto_preflight.maybe_refresh(db, settings, runner=runner) is False
    assert calls == []


def test_skips_on_live_fake_conflict(db):
    calls, runner = _spy()
    assert auto_preflight.maybe_refresh(db, _live_settings(agent_fake_provider=True), runner=runner) is False
    assert calls == []


def test_skips_when_no_db(db):
    calls, runner = _spy()
    assert auto_preflight.maybe_refresh(None, _live_settings(), runner=runner) is False
    assert calls == []


# --- Kick + concurrency guards -----------------------------------------------

def test_kicks_once_when_preflight_missing(db, monkeypatch):
    monkeypatch.setattr(auto_preflight, "_required_route_keys", lambda s, r: ONE_KEY)
    calls, runner = _spy()
    assert auto_preflight.maybe_refresh(db, _live_settings(), runner=runner) is True
    assert len(calls) == 1


def test_in_flight_guard_blocks_second_kick(db, monkeypatch):
    monkeypatch.setattr(auto_preflight, "_required_route_keys", lambda s, r: ONE_KEY)
    calls, runner = _spy()
    assert auto_preflight.maybe_refresh(db, _live_settings(), runner=runner) is True
    # The spy runner does not clear the running flag → a second call is a no-op.
    assert auto_preflight.maybe_refresh(db, _live_settings(), runner=runner) is False
    assert len(calls) == 1


def test_cooldown_blocks_rapid_retry(db, monkeypatch):
    monkeypatch.setattr(auto_preflight, "_required_route_keys", lambda s, r: ONE_KEY)
    calls, runner = _spy()
    auto_preflight._state["running"] = False
    auto_preflight._state["last_attempt"] = datetime.now(timezone.utc)
    assert auto_preflight.maybe_refresh(db, _live_settings(), runner=runner) is False
    assert calls == []


# --- refresh_needed: expiry / margin logic -----------------------------------

def test_refresh_needed_tracks_expiry_and_margin(db, monkeypatch):
    monkeypatch.setattr(auto_preflight, "_required_route_keys", lambda s, r: ONE_KEY)
    settings = _live_settings()
    registry = get_agent_registry()

    # No row yet → needed.
    assert auto_preflight.refresh_needed(db, settings, registry) is True

    result = preflight_route(
        ONE_KEY[0], settings=settings, adapter=FakeProvider(), execute_live=False
    )
    row = persist_route_preflight(db, result, settings=settings)

    # Fresh row well beyond the margin → not needed.
    row.expires_at = datetime.now(timezone.utc) + timedelta(hours=6)
    db.flush()
    assert auto_preflight.refresh_needed(db, settings, registry) is False

    # Within the proactive margin (default 30 min) → needed again.
    row.expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.flush()
    assert auto_preflight.refresh_needed(db, settings, registry) is True

    # Expired → needed.
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.flush()
    assert auto_preflight.refresh_needed(db, settings, registry) is True
