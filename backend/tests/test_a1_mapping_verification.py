"""A1 agent candidates flow through the deterministic verifier (Milestone 9C)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import evidence_mapping
from app.db.models import EvidenceAnchor, EvidenceCandidate
from app.db.session import SessionLocal
from app.evidence import pipeline as evidence_pipeline
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


def _map(db, run, payload):
    return evidence_mapping.run_a1_evidence_mapping(
        db, run, provider_resolver=fake_resolver(success_fake(payload))
    )


def _agent_candidate(db, run):
    return db.scalar(
        select(EvidenceCandidate).where(
            EvidenceCandidate.run_id == run.run_id,
            EvidenceCandidate.generation_origin == "agent_a1_evidence_mapping",
        )
    )


def test_agent_exact_quote_becomes_exact_verified_via_verifier(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    _map(db, run, mapping_result(candidates=[candidate(frags[0], QUOTE)]))
    cand = _agent_candidate(db, run)
    assert cand.anchor_id is None  # not verified yet — A1 cannot verify

    # The deterministic verifier is the ONLY thing that produces exact_verified.
    evidence_pipeline.run_verification(db, run)
    cand = _agent_candidate(db, run)
    anchor = db.get(EvidenceAnchor, cand.anchor_id)
    assert anchor.verification_status == "exact_verified"
    assert anchor.match_type == "exact_normalized"


def test_altered_quote_does_not_verify(db):
    # The fragment text differs from the (impossible) quote, but build a fragment
    # where the candidate quote exists, then mutate the version so the offset no
    # longer matches → verifier returns unverified, never exact_verified.
    run, frags, sv = build_run(db, fragments=["Prefix. " + QUOTE])
    _map(db, run, mapping_result(candidates=[candidate(frags[0], QUOTE)]))
    cand = _agent_candidate(db, run)
    # Tamper with the frozen version text after the candidate was positioned.
    from app.db.models import SourceVersion
    version = db.get(SourceVersion, sv)
    version.normalized_text = "Totally different content of equal-ish length here..."
    db.flush()

    evidence_pipeline.run_verification(db, run)
    cand = _agent_candidate(db, run)
    anchor = db.get(EvidenceAnchor, cand.anchor_id)
    assert anchor.verification_status in ("unverified", "rejected")


def test_anchor_dedup_with_deterministic(db):
    run, frags, sv = build_run(db, fragments=[QUOTE])
    # Identical deterministic candidate already verified → agent quote must not
    # create a second anchor (idempotent verification).
    from app.evidence.discovery import quote_hash
    db.add(EvidenceCandidate(
        candidate_id="det-1", run_id=run.run_id, workspace_id=run.workspace_id,
        target_type="requirement", target_requirement_id="REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH",
        fragment_id=frags[0], source_version_id=sv, source_id="src", proposed_quote=QUOTE,
        quote_hash=quote_hash(QUOTE), span_start_in_fragment=0,
        span_end_in_fragment=len(QUOTE), match_type="exact_normalized",
        retrieval_score=1.0, status="proposed", retrieval_algorithm_version="v1",
        generation_origin="deterministic_lexical",
    ))
    db.flush()
    _map(db, run, mapping_result(candidates=[candidate(frags[0], QUOTE)]))
    evidence_pipeline.run_verification(db, run)
    anchors = db.scalars(
        select(EvidenceAnchor).where(EvidenceAnchor.run_id == run.run_id)
    ).all()
    assert len(anchors) == 1  # one shared anchor, no duplicate


def test_workspace_isolation(db):
    run, frags, _ = build_run(db, fragments=[QUOTE], workspace_id="ws-demo")
    _map(db, run, mapping_result(candidates=[candidate(frags[0], QUOTE)]))
    cand = _agent_candidate(db, run)
    assert cand.workspace_id == "ws-demo"
