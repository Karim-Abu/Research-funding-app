"""A1 evidence-candidate validation + agent-origin persistence (Milestone 9C)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import evidence_mapping
from app.db.models import AgentEvidenceProposal, EvidenceCandidate
from app.db.session import SessionLocal
from app.repositories import evidence as evidence_repo
from tests.a1_mapping_helpers import (
    FIELD_ID,
    REQ_ID,
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


def _run(db, run, payload):
    return evidence_mapping.run_a1_evidence_mapping(
        db, run, provider_resolver=fake_resolver(success_fake(payload))
    )


def _candidates(db, run):
    return db.scalars(
        select(EvidenceCandidate).where(EvidenceCandidate.run_id == run.run_id)
    ).all()


def test_valid_candidate_persists_with_agent_origin(db):
    run, frags, sv = build_run(db, fragments=[QUOTE])
    out = _run(db, run, mapping_result(candidates=[candidate(frags[0], QUOTE)]))
    assert out.status == "succeeded" and out.candidates_persisted == 1
    cand = _candidates(db, run)[0]
    assert cand.generation_origin == "agent_a1_evidence_mapping"
    assert cand.target_requirement_id == REQ_ID and cand.match_type == "exact_normalized"
    assert cand.agent_invocation_id and cand.prompt_version
    # span derived deterministically → quote sits at the recorded offsets.
    assert cand.span_start_in_fragment == 0 and cand.span_end_in_fragment == len(QUOTE)


def test_quote_must_exist_in_fragment(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    out = _run(db, run, mapping_result(
        candidates=[candidate(frags[0], "A paraphrased partner statement.")]
    ))
    assert out.status == "succeeded" and out.candidates_persisted == 0
    assert out.candidates_rejected == 1 and _candidates(db, run) == []


def test_out_of_snapshot_fragment_rejected(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    out = _run(db, run, mapping_result(candidates=[candidate("GHOST", QUOTE)]))
    assert out.candidates_persisted == 0 and out.candidates_rejected == 1


def test_unknown_requirement_target_rejected(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    out = _run(db, run, mapping_result(
        candidates=[candidate(frags[0], QUOTE, target_id="REQ.NOPE")]
    ))
    assert out.candidates_persisted == 0 and out.candidates_rejected == 1


def test_portal_field_target_not_persisted(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    out = _run(db, run, mapping_result(
        candidates=[candidate(frags[0], QUOTE, target_type="portal_field", target_id=FIELD_ID)]
    ))
    # Field targets have no candidate/verify/link path in M9C → rejected, not persisted.
    assert out.candidates_persisted == 0 and _candidates(db, run) == []


def test_ambiguous_quote_rejected(db):
    # "ab" occurs twice → span cannot be derived unambiguously → rejected.
    run, frags, _ = build_run(db, fragments=["ab cd ab"])
    out = _run(db, run, mapping_result(candidates=[candidate(frags[0], "ab")]))
    assert out.candidates_persisted == 0 and out.candidates_rejected == 1


def test_no_exact_verified_or_human_verified_from_model(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    _run(db, run, mapping_result(candidates=[candidate(frags[0], QUOTE)]))
    cand = _candidates(db, run)[0]
    # The agent only proposes; the candidate is plain "proposed" with no anchor yet.
    assert cand.status == "proposed" and cand.anchor_id is None


def test_duplicate_of_deterministic_not_duplicated(db):
    run, frags, sv = build_run(db, fragments=[QUOTE])
    # Pre-seed a deterministic candidate identical to what the agent will propose.
    from app.evidence.discovery import quote_hash
    det_candidate = EvidenceCandidate(
        candidate_id="det-1", run_id=run.run_id, workspace_id=run.workspace_id,
        target_type="requirement", target_requirement_id=REQ_ID, fragment_id=frags[0],
        source_version_id=sv, source_id="src", proposed_quote=QUOTE,
        quote_hash=quote_hash(QUOTE), span_start_in_fragment=0,
        span_end_in_fragment=len(QUOTE), match_type="exact_normalized",
        retrieval_score=1.0, status="proposed", retrieval_algorithm_version="v1",
        generation_origin="deterministic_lexical",
    )
    db.add(det_candidate)
    db.flush()

    out = _run(db, run, mapping_result(candidates=[candidate(frags[0], QUOTE)]))
    assert out.candidates_persisted == 0 and out.candidates_deduplicated == 1
    # Only the single deterministic candidate exists — no agent duplicate.
    assert len(_candidates(db, run)) == 1
    proposal = db.scalar(
        select(AgentEvidenceProposal).where(
            AgentEvidenceProposal.run_id == run.run_id,
            AgentEvidenceProposal.outcome == "deduplicated",
        )
    )
    assert proposal.existing_candidate_id == "det-1"
    assert proposal.duplicate_of_deterministic is True


def test_per_target_cap_enforced(db):
    # 6 distinct exact quotes for the same requirement → only 5 persist (cap).
    quotes = [f"Quote number {i} about the partner. " for i in range(6)]
    run, frags, _ = build_run(db, fragments=quotes)
    cands = [candidate(frags[i], quotes[i]) for i in range(6)]
    out = _run(db, run, mapping_result(candidates=cands))
    assert out.candidates_persisted == 5 and out.candidates_rejected == 1
