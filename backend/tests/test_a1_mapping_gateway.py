"""A1 evidence-mapping ↔ ModelGateway integration via the fake provider (M9C)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import evidence_mapping
from app.agents.providers import FakeProvider
from app.config.settings import get_settings
from app.db.models import ControlResult, EvidenceCandidate, OpenIssue
from app.db.session import SessionLocal
from tests.a1_mapping_helpers import (
    build_run,
    candidate,
    fake_resolver,
    mapping_result,
    success_fake,
)

QUOTE = "The Swiss implementation partner is based in Zurich."


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _map(db, run, provider):
    return evidence_mapping.run_a1_evidence_mapping(
        db, run, provider_resolver=fake_resolver(provider)
    )


def _candidates(db, run):
    return db.scalars(
        select(EvidenceCandidate).where(EvidenceCandidate.run_id == run.run_id)
    ).all()


def _issues(db, run):
    return db.scalars(select(OpenIssue).where(OpenIssue.run_id == run.run_id)).all()


def test_valid_candidate_output(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    out = _map(db, run, success_fake(mapping_result(candidates=[candidate(frags[0], QUOTE)])))
    assert out.status == "succeeded" and out.candidates_persisted == 1


def test_missing_evidence_unmapped_targets(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    out = _map(db, run, success_fake(mapping_result(
        unmapped=[{"target_type": "requirement", "target_id": "REQ.X"}]
    )))
    assert out.status == "succeeded" and out.candidates_persisted == 0
    assert _candidates(db, run) == []


def test_malformed_output_safe_failure(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    out = _map(db, run, FakeProvider(mode="malformed"))
    assert out.status == "failed" and _candidates(db, run) == []
    assert any(i.issue_type == "ai_evidence_mapping_unavailable" for i in _issues(db, run))


def test_timeout_creates_info_issue(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    out = _map(db, run, FakeProvider(mode="timeout"))
    assert out.status == "failed"
    assert any(i.severity == "info" for i in _issues(db, run))


def test_provider_error_falls_back_then_fails(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    out = _map(db, run, FakeProvider(mode="error"))
    assert out.status == "failed" and _candidates(db, run) == []


def test_provider_unavailable_skip_no_issue(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    out = evidence_mapping.run_a1_evidence_mapping(
        db, run, provider_resolver=lambda _route: None
    )
    assert out.status == "skipped" and _issues(db, run) == []


def test_deterministic_only_skips(db):
    run, frags, _ = build_run(db, fragments=[QUOTE], processing_mode="deterministic_only")
    provider = success_fake(mapping_result(candidates=[candidate(frags[0], QUOTE)]))
    out = _map(db, run, provider)
    assert out.status == "skipped" and provider.calls == 0 and _candidates(db, run) == []


def test_confidential_blocks(db):
    run, frags, _ = build_run(db, fragments=[QUOTE], sensitivity="confidential")
    provider = success_fake(mapping_result(candidates=[candidate(frags[0], QUOTE)]))
    out = _map(db, run, provider)
    assert out.status == "blocked" and provider.calls == 0
    blocked = db.scalars(
        select(ControlResult).where(
            ControlResult.run_id == run.run_id,
            ControlResult.control_id == "CTRL.DATA_POLICY",
            ControlResult.status == "blocked",
        )
    ).all()
    assert blocked


def test_internal_real_project_blocked_without_approval(db):
    run, frags, _ = build_run(db, fragments=[QUOTE], sensitivity="internal", origin="real_project")
    provider = success_fake(mapping_result(candidates=[candidate(frags[0], QUOTE)]))
    out = _map(db, run, provider)
    assert out.status == "blocked" and provider.calls == 0
    assert get_settings().agent_institutional_route_approved is False


def test_evidence_requirement_control_recorded(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    out = _map(db, run, success_fake(mapping_result(candidates=[candidate(frags[0], QUOTE)])))
    ctrl = db.scalars(
        select(ControlResult).where(
            ControlResult.agent_invocation_id == out.invocation_id,
            ControlResult.control_id == "CTRL.EVIDENCE_REQUIREMENT",
        )
    ).all()
    assert ctrl and ctrl[0].status == "passed"
