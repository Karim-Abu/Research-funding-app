"""A1 evidence-proposal evaluation trail + dedup traceability (Milestone 9C corr #2/#4)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.agents import evidence_mapping
from app.db.models import AgentEvidenceProposal, EvidenceCandidate, RequirementAssessment
from app.db.session import SessionLocal
from app.evidence import pipeline as evidence_pipeline
from tests.a1_mapping_helpers import (
    REQ_ID,
    build_run,
    candidate,
    fake_resolver,
    mapping_result,
    success_fake,
)

QUOTE = "Acme GmbH is the Swiss implementation partner based in Zurich."


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _map(db, run, payload):
    return evidence_mapping.run_a1_evidence_mapping(
        db, run, provider_resolver=fake_resolver(success_fake(payload))
    )


def _proposals(db, run):
    return db.scalars(
        select(AgentEvidenceProposal).where(AgentEvidenceProposal.run_id == run.run_id)
    ).all()


def test_accepted_candidate_writes_persisted_new_proposal(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    _map(db, run, mapping_result(candidates=[candidate(frags[0], QUOTE)]))
    proposals = _proposals(db, run)
    assert len(proposals) == 1
    p = proposals[0]
    assert p.outcome == "persisted_new" and p.proposed_by_agent is True
    assert p.candidate_id and p.target_requirement_id == REQ_ID and p.agent_invocation_id


def test_backfill_fills_verification_and_link(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    _map(db, run, mapping_result(candidates=[candidate(frags[0], QUOTE)]))
    evidence_pipeline.run_verification(db, run)

    # A RequirementAssessment must exist for the link to materialize.
    assessment_id = str(uuid.uuid4())
    db.add(RequirementAssessment(
        assessment_id=assessment_id, run_id=run.run_id, requirement_id=REQ_ID,
        requirement_version="1.0.0", status="met", basis="deterministic_rule",
        reasoning="test",
    ))
    db.flush()
    evidence_pipeline.materialize_links(db, run)
    evidence_mapping.backfill_agent_evaluation(db, run)

    p = _proposals(db, run)[0]
    assert p.verification_status == "exact_verified"
    assert p.linked_assessment_id == assessment_id


def test_rejected_candidate_writes_rejected_proposal(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    _map(db, run, mapping_result(
        candidates=[candidate(frags[0], "A paraphrase not in the source.")]
    ))
    p = _proposals(db, run)[0]
    assert p.outcome == "rejected" and p.rejection_reason == "quote_not_in_fragment"
    assert p.candidate_id is None


def test_backfill_idempotent_under_replay(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    _map(db, run, mapping_result(candidates=[candidate(frags[0], QUOTE)]))
    evidence_pipeline.run_verification(db, run)
    evidence_mapping.backfill_agent_evaluation(db, run)
    evidence_mapping.backfill_agent_evaluation(db, run)  # second call is safe
    assert _proposals(db, run)[0].verification_status == "exact_verified"
