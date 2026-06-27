"""A1 evidence mapping in the graph stage + replay + deterministic preservation (M9C)."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.agents import evidence_mapping
from app.db.models import AgentInvocation, EvidenceCandidate
from app.db.session import SessionLocal
from app.runs.graph import node_extract_facts_and_map_evidence
from tests.a1_mapping_helpers import (
    build_run,
    candidate,
    fake_resolver,
    mapping_result,
    success_fake,
)

QUOTE = "The Swiss implementation partner is based in Zurich."


def _commit_run(**kw):
    db = SessionLocal()
    try:
        run, frags, _ = build_run(db, fragments=[QUOTE], **kw)
        run_id = run.run_id
        db.commit()
        return run_id, frags
    finally:
        db.close()


def _agent_count(run_id: str) -> int:
    db = SessionLocal()
    try:
        return db.scalar(
            select(func.count(EvidenceCandidate.candidate_id)).where(
                EvidenceCandidate.run_id == run_id,
                EvidenceCandidate.generation_origin == "agent_a1_evidence_mapping",
            )
        ) or 0
    finally:
        db.close()


def _total_candidates(run_id: str) -> int:
    db = SessionLocal()
    try:
        return db.scalar(
            select(func.count(EvidenceCandidate.candidate_id)).where(
                EvidenceCandidate.run_id == run_id
            )
        ) or 0
    finally:
        db.close()


@pytest.fixture
def fresh():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_cloud_path_creates_agent_candidates_and_completes(monkeypatch, fresh):
    run_id, frags = _commit_run(processing_mode="cloud_assisted")
    provider = success_fake(mapping_result(candidates=[candidate(frags[0], QUOTE)]))
    monkeypatch.setattr(evidence_mapping, "_PROVIDER_RESOLVER", fake_resolver(provider))

    node_extract_facts_and_map_evidence({"run_id": run_id})

    assert _agent_count(run_id) == 1
    invs = fresh.scalars(
        select(AgentInvocation).where(
            AgentInvocation.run_id == run_id,
            AgentInvocation.profile_id == "A1.evidence_candidate_mapping",
        )
    ).all()
    assert invs and all(i.profile_id == "A1.evidence_candidate_mapping" for i in invs)
    # No A2/A3 invoked.
    a23 = fresh.scalars(
        select(AgentInvocation).where(
            AgentInvocation.run_id == run_id,
            AgentInvocation.agent_id.in_(["A2", "A3"]),
        )
    ).all()
    assert a23 == []


def test_deterministic_only_skips_mapping(monkeypatch):
    # Baseline run: deterministic candidate count without any agent mapping.
    baseline_id, _ = _commit_run(processing_mode="deterministic_only")
    node_extract_facts_and_map_evidence({"run_id": baseline_id})
    baseline_total = _total_candidates(baseline_id)

    assert _agent_count(baseline_id) == 0  # no agent candidates on deterministic-only

    # Same content with the agent provider available but mode deterministic_only →
    # still no agent candidates; total candidates identical to the baseline.
    other_id, frags = _commit_run(processing_mode="deterministic_only")
    provider = success_fake(mapping_result(candidates=[candidate(frags[0], QUOTE)]))
    monkeypatch.setattr(evidence_mapping, "_PROVIDER_RESOLVER", fake_resolver(provider))
    node_extract_facts_and_map_evidence({"run_id": other_id})
    assert provider.calls == 0
    assert _agent_count(other_id) == 0
    assert _total_candidates(other_id) == baseline_total


def test_replay_guard_makes_no_second_provider_call(monkeypatch):
    run_id, frags = _commit_run(processing_mode="cloud_assisted")
    p1 = success_fake(mapping_result(candidates=[candidate(frags[0], QUOTE)]))
    monkeypatch.setattr(evidence_mapping, "_PROVIDER_RESOLVER", fake_resolver(p1))
    node_extract_facts_and_map_evidence({"run_id": run_id})
    assert p1.calls == 1 and _agent_count(run_id) == 1

    # Re-execute the stage (checkpoint replay): a succeeded invocation already exists.
    from app.db.models import AnalysisRun

    p2 = success_fake(mapping_result(candidates=[candidate(frags[0], QUOTE)]))
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        outcome = evidence_mapping.run_a1_evidence_mapping(
            db, run, provider_resolver=fake_resolver(p2)
        )
        db.commit()
    finally:
        db.close()
    assert outcome.status == "reused" and p2.calls == 0
    assert _agent_count(run_id) == 1  # no duplicate from replay
