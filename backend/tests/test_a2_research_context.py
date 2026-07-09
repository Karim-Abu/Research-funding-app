"""R5.7 — A2 Value Creation + Solution mit advisory Research-Kontext (fake provider only).

Research context (imported D0/public sources + non-imported ResearchResult candidates) is
advisory only: it flows into the A2 context_text, is field-scoped by ResearchTask.purpose
(VC ← market_comparison, SOL ← partner_research_org_topic), and NEVER becomes an evidence
anchor. A candidate/source id can never appear in used_anchor_ids; missing market/SOTA/
baseline evidence must surface as missing_inputs. Non-VC/SOL fields get no research block.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import field_drafting
from app.agents.field_drafting_context import (
    assemble_a2_context,
    retrieve_advisory_research_context,
)
from app.agents.proposal import AIProposal
from app.db.models import AgentInvocation, DraftSuggestion
from app.db.session import SessionLocal
from tests.a2_helpers import (
    FIELD_ID as SOL_FIELD_ID,
    GOOD_TEXT as SOL_GOOD_TEXT,
    MARKET_PURPOSE,
    PARTNER_PURPOSE,
    VC_FIELD_ID,
    VC_GOOD_TEXT,
    add_imported_public_source,
    add_research_candidate,
    add_verified_anchor,
    build_run_with_draft,
    bundle,
    fake_resolver,
    success_fake,
)

VC_PROFILE = "A2.value_creation_market_logic"
SOL_PROFILE = "A2.solution_innovation"


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _vc_draft(db, **kw):
    return build_run_with_draft(
        db, field_id=VC_FIELD_ID, character_limit=15000, field_name="Value Creation",
        draft_text="3.1 ... 3.2 ...", **kw,
    )


def _sol_draft(db, **kw):
    return build_run_with_draft(db, field_id=SOL_FIELD_ID, **kw)


def _run(db, run, draft, base, field_id, provider, op="op-rc"):
    return field_drafting.run_a2_field_drafting(
        db, run, field_id=field_id, draft_id=draft.draft_id, base_version_id=base,
        operation_id=op, provider_resolver=fake_resolver(provider),
    )


def _vc_bundle(**kw):
    kw.setdefault("suggested_text", VC_GOOD_TEXT)
    return bundle(field_id=VC_FIELD_ID, **kw)


def _sol_bundle(**kw):
    kw.setdefault("suggested_text", SOL_GOOD_TEXT)
    return bundle(field_id=SOL_FIELD_ID, **kw)


# --- purpose-scoped gating (context assembly) --------------------------------


def test_vc_context_is_market_scoped(db):
    run, _draft, _base = _vc_draft(db)
    market = add_research_candidate(db, run, purpose=MARKET_PURPOSE,
                                    title="Marktkandidat Alpha")
    add_research_candidate(db, run, purpose=PARTNER_PURPOSE, title="Partnerkandidat Beta")
    rc = retrieve_advisory_research_context(db, run, VC_PROFILE)
    titles = " ".join(c["title"] for c in rc["candidates"])
    assert "Marktkandidat Alpha" in titles
    assert "Partnerkandidat Beta" not in titles  # partner candidate filtered out for VC
    assert market  # sanity


def test_sol_context_is_partner_scoped(db):
    run, _draft, _base = _sol_draft(db)
    add_research_candidate(db, run, purpose=MARKET_PURPOSE, title="Marktkandidat Alpha")
    add_research_candidate(db, run, purpose=PARTNER_PURPOSE, title="Partnerkandidat Beta")
    rc = retrieve_advisory_research_context(db, run, SOL_PROFILE)
    titles = " ".join(c["title"] for c in rc["candidates"])
    assert "Partnerkandidat Beta" in titles
    assert "Marktkandidat Alpha" not in titles


def test_non_vc_sol_field_gets_no_research_block(db):
    run, _draft, _base = _vc_draft(db)
    add_research_candidate(db, run, purpose=MARKET_PURPOSE, title="Marktkandidat Alpha")
    # Abstract profile is not in the research map → no research context, empty dict.
    assert retrieve_advisory_research_context(db, run, "A2.introduction_public_summary") == {}
    ctx = assemble_a2_context(db, run, field_id="INTRO.APP.ABSTRACT",
                              profile_id="A2.introduction_public_summary")
    assert "RESEARCH CONTEXT" not in ctx.context_text
    assert ctx.research_context == {}


def test_vc_context_includes_imported_source_and_marks_advisory(db):
    run, _draft, _base = _vc_draft(db)
    add_imported_public_source(db, run, name="Marktbericht öffentlich",
                               text="Markt und Wettbewerber wachsen; Umsatz ca. 12 Mio.")
    ctx = assemble_a2_context(db, run, field_id=VC_FIELD_ID, profile_id=VC_PROFILE)
    assert "RESEARCH CONTEXT" in ctx.context_text
    assert "NOT evidence" in ctx.context_text
    assert ctx.meta["research_context_count"] >= 1


# --- candidate/source can never be evidence ----------------------------------


def test_vc_research_candidate_cannot_be_cited_as_evidence(db):
    run, draft, base = _vc_draft(db)
    result_id = add_research_candidate(db, run, purpose=MARKET_PURPOSE)
    # Model tries to cite the candidate id as an evidence anchor → rejected, no persistence.
    out = _run(db, run, draft, base, VC_FIELD_ID,
               success_fake(_vc_bundle(evidence_anchor_ids=[result_id])))
    assert out.status == "failed" and out.reason == "unknown_evidence_anchor"
    assert db.scalar(
        select(DraftSuggestion).where(DraftSuggestion.run_id == run.run_id)
    ) is None


def test_sol_partner_candidate_cannot_be_cited_as_evidence(db):
    run, draft, base = _sol_draft(db)
    result_id = add_research_candidate(db, run, purpose=PARTNER_PURPOSE)
    out = _run(db, run, draft, base, SOL_FIELD_ID,
               success_fake(_sol_bundle(evidence_anchor_ids=[result_id])))
    assert out.status == "failed" and out.reason == "unknown_evidence_anchor"


def test_vc_imported_source_number_is_not_an_anchor(db):
    run, draft, base = _vc_draft(db)
    add_imported_public_source(db, run, text="Markt wächst; Umsatz ca. 12 Mio.")
    # A clean draft that keeps the number only as a placeholder; no anchors cited.
    out = _run(db, run, draft, base, VC_FIELD_ID, success_fake(_vc_bundle()))
    assert out.status == "succeeded"
    proposal = AIProposal.model_validate(out.view["ai_proposal"])
    assert proposal.used_anchor_ids == []  # the market number never became an anchor


# --- missing evidence → missing_inputs (Rule 6) ------------------------------


def test_vc_missing_market_evidence_becomes_missing_inputs(db):
    run, draft, base = _vc_draft(db)
    # Only a candidate exists (no verified anchor); the draft marks the gap → missing_inputs.
    add_research_candidate(db, run, purpose=MARKET_PURPOSE)
    out = _run(db, run, draft, base, VC_FIELD_ID, success_fake(_vc_bundle(
        placeholders=[{"label": "Marktgrösse", "reason": "kein Beleg, nur Kandidat"}],
    )))
    assert out.status == "succeeded"
    proposal = AIProposal.model_validate(out.view["ai_proposal"])
    assert proposal.missing_inputs and proposal.missing_inputs[0].label == "Marktgrösse"
    assert "contains_placeholders" in proposal.safety_notes


@pytest.mark.parametrize("label", ["State of the Art", "Baseline", "Validierungsmethode"])
def test_sol_missing_solution_evidence_becomes_missing_inputs(db, label):
    run, draft, base = _sol_draft(db)
    add_research_candidate(db, run, purpose=PARTNER_PURPOSE)
    out = _run(db, run, draft, base, SOL_FIELD_ID, success_fake(_sol_bundle(
        placeholders=[{"label": label, "reason": "kein Beleg vorhanden"}],
    )))
    assert out.status == "succeeded"
    proposal = AIProposal.model_validate(out.view["ai_proposal"])
    assert proposal.missing_inputs[0].label == label


# --- AIProposal shape + only own profile -------------------------------------


def test_vc_ai_proposal_shape_and_allowed_anchor(db):
    run, draft, base = _vc_draft(db)
    add_research_candidate(db, run, purpose=MARKET_PURPOSE)
    anchor_id = add_verified_anchor(db, run)
    out = _run(db, run, draft, base, VC_FIELD_ID,
               success_fake(_vc_bundle(evidence_anchor_ids=[anchor_id])))
    assert out.status == "succeeded"
    proposal = AIProposal.model_validate(out.view["ai_proposal"])
    assert proposal.human_review_required is True
    assert proposal.used_anchor_ids == [anchor_id]  # only the real verified anchor
    assert proposal.usage_record_id is not None
    assert proposal.data_mode
    # Only the VC profile was invoked — no SOL, no A3.
    profiles = {i.profile_id for i in db.scalars(
        select(AgentInvocation).where(AgentInvocation.run_id == run.run_id)
    )}
    assert SOL_PROFILE not in profiles
    assert not any(p.startswith("A3") for p in profiles)
