"""R5.7/R8 — A2 Value Creation + Solution mit advisory Research-Kontext (fake provider only).

R8 (Anforderung 10): NUR vom Menschen akzeptierte (importierte) D0/public-Quellen werden
A2-Kontext; nicht importierte ResearchResult-Kandidaten und verworfene Ergebnisse nie.
Research context is advisory only: it flows into the A2 context_text and NEVER becomes an
evidence anchor. A candidate/source id can never appear in used_anchor_ids; missing
market/SOTA/baseline evidence must surface as missing_inputs. Non-VC/SOL fields get no
research block.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import field_drafting
from app.agents.field_drafting_context import (
    assemble_a2_context,
    retrieve_advisory_research_context,
)
from app.agents.proposal import DraftProposal
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
    fake_resolver,
    section_bundle,
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
        draft_text=VC_GOOD_TEXT, **kw,
    )


def _sol_draft(db, **kw):
    return build_run_with_draft(db, field_id=SOL_FIELD_ID, **kw)


def _run(db, run, draft, base, field_id, provider, op="op-rc"):
    target_section = "3.2" if field_id == VC_FIELD_ID else "4.2"
    return field_drafting.run_a2_field_drafting(
        db, run, field_id=field_id, draft_id=draft.draft_id, base_version_id=base,
        operation_id=op, target_section=target_section,
        provider_resolver=fake_resolver(provider),
    )


def _vc_bundle(**kw):
    kw.setdefault("suggested_text", "3.2 Geschäftsmodell und Markt: Zielkunden [offen].")
    return section_bundle(
        field_id=VC_FIELD_ID, target_section="3.2", **kw
    )


def _sol_bundle(**kw):
    kw.setdefault("suggested_text", "4.2 Neuheit: klare Abgrenzung [offen].")
    return section_bundle(
        field_id=SOL_FIELD_ID, target_section="4.2", **kw
    )


# --- R8: nur akzeptierte (importierte) Quellen werden Kontext -----------------


def test_candidates_never_enter_context_until_imported(db):
    """R8 (Anforderung 10): nicht importierte ResearchResult-Kandidaten fliessen
    NICHT mehr in den A2-Kontext — für kein Profil."""
    run, _draft, _base = _vc_draft(db)
    add_research_candidate(db, run, purpose=MARKET_PURPOSE, title="Marktkandidat Alpha")
    add_research_candidate(db, run, purpose=PARTNER_PURPOSE, title="Partnerkandidat Beta")
    assert retrieve_advisory_research_context(db, run, VC_PROFILE) == {}
    assert retrieve_advisory_research_context(db, run, SOL_PROFILE) == {}
    ctx = assemble_a2_context(db, run, field_id=VC_FIELD_ID, profile_id=VC_PROFILE)
    assert "Marktkandidat Alpha" not in ctx.context_text
    assert "Marktkandidat Alpha" not in ctx.context_text


def test_reviewed_supporting_source_enters_context_and_discarded_never(db):
    run, _draft, _base = _vc_draft(db)
    add_imported_public_source(db, run, name="Akzeptierter Marktbericht",
                               text="Markt und Wettbewerber wachsen stark.")
    add_research_candidate(db, run, purpose=MARKET_PURPOSE, title="Offener Kandidat")
    discarded = add_research_candidate(db, run, purpose=MARKET_PURPOSE,
                                       title="Verworfener Kandidat")
    from app.db.models import ResearchResult
    db.get(ResearchResult, discarded).status = "rejected"
    db.flush()
    rc = retrieve_advisory_research_context(db, run, VC_PROFILE)
    names = " ".join(s["source_name"] for s in rc["imported_sources"])
    assert "Akzeptierter Marktbericht" in names
    assert "candidates" not in rc
    ctx = assemble_a2_context(db, run, field_id=VC_FIELD_ID, profile_id=VC_PROFILE)
    assert "Offener Kandidat" not in ctx.context_text
    assert "Verworfener Kandidat" not in ctx.context_text


@pytest.mark.parametrize(
    ("content_review_status", "support_status", "result_status"),
    [
        ("unreviewed", "not_checked", "imported"),
        ("reviewed", "does_not_support", "rejected"),
        ("reviewed", "does_not_support", "imported"),
    ],
)
def test_unreviewed_rejected_or_non_supporting_source_never_enters_context(
    db, content_review_status, support_status, result_status
):
    run, _draft, _base = _vc_draft(db)
    add_imported_public_source(
        db,
        run,
        name="Nicht zulässige Research-Quelle",
        content_review_status=content_review_status,
        support_status=support_status,
        result_status=result_status,
    )
    assert retrieve_advisory_research_context(db, run, VC_PROFILE) == {}


def test_partially_supporting_reviewed_source_enters_context(db):
    run, _draft, _base = _vc_draft(db)
    add_imported_public_source(
        db,
        run,
        name="Teilweise stützende Quelle",
        support_status="partially_supports",
    )
    context = retrieve_advisory_research_context(db, run, VC_PROFILE)
    assert context["imported_sources"][0]["support_status"] == "partially_supports"
    assert context["imported_sources"][0]["content_review_status"] == "reviewed"


@pytest.mark.parametrize(
    ("execution_mode", "document_status", "version_status"),
    [
        ("fake_demo", "processed", "processed"),
        ("live", "processing", "processed"),
        ("live", "processed", "pending"),
    ],
)
def test_non_live_or_incomplete_source_never_enters_context(
    db, execution_mode, document_status, version_status
):
    run, _draft, _base = _vc_draft(db)
    add_imported_public_source(
        db,
        run,
        execution_mode=execution_mode,
        document_status=document_status,
        version_status=version_status,
    )
    assert retrieve_advisory_research_context(db, run, VC_PROFILE) == {}


def test_non_vc_sol_field_gets_no_research_block(db):
    run, _draft, _base = _vc_draft(db)
    add_research_candidate(db, run, purpose=MARKET_PURPOSE, title="Marktkandidat Alpha")
    # Abstract profile is not in the research map → no research context, empty dict.
    assert retrieve_advisory_research_context(db, run, "A2.introduction_public_summary") == {}
    ctx = assemble_a2_context(db, run, field_id="INTRO.APP.ABSTRACT",
                              profile_id="A2.introduction_public_summary")
    assert "[research_candidate]" in ctx.context_text
    assert ctx.research_context == {}


def test_vc_context_includes_imported_source_and_marks_advisory(db):
    run, _draft, _base = _vc_draft(db)
    add_imported_public_source(db, run, name="Marktbericht öffentlich",
                               text="Markt und Wettbewerber wachsen; Umsatz ca. 12 Mio.")
    ctx = assemble_a2_context(db, run, field_id=VC_FIELD_ID, profile_id=VC_PROFILE)
    assert "[research_candidate]" in ctx.context_text
    assert "Marktbericht öffentlich" in ctx.context_text
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
    proposal = DraftProposal.model_validate(out.view["proposal"])
    assert out.view["ai_proposal"] is None
    assert proposal.used_anchor_ids == []  # the market number never became an anchor


def test_used_research_source_is_subset_checked_and_visible_separately(db):
    run, draft, base = _vc_draft(db)
    source_id = add_imported_public_source(
        db, run, name="Live market report",
        text="Market competitors serve manufacturing customers.",
    )
    out = _run(
        db, run, draft, base, VC_FIELD_ID,
        success_fake(_vc_bundle(research_source_ids=[source_id])),
    )
    assert out.status == "succeeded"
    proposal = DraftProposal.model_validate(out.view["proposal"])
    assert proposal.used_research_source_ids == [source_id]
    assert proposal.used_anchor_ids == []
    assert out.view["research_sources"] == [{
        "source_id": source_id,
        "title": "Live market report",
        "url": "https://public.example.test/research",
        "research_module": "competition_alternatives",
        "support_status": "supports",
        "content_review_status": "reviewed",
    }]

    other_run, other_draft, other_base = _vc_draft(db)
    rejected = _run(
        db, other_run, other_draft, other_base, VC_FIELD_ID,
        success_fake(_vc_bundle(research_source_ids=["unknown-source"])),
        op="op-unknown-research-source",
    )
    assert rejected.status == "failed"
    assert rejected.reason == "unknown_research_source"


# --- missing evidence → missing_inputs (Rule 6) ------------------------------


def test_vc_missing_market_evidence_becomes_missing_inputs(db):
    run, draft, base = _vc_draft(db)
    # Only a candidate exists (no verified anchor); the draft marks the gap → missing_inputs.
    add_research_candidate(db, run, purpose=MARKET_PURPOSE)
    out = _run(db, run, draft, base, VC_FIELD_ID, success_fake(_vc_bundle(
        missing_inputs=[{"label": "Marktgrösse", "reason": "kein Beleg, nur Kandidat"}],
    )))
    assert out.status == "succeeded"
    proposal = DraftProposal.model_validate(out.view["proposal"])
    assert proposal.missing_inputs and proposal.missing_inputs[0].label == "Marktgrösse"
    assert "contains_placeholders" in proposal.safety_notes


@pytest.mark.parametrize("label", ["State of the Art", "Baseline", "Validierungsmethode"])
def test_sol_missing_solution_evidence_becomes_missing_inputs(db, label):
    run, draft, base = _sol_draft(db)
    add_research_candidate(db, run, purpose=PARTNER_PURPOSE)
    out = _run(db, run, draft, base, SOL_FIELD_ID, success_fake(_sol_bundle(
        missing_inputs=[{"label": label, "reason": "kein Beleg vorhanden"}],
    )))
    assert out.status == "succeeded"
    proposal = DraftProposal.model_validate(out.view["proposal"])
    assert proposal.missing_inputs[0].label == label


# --- AIProposal shape + only own profile -------------------------------------


def test_vc_demo_proposal_shape_and_allowed_anchor(db):
    run, draft, base = _vc_draft(db)
    add_research_candidate(db, run, purpose=MARKET_PURPOSE)
    anchor_id = add_verified_anchor(db, run)
    out = _run(db, run, draft, base, VC_FIELD_ID,
               success_fake(_vc_bundle(evidence_anchor_ids=[anchor_id])))
    assert out.status == "succeeded"
    proposal = DraftProposal.model_validate(out.view["proposal"])
    assert out.view["ai_proposal"] is None
    assert proposal.human_review_required is True
    assert proposal.used_anchor_ids == [anchor_id]  # only the real verified anchor
    assert proposal.usage_record_id is None
    assert proposal.generation_kind == "fake_demo"
    assert proposal.data_mode
    # Only the VC profile was invoked — no SOL, no A3.
    profiles = {i.profile_id for i in db.scalars(
        select(AgentInvocation).where(AgentInvocation.run_id == run.run_id)
    )}
    assert SOL_PROFILE not in profiles
    assert not any(p.startswith("A3") for p in profiles)
