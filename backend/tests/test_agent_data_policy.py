"""Data Policy enforcement for model invocations (Milestone 9A)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import data_policy
from app.agents.gateway import SafeFailure, invoke
from app.agents.providers import FakeProvider
from app.agents.registry import get_agent_registry
from app.config.settings import get_settings
from app.db.models import AgentInvocation, ControlResult
from app.db.session import SessionLocal
from tests.agent_helpers import base_request, fake_resolver

PROFILE = "A1.project_fact_extraction"


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _decide(classification, processing_mode, *, approved=False, confirmation=False):
    profile = get_agent_registry().profile(PROFILE)
    settings = get_settings().model_copy(
        update={"agent_institutional_route_approved": approved}
    )
    return data_policy.evaluate(
        profile=profile, classification=classification, processing_mode=processing_mode,
        settings=settings, run_confirmation=confirmation,
    )


def test_public_cloud_allowed():
    assert _decide({"sensitivity": "public"}, "cloud_assisted").outcome == "allowed"


def test_deterministic_only_blocked():
    assert _decide({"sensitivity": "public"}, "deterministic_only").blocked


def test_local_only_blocked():
    assert _decide({"sensitivity": "public"}, "local_only").blocked


def test_confidential_blocked():
    assert _decide({"sensitivity": "confidential"}, "cloud_assisted").blocked


def test_nda_blocked():
    assert _decide({"sensitivity": "public", "nda_applies": True}, "cloud_assisted").blocked


def test_missing_classification_blocked():
    assert _decide({}, "cloud_assisted").blocked  # missing → confidential → blocked


def test_internal_blocked_without_institutional_approval():
    assert _decide({"sensitivity": "internal"}, "cloud_assisted").blocked


def test_internal_allowed_with_approval_and_confirmation():
    d = _decide({"sensitivity": "internal"}, "cloud_assisted", approved=True, confirmation=True)
    assert d.outcome == "allowed_with_confirmation"


def test_internal_blocked_with_approval_but_no_confirmation():
    assert _decide({"sensitivity": "internal"}, "cloud_assisted", approved=True).blocked


def test_no_silent_downgrade_deterministic_stays_blocked():
    # deterministic_only is never auto-upgraded to cloud_assisted.
    assert _decide({"sensitivity": "public"}, "deterministic_only").blocked


def test_gateway_block_records_status_and_control(db):
    resp = invoke(
        db, base_request(processing_mode="deterministic_only"),
        provider_resolver=fake_resolver(FakeProvider()),
    )
    assert isinstance(resp, SafeFailure) and resp.status == "blocked"
    inv = db.get(AgentInvocation, resp.invocation_id)
    assert inv.status == "blocked"
    dp_control = db.scalar(
        select(ControlResult).where(
            ControlResult.agent_invocation_id == inv.invocation_id,
            ControlResult.control_id == "CTRL.DATA_POLICY",
        )
    )
    assert dp_control is not None and dp_control.status == "blocked"
