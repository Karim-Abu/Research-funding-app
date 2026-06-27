"""A1 ExtractedFact persistence (Milestone 9B)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import fact_extraction
from app.db.models import ExtractedFact
from app.db.session import SessionLocal
from app.repositories import extracted_facts as facts_repo
from tests.a1_helpers import (
    REQ_ID,
    build_run,
    fact,
    fake_resolver,
    result_payload,
    success_fake,
)


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _run_a1(db, run, payload):
    return fact_extraction.run_a1_fact_extraction(
        db, run, provider_resolver=fake_resolver(success_fake(payload))
    )


def test_proposed_conflict_missing_persist(db):
    run, frags, _ = build_run(db, fragments=["Alpha.", "Beta."])
    payload = result_payload(
        facts=[fact("f1", [frags[0]], statement="Alpha is funded.")],
        conflicts=[{"conflict_id": "c1", "description": "Alpha vs Beta budget", "fact_ids": ["f1"]}],
        missing=[{"target_ref": REQ_ID, "description": "No implementation partner stated."}],
    )
    outcome = _run_a1(db, run, payload)
    assert outcome.status == "succeeded" and outcome.facts_persisted == 3

    rows = db.scalars(select(ExtractedFact).where(ExtractedFact.run_id == run.run_id)).all()
    statuses = sorted(r.status for r in rows)
    assert statuses == ["conflicted", "missing", "proposed"]
    proposed = next(r for r in rows if r.status == "proposed")
    assert proposed.source_fragment_ids == [frags[0]]
    assert proposed.agent_invocation_id and proposed.prompt_version
    missing = next(r for r in rows if r.status == "missing")
    assert missing.requirement_id == REQ_ID and missing.source_fragment_ids == []


def test_confirmed_and_rejected_never_created(db):
    run, frags, _ = build_run(db)
    _run_a1(db, run, result_payload(facts=[fact("f1", [frags[0]])]))
    rows = db.scalars(select(ExtractedFact).where(ExtractedFact.run_id == run.run_id)).all()
    assert rows and all(r.status in fact_extraction.facts_repo.M9B_STATUSES for r in rows)
    assert not any(r.status in ("confirmed", "rejected") for r in rows)


def test_idempotent_upsert_no_duplicates(db):
    run, frags, sv = build_run(db)
    kw = dict(
        run_id=run.run_id, workspace_id=run.workspace_id, fact_type="project_fact",
        normalized_value=None, original_statement="Same fact.", status="proposed",
        requirement_id=None, field_id=None, source_fragment_ids=[frags[0]],
        source_version_ids=[sv], profile_id="A1.project_fact_extraction",
        model_route="r", model_id="m", schema_version="s", prompt_version="p",
        agent_invocation_id="inv",
    )
    _, created1 = facts_repo.upsert(db, **kw)
    _, created2 = facts_repo.upsert(db, **kw)
    assert created1 is True and created2 is False
    rows = db.scalars(select(ExtractedFact).where(ExtractedFact.run_id == run.run_id)).all()
    assert len(rows) == 1


def test_workspace_isolation(db):
    run, frags, _ = build_run(db, workspace_id="ws-demo")
    _run_a1(db, run, result_payload(facts=[fact("f1", [frags[0]])]))
    rows = db.scalars(select(ExtractedFact).where(ExtractedFact.run_id == run.run_id)).all()
    assert rows and all(r.workspace_id == "ws-demo" for r in rows)
    # No facts leak into another workspace's view.
    other = db.scalars(
        select(ExtractedFact).where(ExtractedFact.workspace_id == "ws-other")
    ).all()
    assert other == []
