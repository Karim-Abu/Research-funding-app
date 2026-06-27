"""A1 CostGuard + usage recording via the orchestrator (Milestone 9B)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import fact_extraction
from app.db.models import ExtractedFact, UsageRecord
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


def test_max_per_run_enforced(db):
    run, frags, _ = build_run(db)
    payload = result_payload(facts=[fact("f", [frags[0]])])
    first = _run(db, run, success_fake(payload))
    assert first.status == "succeeded"
    before = len(db.scalars(select(ExtractedFact).where(ExtractedFact.run_id == run.run_id)).all())
    # Second A1 call on the same run exceeds max_per_run=1 → blocked, no new facts.
    second = _run(db, run, success_fake(payload))
    assert second.status == "blocked"
    after = len(db.scalars(select(ExtractedFact).where(ExtractedFact.run_id == run.run_id)).all())
    assert after == before


def test_usage_record_token_fields_populated(db):
    run, frags, _ = build_run(db)
    provider = success_fake(
        result_payload(facts=[fact("f", [frags[0]])]), input_tokens=33, output_tokens=44
    )
    _run(db, run, provider)
    usage = db.scalars(
        select(UsageRecord).where(UsageRecord.run_id == run.run_id)
    ).all()
    assert any(u.input_tokens == 33 and u.output_tokens == 44 for u in usage)
    assert all(u.cost_chf == 0.0 for u in usage)  # no pricing config → placeholder
