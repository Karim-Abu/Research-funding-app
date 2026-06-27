"""A1 Data Policy gating in the orchestrator (Milestone 9B)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import fact_extraction
from app.config.settings import get_settings
from app.db.models import ControlResult, ExtractedFact
from app.db.session import SessionLocal
from tests.a1_helpers import build_run, fact, fake_resolver, result_payload, success_fake


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _run(db, run, provider):
    return fact_extraction.run_a1_fact_extraction(
        db, run, provider_resolver=fake_resolver(provider)
    )


def _facts(db, run):
    return db.scalars(select(ExtractedFact).where(ExtractedFact.run_id == run.run_id)).all()


def test_deterministic_only_skips_without_provider_call(db):
    run, frags, _ = build_run(db, processing_mode="deterministic_only")
    provider = success_fake(result_payload(facts=[fact("f", [frags[0]])]))
    out = _run(db, run, provider)
    assert out.status == "skipped" and provider.calls == 0  # never called
    assert _facts(db, run) == []


def test_local_only_skips(db):
    run, frags, _ = build_run(db, processing_mode="local_only")
    provider = success_fake(result_payload(facts=[fact("f", [frags[0]])]))
    out = _run(db, run, provider)
    assert out.status == "skipped" and provider.calls == 0


def test_public_synthetic_cloud_runs_a1(db):
    run, frags, _ = build_run(db, sensitivity="public", origin="synthetic")
    out = _run(db, run, success_fake(result_payload(facts=[fact("f", [frags[0]])])))
    assert out.status == "succeeded" and _facts(db, run)


def test_confidential_blocks(db):
    run, frags, _ = build_run(db, sensitivity="confidential")
    provider = success_fake(result_payload(facts=[fact("f", [frags[0]])]))
    out = _run(db, run, provider)
    assert out.status == "blocked" and provider.calls == 0 and _facts(db, run) == []
    blocked = db.scalars(
        select(ControlResult).where(
            ControlResult.run_id == run.run_id,
            ControlResult.control_id == "CTRL.DATA_POLICY",
            ControlResult.status == "blocked",
        )
    ).all()
    assert blocked


def test_nda_blocks(db):
    run, frags, _ = build_run(db, sensitivity="public", nda=True)
    provider = success_fake(result_payload(facts=[fact("f", [frags[0]])]))
    out = _run(db, run, provider)
    assert out.status == "blocked" and provider.calls == 0


def test_internal_real_project_blocked_without_approval(db):
    run, frags, _ = build_run(db, sensitivity="internal", origin="real_project")
    provider = success_fake(result_payload(facts=[fact("f", [frags[0]])]))
    out = _run(db, run, provider)
    assert out.status == "blocked" and provider.calls == 0
    assert get_settings().agent_institutional_route_approved is False
