"""R5.2 — AIProposal: Schema, Anchor-Regel, missing_inputs, Metering-Linkage.

Alles über FakeProvider — keine echten Provider-Calls.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agents import field_drafting
from app.agents.proposal import AIProposal, DraftProposal, proposal_anchor_violations
from app.db.models import AgentInvocation
from app.db.session import SessionLocal
from tests.a2_helpers import (
    GOOD_TEXT,
    add_verified_anchor,
    build_run_with_draft,
    bundle,
    fake_resolver,
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


def _run(db, run, draft, base, provider, *, operation_id="op-r52"):
    return field_drafting.run_a2_solution_innovation(
        db, run, draft_id=draft.draft_id, base_version_id=base,
        operation_id=operation_id, provider_resolver=fake_resolver(provider),
    )


def test_proposal_in_view_and_schema_valid(db):
    run, draft, base = build_run_with_draft(db)
    anchor = add_verified_anchor(db, run)
    out = _run(db, run, draft, base, success_fake(bundle(evidence_anchor_ids=[anchor])))
    assert out.status == "succeeded"
    raw = out.view["proposal"]
    proposal = DraftProposal.model_validate(raw)  # neutral view is schema-valid
    assert out.view["ai_proposal"] is None
    assert proposal.suggestion_text == GOOD_TEXT
    assert proposal.used_anchor_ids == [anchor]
    assert proposal.human_review_required is True
    assert proposal.profile_id == "A2.solution_innovation"
    assert proposal.prompt_version is None
    assert proposal.model_ref is None and proposal.provider is None and proposal.model is None
    assert proposal.generation_kind == "fake_demo"
    assert proposal.data_mode == "fake_test"  # AI_EVAL_MODE=off + origin=synthetic
    assert isinstance(raw["created_at"], str)  # ISO-serialisiert (JSON-Spalte)


def test_extra_field_rejected(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, success_fake(bundle()))
    dump = dict(out.view["proposal"])
    dump["auto_accept"] = True
    with pytest.raises(ValidationError):
        DraftProposal.model_validate(dump)


def test_human_review_required_cannot_be_false(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, success_fake(bundle()))
    dump = dict(out.view["proposal"])
    dump["human_review_required"] = False
    with pytest.raises(ValidationError):
        DraftProposal.model_validate(dump)


def test_unknown_anchor_ids_error(db):
    # Helper-Ebene …
    assert proposal_anchor_violations(["GHOST"], {"a1", "a2"}) == ["GHOST"]
    assert proposal_anchor_violations(["a1"], {"a1"}) == []
    # … und Flow-Ebene: erfundener Anchor ⇒ kein Proposal, klarer Fehler.
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, success_fake(bundle(evidence_anchor_ids=["GHOST"])))
    assert out.status == "failed" and out.reason == "unknown_evidence_anchor"
    assert out.view is None


def test_missing_inputs_accepted(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, success_fake(bundle(
        placeholders=[{"label": "[Marktzahl fehlt]", "reason": "missing_market_data"}],
    )))
    assert out.status == "succeeded"
    proposal = DraftProposal.model_validate(out.view["proposal"])
    assert proposal.missing_inputs[0].label == "[Marktzahl fehlt]"
    assert proposal.missing_inputs[0].reason == "missing_market_data"
    assert "contains_placeholders" in proposal.safety_notes


def test_usage_record_and_context_hash_linkage(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, success_fake(bundle()))
    assert out.status == "succeeded"
    raw = out.view["proposal"]
    inv = db.get(AgentInvocation, out.invocation_id)
    assert inv.usage_record_id  # EVAL.1-Metering griff automatisch
    assert raw["usage_record_id"] is None
    assert raw["context_hash"] == inv.context_meta["context_hash"]
    # usage_record_id ist optional: Auslassung bleibt schema-valid.
    without = {k: v for k, v in raw.items() if k != "usage_record_id"}
    assert DraftProposal.model_validate(without).usage_record_id is None
    with pytest.raises(ValidationError):
        AIProposal.model_validate(raw)  # Fake-Demo darf nie als KI-Proposal gelten.


def test_reused_view_carries_proposal(db):
    run, draft, base = build_run_with_draft(db)
    first = _run(db, run, draft, base, success_fake(bundle()))
    assert first.status == "succeeded"
    second = _run(db, run, draft, base, success_fake(bundle()), operation_id="op-r52b")
    assert second.status == "reused"
    proposal = DraftProposal.model_validate(second.view["proposal"])
    assert second.view["ai_proposal"] is None
    assert proposal.human_review_required is True
    assert proposal.suggestion_text == GOOD_TEXT
