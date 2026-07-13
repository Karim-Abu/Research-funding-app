"""Milestone 9G — A3 evidence-consistency review (fake provider only).

Activates exactly one A3 profile; advisory ReviewFindings only. Covers context scope,
eligibility, output validation, agent-finding persistence/dedup, approval gating, and
the recheck integration (resolve-only-on-success + recheck clears recheck_required).
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.agents import critic_review
from app.agents import critic_review_context as a3_context
from app.agents.a3_review import A3_PROFILE_ID
from app.agents.providers import FakeProvider
from app.config.settings import get_settings
from app.db.models import ReviewApproval, ReviewFinding
from app.db.session import SessionLocal
from app.review import package as review_package
from app.review.recheck import _maybe_run_a3
from tests.a2_helpers import (
    VC_FIELD_ID,
    GOOD_TEXT,
    add_verified_anchor,
    build_run_with_draft,
    fake_resolver,
)

SOL = "SOL.INNOVATION_SOLUTION.EDITOR"


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _sol_run(db, **kw):
    return build_run_with_draft(db, field_id=SOL, character_limit=25000,
                                field_name="Innovation Solution",
                                draft_text=GOOD_TEXT, **kw)


def _a3_bundle(field_id=SOL, severity="warning", **extra):
    target_section = "3.2" if field_id == VC_FIELD_ID else "4.2"
    finding = {"origin_profile_id": A3_PROFILE_ID, "severity": severity, "status": "open",
               "field_id": field_id, "target_section": target_section,
               "description": "Aussage ohne verknüpften Beleg.",
               "recommended_next_action": "Beleg ergänzen oder Aussage markieren."}
    finding.update(extra)
    return {"findings": [finding],
            "profile_summaries": [{"profile_id": A3_PROFILE_ID}], "overall_limitations": []}


def _resolver(bundle):
    return fake_resolver(FakeProvider(raw_output=json.dumps(bundle)))


def _run_a3(db, run, bundle=None):
    return critic_review.run_a3_evidence_consistency(
        db, run, provider_resolver=_resolver(bundle or _a3_bundle()),
    )


# --- context ---------------------------------------------------------------


def test_context_scopes_to_drafts_and_confirmed_facts_empty(db):
    run, _d, _b = _sol_run(db)
    ctx = a3_context.assemble_critic_context(db, run)
    assert ctx is not None
    assert ctx.allowed_field_ids == {
        SOL,
        "PS.RISK_MANAGEMENT.SECTION",
    }  # scoped draft plus the advisory risk-register target
    # corr 1: proposed A1 facts are NEVER passed as confirmed.
    assert ctx.payload["confirmed_facts"] == []
    assert ctx.context_hash


def test_scope_empty_skips(db):
    # A run whose drafts are not in A3 scope → no scoped draft content.
    run, _d, _b = build_run_with_draft(db, field_id="INTRO.APP.ABSTRACT", character_limit=2000,
                                       field_name="Abstract", draft_text="Some abstract.")
    ctx = a3_context.assemble_critic_context(db, run)
    assert ctx is None
    out = critic_review.run_a3_evidence_consistency(db, run, provider_resolver=_resolver(_a3_bundle()))
    assert out.status == "skipped" and out.reason == "scope_empty"


# --- eligibility -----------------------------------------------------------


def test_availability_deterministic_unavailable(db):
    run, _d, _b = _sol_run(db, processing_mode="deterministic_only")
    ok, reason = critic_review.availability(run)
    assert ok is False and reason == "processing_mode_deterministic_only"


def test_availability_confidential_blocked(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_fake_provider", True)
    run, _d, _b = _sol_run(db, sensitivity="confidential")
    ok, _ = critic_review.availability(run)
    assert ok is False


def test_availability_cloud_fake_available(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_fake_provider", True)
    run, _d, _b = _sol_run(db)
    ok, reason = critic_review.availability(run)
    assert ok is True and reason == "available"


# --- output validation -----------------------------------------------------


def test_eligible_run_yields_findings(db):
    run, _d, _b = _sol_run(db)
    out = _run_a3(db, run)
    assert out.status == "succeeded"
    assert len(out.findings) == 1 and out.findings[0].field_id == SOL


@pytest.mark.parametrize(
    ("target_section", "draft_text", "description", "action"),
    [
        (
            "4.3",
            GOOD_TEXT.replace("4.3 Ziele: messbar mit Baseline.", "4.3 Ziel: besser werden."),
            "Textstelle 'Ziel: besser werden': Baseline, Zielwert, Messmethode/Datenquelle und Validierungsmoment fehlen.",
            "KPI-Kette mit den vier fehlenden Elementen ergänzen; unbekannte Werte als offene Inputs belassen.",
        ),
        (
            "4.1",
            GOOD_TEXT.replace("4.1 Stand der Technik: bestehende Verfahren.", "4.1 Unsere Lösung ist einzigartig."),
            "Textstelle 'Unsere Lösung ist einzigartig': konkrete SOTA-Vergleichsbasis und Differenzierungsmerkmal fehlen.",
            "Vergleichsverfahren und projektspezifisches Differenzierungsmerkmal benennen und belegen.",
        ),
        (
            "4.3",
            GOOD_TEXT.replace(
                "4.3 Ziele: messbar mit Baseline.", "4.3 Zielwert 40."
            ).replace(
                "4.4 Vorarbeiten: abgeschlossene Vorstudien.",
                "4.4 Die Vorstudie verwendet Zielwert 60.",
            ),
            "Textstelle 'Zielwert 40' widerspricht dem Zielwert 60 in Abschnitt 4.4.",
            "Bezugsgröße und gültigen Zielwert klären und beide Abschnitte konsistent korrigieren.",
        ),
    ],
)
def test_a3_returns_concrete_kpi_sota_and_number_findings(
    db, target_section, draft_text, description, action
):
    run, _draft, _base = build_run_with_draft(
        db, field_id=SOL, character_limit=25000,
        field_name="Innovation Solution", draft_text=draft_text,
    )
    out = _run_a3(
        db,
        run,
        bundle=_a3_bundle(
            target_section=target_section,
            description=description,
            recommended_next_action=action,
        ),
    )
    assert out.status == "succeeded"
    assert len(out.findings) == 1
    finding = out.findings[0]
    assert finding.target_section == target_section
    assert finding.description == description
    assert finding.recommended_next_action == action


def test_invalid_field_dropped(db):
    run, _d, _b = _sol_run(db)
    out = _run_a3(db, run, bundle=_a3_bundle(field_id="INTRO.APP.ABSTRACT"))
    assert out.status == "succeeded" and out.findings == []  # out-of-scope dropped


def test_invalid_evidence_anchor_dropped(db):
    run, _d, _b = _sol_run(db)
    out = _run_a3(db, run, bundle=_a3_bundle(evidence_anchor_id="anchor-nope"))
    assert out.status == "succeeded" and out.findings == []


def test_exact_anchor_without_support_decision_is_not_external_evidence(db):
    run, _d, _b = _sol_run(db)
    anchor_id = add_verified_anchor(db, run, supported=False)
    out = _run_a3(db, run, bundle=_a3_bundle(evidence_anchor_id=anchor_id))
    assert out.status == "succeeded" and out.findings == []


def test_approval_finding_rejected_by_schema(db):
    run, _d, _b = _sol_run(db)
    bad = {"findings": [{"origin_profile_id": A3_PROFILE_ID, "severity": "info",
                         "status": "open", "field_id": SOL, "description": "x",
                         "target_section": "4.2",
                         "approval": "approved"}],
           "profile_summaries": []}
    out = _run_a3(db, run, bundle=bad)
    # extra="forbid" → gateway schema failure → SafeFailure → no findings.
    assert out.status in ("failed", "blocked") and out.findings == []


# --- persistence / dedup / gating ------------------------------------------
# A3 enforces CostGuard max_per_run_bundle=1, so persistence/dedup is exercised by
# applying constructed A3Finding objects directly (no second gateway invocation).


def _finding(field_id=SOL, severity="warning", description="Aussage ohne verknüpften Beleg."):
    return critic_review.A3Finding(
        origin_profile_id=A3_PROFILE_ID, severity=severity, status="open",
        description=description, field_id=field_id,
        target_section="3.2" if field_id == VC_FIELD_ID else "4.2",
    )


def _apply(db, run, *findings):
    review_package.apply_agent_findings(db, run, list(findings), profile_id=A3_PROFILE_ID)


def _agent_findings(db, run):
    return list(db.scalars(select(ReviewFinding).where(
        ReviewFinding.run_id == run.run_id, ReviewFinding.source == "agent")))


def test_eligible_invocation_then_persist(db):
    run, _d, _b = _sol_run(db)
    out = _run_a3(db, run)
    assert out.status == "succeeded"
    _apply(db, run, *out.findings)
    rows = _agent_findings(db, run)
    assert len(rows) == 1
    assert rows[0].profile_id == A3_PROFILE_ID and rows[0].advisory is True
    assert rows[0].field_id == SOL


def test_dedup_no_duplicate_on_reapply(db):
    run, _d, _b = _sol_run(db)
    _apply(db, run, _finding())
    _apply(db, run, _finding())  # same code again
    assert len(_agent_findings(db, run)) == 1


def test_deterministic_findings_separate(db):
    run, _d, _b = _sol_run(db)
    review_package.apply_findings(db, run)  # deterministic
    _apply(db, run, _finding())  # agent
    det = db.scalars(select(ReviewFinding).where(
        ReviewFinding.run_id == run.run_id, ReviewFinding.source == "deterministic_review"))
    assert all(f.profile_id != A3_PROFILE_ID for f in det)
    assert len(_agent_findings(db, run)) == 1


def test_agent_blocker_label_is_downgraded_and_never_blocks_approval(db):
    run, _d, _b = _sol_run(db)
    _apply(db, run, _finding(severity="info", description="info claim"))
    assert review_package.has_open_blocker(db, run) is False
    _apply(db, run, _finding(severity="blocker", description="blocker claim"))
    assert review_package.has_open_blocker(db, run) is False
    blocker_row = next(f for f in _agent_findings(db, run) if f.description == "blocker claim")
    assert blocker_row.severity == "warning" and blocker_row.advisory is True


def test_resolved_agent_finding_not_reopened_when_unseen(db):
    run, _d, _b = _sol_run(db)
    _apply(db, run, _finding(description="claim A"))
    _apply(db, run, _finding(description="claim B"))  # different code → A resolves
    rows = {f.description: f.status for f in _agent_findings(db, run)}
    assert rows["claim A"] == "resolved" and rows["claim B"] == "open"


# --- recheck integration ----------------------------------------------------


def test_maybe_run_a3_deterministic_makes_no_findings(db):
    run, _d, _b = _sol_run(db, processing_mode="deterministic_only")
    _maybe_run_a3(db, run)
    assert _agent_findings(db, run) == []


def test_maybe_run_a3_cloud_persists(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_fake_provider", True)
    run, _d, _b = _sol_run(db)
    _maybe_run_a3(db, run)
    assert len(_agent_findings(db, run)) == 1  # built-in fake warning


def test_recheck_clears_required_with_advisory_agent_warning(db):
    # A successful recheck clears recheck_required; A3 remains advisory.
    run, _d, _b = _sol_run(db)
    run.recheck_required = True
    _apply(db, run, _finding(severity="blocker"))
    pkg = review_package.refresh_package(db, run, clear_recheck=True)
    assert run.recheck_required is False
    assert pkg.blocker_count == 0


def test_failed_a3_preserves_prior_findings(db, monkeypatch):
    # corr 2: a failed/skipped A3 must not resolve prior A3 findings.
    monkeypatch.setattr(get_settings(), "agent_fake_provider", True)
    run, _d, _b = _sol_run(db)
    _apply(db, run, _finding(description="prior claim"))
    assert len(_agent_findings(db, run)) == 1
    # A provider failure during recheck: availability true but the run fails.
    monkeypatch.setattr(
        critic_review, "run_a3_evidence_consistency",
        lambda *a, **k: critic_review.A3Outcome(status="failed", reason="provider_error"),
    )
    _maybe_run_a3(db, run)
    rows = _agent_findings(db, run)
    assert len(rows) == 1 and rows[0].status == "open"  # preserved, not resolved
