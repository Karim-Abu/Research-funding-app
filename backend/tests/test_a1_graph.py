"""A1 inside the run graph stage + deterministic-baseline preservation (M9B)."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.agents import fact_extraction
from app.db.models import AgentInvocation, AnalysisRun, EvidenceCandidate, ExtractedFact
from app.db.session import SessionLocal
from app.evidence import pipeline as evidence_pipeline
from app.runs.graph import node_extract_facts_and_map_evidence
from tests.a1_helpers import build_run, fact, fake_resolver, result_payload, success_fake

FRAGMENTS = [
    "The consortium includes a Swiss implementation partner based in Zürich.",
    "The project develops a novel sensor platform with measurable innovation.",
]


def _commit_run(**kw):
    db = SessionLocal()
    try:
        run, frags, _ = build_run(db, fragments=FRAGMENTS, **kw)
        run_id = run.run_id
        db.commit()
        return run_id, frags
    finally:
        db.close()


def _candidate_count(run_id: str) -> int:
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


def test_cloud_path_persists_facts_and_runs_discovery(monkeypatch, fresh):
    run_id, frags = _commit_run(processing_mode="cloud_assisted")
    provider = success_fake(result_payload(facts=[fact("f", [frags[0]])]))
    monkeypatch.setattr(fact_extraction, "_PROVIDER_RESOLVER", fake_resolver(provider))

    node_extract_facts_and_map_evidence({"run_id": run_id})

    facts = fresh.scalars(
        select(ExtractedFact).where(ExtractedFact.run_id == run_id)
    ).all()
    assert len(facts) == 1  # A1 ran and persisted
    # Fact extraction ran; only A1 agents are ever invoked (no A2/A3). The same
    # stage also runs A1.evidence_candidate_mapping (M9C).
    invs = fresh.scalars(
        select(AgentInvocation).where(AgentInvocation.run_id == run_id)
    ).all()
    assert any(i.profile_id == "A1.project_fact_extraction" for i in invs)
    assert all(i.agent_id == "A1" for i in invs)


def test_deterministic_only_path_skips_facts(monkeypatch, fresh):
    run_id, frags = _commit_run(processing_mode="deterministic_only")
    provider = success_fake(result_payload(facts=[fact("f", [frags[0]])]))
    monkeypatch.setattr(fact_extraction, "_PROVIDER_RESOLVER", fake_resolver(provider))

    node_extract_facts_and_map_evidence({"run_id": run_id})

    assert provider.calls == 0  # no provider call on deterministic-only
    assert fresh.scalars(
        select(ExtractedFact).where(ExtractedFact.run_id == run_id)
    ).all() == []
    assert fresh.scalars(
        select(AgentInvocation).where(AgentInvocation.run_id == run_id)
    ).all() == []


def test_a1_does_not_change_deterministic_evidence(monkeypatch):
    # Run A1 + discovery on run_a (via the node); discovery-only on identical run_b.
    run_a, frags_a = _commit_run(processing_mode="cloud_assisted")
    provider = success_fake(result_payload(facts=[fact("f", [frags_a[0]])]))
    monkeypatch.setattr(fact_extraction, "_PROVIDER_RESOLVER", fake_resolver(provider))
    node_extract_facts_and_map_evidence({"run_id": run_a})

    run_b, _ = _commit_run(processing_mode="cloud_assisted")
    db = SessionLocal()
    try:
        evidence_pipeline.run_discovery(db, db.get(AnalysisRun, run_b))
        db.commit()
    finally:
        db.close()

    # A1 facts must not influence the deterministic evidence candidate count.
    assert _candidate_count(run_a) == _candidate_count(run_b)
