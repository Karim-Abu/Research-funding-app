"""A1 provenance enforcement before persistence (Milestone 9B)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import fact_extraction
from app.db.models import ExtractedFact, OpenIssue
from app.db.session import SessionLocal
from tests.a1_helpers import (
    FIELD_ID,
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


def _run(db, run, payload):
    return fact_extraction.run_a1_fact_extraction(
        db, run, provider_resolver=fake_resolver(success_fake(payload))
    )


def _facts(db, run):
    return db.scalars(select(ExtractedFact).where(ExtractedFact.run_id == run.run_id)).all()


def test_valid_provenance_persists(db):
    run, frags, _ = build_run(db)
    out = _run(db, run, result_payload(facts=[fact("f1", [frags[0]], target_ref=REQ_ID)]))
    assert out.status == "succeeded" and out.facts_persisted == 1
    assert _facts(db, run)[0].requirement_id == REQ_ID


def test_hallucinated_fragment_rejected(db):
    run, frags, _ = build_run(db)
    # Fragment id not present in the run snapshot → gateway rejects the whole
    # output (no facts), the orchestrator records a genuine failure.
    out = _run(db, run, result_payload(facts=[fact("f1", ["GHOST-FRAGMENT"])]))
    assert out.status == "failed" and _facts(db, run) == []
    issues = db.scalars(select(OpenIssue).where(OpenIssue.run_id == run.run_id)).all()
    assert any(i.issue_type == "ai_extraction_unavailable" for i in issues)


def test_fragment_outside_run_snapshot_rejected(db):
    run_a, frags_a, _ = build_run(db)
    run_b, frags_b, _ = build_run(db)  # different run/snapshot
    # A fact in run_a citing run_b's fragment → not in run_a's allowed set.
    out = _run(db, run_a, result_payload(facts=[fact("f1", [frags_b[0]])]))
    assert out.status == "failed" and _facts(db, run_a) == []


def test_foreign_workspace_fragment_rejected(db):
    run, frags, _ = build_run(db, workspace_id="ws-demo")
    other_run, other_frags, _ = build_run(db, workspace_id="ws-test")
    out = _run(db, run, result_payload(facts=[fact("f1", [other_frags[0]])]))
    assert out.status == "failed" and _facts(db, run) == []


def test_invalid_requirement_id_rejected_partial(db):
    run, frags, _ = build_run(db)
    payload = result_payload(facts=[
        fact("ok", [frags[0]], target_ref=REQ_ID),
        fact("bad", [frags[0]], target_ref="REQ.DOES.NOT.EXIST"),
    ])
    out = _run(db, run, payload)
    assert out.status == "succeeded"
    assert out.facts_persisted == 1 and out.facts_rejected == 1
    rows = _facts(db, run)
    assert len(rows) == 1 and rows[0].requirement_id == REQ_ID


def test_invalid_field_id_rejected(db):
    run, frags, _ = build_run(db)
    out = _run(db, run, result_payload(
        facts=[fact("bad", [frags[0]], target_ref="SOL.NOPE")]
    ))
    assert out.status == "succeeded" and out.facts_persisted == 0
    assert out.facts_rejected == 1 and _facts(db, run) == []


def test_valid_field_target_resolves(db):
    run, frags, _ = build_run(db)
    out = _run(db, run, result_payload(facts=[fact("f", [frags[0]], target_ref=FIELD_ID)]))
    assert out.facts_persisted == 1 and _facts(db, run)[0].field_id == FIELD_ID
