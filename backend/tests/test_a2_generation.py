"""A2 solution-innovation suggestion generation + validation (Milestone 9D)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agents import field_drafting
from app.agents.providers import FakeProvider
from app.db.models import ControlResult, DraftSuggestion
from app.db.session import SessionLocal
from tests.a2_helpers import (
    GOOD_TEXT,
    add_verified_anchor,
    bundle,
    build_run_with_draft,
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


def _run(db, run, draft, base, provider, *, operation_id="op-1"):
    return field_drafting.run_a2_solution_innovation(
        db, run, draft_id=draft.draft_id, base_version_id=base, operation_id=operation_id,
        provider_resolver=fake_resolver(provider),
    )


def _suggestions(db, run):
    return db.scalars(select(DraftSuggestion).where(DraftSuggestion.run_id == run.run_id)).all()


def test_valid_suggestion_persists(db):
    run, draft, base = build_run_with_draft(db)
    anchor = add_verified_anchor(db, run)
    out = _run(db, run, draft, base, success_fake(bundle(evidence_anchor_ids=[anchor])))
    assert out.status == "succeeded" and out.suggestion_id
    s = _suggestions(db, run)[0]
    assert s.status == "proposed" and s.field_id == "SOL.INNOVATION_SOLUTION.EDITOR"
    assert s.suggested_text == GOOD_TEXT and s.evidence_anchor_ids == [anchor]
    assert s.agent_invocation_id and s.content_hash and s.operation_id == "op-1"
    # The operation-result view is available for the frontend.
    assert out.view["character_limit"] == 25000 and out.view["suggested_text"] == GOOD_TEXT


def test_over_character_limit_rejected(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, success_fake(bundle(suggested_text="4.1 " + "x" * 26000)))
    assert out.status == "failed" and out.reason == "character_limit_exceeded"
    assert _suggestions(db, run) == []  # never persisted, never trimmed


def test_missing_mandatory_structure_rejected(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, success_fake(bundle(suggested_text="Only 4.1 and 4.2 here.")))
    assert out.status == "failed" and out.reason == "mandatory_structure_missing"
    assert _suggestions(db, run) == []


def test_invented_evidence_anchor_rejected(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, success_fake(bundle(evidence_anchor_ids=["GHOST-ANCHOR"])))
    assert out.status == "failed" and out.reason == "unknown_evidence_anchor"
    assert _suggestions(db, run) == []


def test_unknown_open_issue_rejected(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, success_fake(bundle(open_issue_ids=["NO-SUCH-ISSUE"])))
    assert out.status == "failed" and out.reason == "unknown_open_issue"


def test_empty_text_rejected(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, success_fake(bundle(suggested_text="   ")))
    assert out.status == "failed" and out.reason == "empty_suggested_text"


def test_malformed_output_safe_failure(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, FakeProvider(mode="malformed"))
    assert out.status in ("failed", "timed_out") and _suggestions(db, run) == []


def test_timeout_safe_failure(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, FakeProvider(mode="timeout"))
    assert out.status in ("failed", "timed_out") and _suggestions(db, run) == []


def test_deterministic_only_skips(db):
    run, draft, base = build_run_with_draft(db, processing_mode="deterministic_only")
    provider = success_fake(bundle())
    out = _run(db, run, draft, base, provider)
    assert out.status == "skipped" and provider.calls == 0 and _suggestions(db, run) == []


def test_confidential_blocked(db):
    run, draft, base = build_run_with_draft(db, sensitivity="confidential")
    provider = success_fake(bundle())
    out = _run(db, run, draft, base, provider)
    assert out.status == "blocked" and provider.calls == 0


def test_availability_no_mode_upgrade(db):
    run, _d, _b = build_run_with_draft(db, processing_mode="deterministic_only")
    available, reason = field_drafting.availability(
        run, "SOL.INNOVATION_SOLUTION.EDITOR"
    )
    assert available is False and reason == "processing_mode_deterministic_only"
    # The run's mode is unchanged (never upgraded).
    assert run.processing_mode == "deterministic_only"


def test_replay_reuses_existing_suggestion(db):
    run, draft, base = build_run_with_draft(db)
    first = _run(db, run, draft, base, success_fake(bundle()), operation_id="op-a")
    assert first.status == "succeeded"
    second_provider = success_fake(bundle())
    second = _run(db, run, draft, base, second_provider, operation_id="op-b")
    assert second.status == "reused" and second_provider.calls == 0
    assert len(_suggestions(db, run)) == 1


def test_fake_provider_flag_drives_default_resolver(db, monkeypatch):
    # With agent_fake_provider on and no explicit resolver, the orchestrator uses
    # the deterministic fake (dev/test affordance) and produces a valid suggestion.
    from app.config.settings import get_settings

    monkeypatch.setattr(get_settings(), "agent_fake_provider", True)
    run, draft, base = build_run_with_draft(db)
    out = field_drafting.run_a2_solution_innovation(
        db, run, draft_id=draft.draft_id, base_version_id=base, operation_id="op-fake",
    )
    assert out.status == "succeeded" and out.suggestion_id
    assert "4.5" in out.view["suggested_text"]


def test_evidence_requirement_control_recorded(db):
    run, draft, base = build_run_with_draft(db)
    out = _run(db, run, draft, base, success_fake(bundle()))
    ctrl = db.scalars(
        select(ControlResult).where(
            ControlResult.agent_invocation_id == out.invocation_id,
            ControlResult.control_id == "CTRL.EVIDENCE_REQUIREMENT",
        )
    ).all()
    assert ctrl and ctrl[0].status == "passed"
