"""A1 ↔ ModelGateway integration via the fake provider (Milestone 9B)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import fact_extraction
from app.agents.providers import FakeProvider
from app.db.models import ExtractedFact, OpenIssue
from app.db.session import SessionLocal
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


def _run(db, run, provider):
    return fact_extraction.run_a1_fact_extraction(
        db, run, provider_resolver=fake_resolver(provider)
    )


def _facts(db, run):
    return db.scalars(select(ExtractedFact).where(ExtractedFact.run_id == run.run_id)).all()


def _issues(db, run):
    return db.scalars(select(OpenIssue).where(OpenIssue.run_id == run.run_id)).all()


def test_success_with_valid_facts(db):
    run, frags, _ = build_run(db)
    out = _run(db, run, success_fake(result_payload(facts=[fact("f", [frags[0]])])))
    assert out.status == "succeeded" and out.facts_persisted == 1


def test_missing_information_response(db):
    run, frags, _ = build_run(db)
    out = _run(db, run, success_fake(result_payload(
        missing=[{"target_ref": REQ_ID, "description": "No budget provided."}]
    )))
    assert out.status == "succeeded"
    assert _facts(db, run)[0].status == "missing"


def test_conflict_response(db):
    run, frags, _ = build_run(db, fragments=["A says X.", "B says not X."])
    out = _run(db, run, success_fake(result_payload(
        facts=[fact("f1", [frags[0]]), fact("f2", [frags[1]])],
        conflicts=[{"conflict_id": "c", "description": "X vs not X", "fact_ids": ["f1", "f2"]}],
    )))
    assert out.status == "succeeded"
    conflicted = [r for r in _facts(db, run) if r.status == "conflicted"]
    assert len(conflicted) == 1 and sorted(conflicted[0].source_fragment_ids) == sorted(frags)


def test_malformed_output_is_safe_failure(db):
    run, frags, _ = build_run(db)
    out = _run(db, run, FakeProvider(mode="malformed"))
    assert out.status == "failed" and _facts(db, run) == []
    assert any(i.issue_type == "ai_extraction_unavailable" for i in _issues(db, run))


def test_timeout_is_safe_failure_with_issue(db):
    run, frags, _ = build_run(db)
    out = _run(db, run, FakeProvider(mode="timeout"))
    assert out.status == "failed"
    assert any(i.severity == "info" for i in _issues(db, run))


def test_provider_error_falls_back_then_fails(db):
    run, frags, _ = build_run(db)
    out = _run(db, run, FakeProvider(mode="error"))  # primary + fallback both error
    assert out.status == "failed" and _facts(db, run) == []


def test_provider_unavailable_is_skip_no_issue(db):
    run, frags, _ = build_run(db)
    out = fact_extraction.run_a1_fact_extraction(
        db, run, provider_resolver=lambda _route: None
    )
    assert out.status == "skipped" and out.reason == "provider_unavailable"
    assert _issues(db, run) == []  # no-key-by-design is non-alarming


def test_extra_field_in_output_rejected(db):
    run, frags, _ = build_run(db)
    payload = result_payload(facts=[fact("f", [frags[0]])])
    payload["unexpected"] = True  # extra="forbid" at the result level
    out = _run(db, run, success_fake(payload))
    assert out.status == "failed" and _facts(db, run) == []
