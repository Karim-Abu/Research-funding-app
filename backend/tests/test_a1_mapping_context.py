"""A1 evidence-mapping context assembly (Milestone 9C)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import context as a1_context
from app.db.models import ToolInvocation
from app.db.session import SessionLocal
from tests.a1_mapping_helpers import add_fact, build_run

QUOTE = "The Swiss implementation partner is based in Zurich."


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def test_context_includes_run_facts_and_snapshot_fragments(db):
    run, frags, _ = build_run(db, fragments=[QUOTE, "Second fragment."])
    add_fact(db, run, statement="A proposed project fact.")
    ctx = a1_context.assemble_evidence_mapping_context(db, run, max_fragments=80)
    assert set(ctx.selected_fragment_ids) == set(frags)  # only snapshot fragments
    assert len(ctx.extracted_facts) == 1
    assert ctx.requirement_defs and ctx.field_defs


def test_context_hash_and_counts(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    ctx = a1_context.assemble_evidence_mapping_context(db, run, max_fragments=80)
    assert ctx.context_hash and ctx.meta["context_hash"] == ctx.context_hash
    assert ctx.meta["selected_fragment_count"] == 1
    assert "char_budget" in ctx.meta


def test_char_budget_truncates_at_fragment_boundary(db, monkeypatch):
    from app.config.settings import get_settings

    run, frags, _ = build_run(db, fragments=["A" * 100, "B" * 100, "C" * 100])
    monkeypatch.setattr(get_settings(), "a1_context_char_budget", 150)
    ctx = a1_context.assemble_evidence_mapping_context(db, run, max_fragments=80)
    # First fragment fits; the next would exceed 150 chars → boundary truncation
    # (never mid-fragment).
    assert ctx.meta["selected_fragment_count"] == 1
    assert ctx.meta["skipped_fragment_count"] == 2


def test_max_fragments_cap(db, monkeypatch):
    run, frags, _ = build_run(db, fragments=["frag one. ", "frag two. ", "frag three. "])
    ctx = a1_context.assemble_evidence_mapping_context(db, run, max_fragments=2)
    assert ctx.meta["selected_fragment_count"] == 2


def test_tool_invocations_recorded_under_mapping_profile(db):
    run, frags, _ = build_run(db, fragments=[QUOTE])
    a1_context.assemble_evidence_mapping_context(db, run, max_fragments=80)
    db.flush()
    tools = db.scalars(
        select(ToolInvocation).where(
            ToolInvocation.run_id == run.run_id,
            ToolInvocation.caller == "A1.evidence_candidate_mapping",
        )
    ).all()
    tool_ids = {t.tool_id for t in tools}
    assert tool_ids == {
        "retrieve_source_fragments", "lookup_requirement_definition",
        "lookup_portal_field_profile",
    }
