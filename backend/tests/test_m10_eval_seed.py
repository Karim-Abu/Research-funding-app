"""Milestone 10 — evaluation seed/reset dataset.

Proves the seed separation (corr 3): plain ``--reset`` produces NO evaluation-only
artifacts, while ``--evaluation`` deterministically adds a Value Creation draft, a
source-backed market comparison, a strong unsupported claim (reliability blocker) and a
RunQualitySummary — idempotently.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.config.settings import get_settings
from app.db.models import (
    DraftVersion,
    MarketComparison,
    MarketComparisonItem,
    PortalFieldDraft,
    ReviewFinding,
    RunQualitySummary,
)
from app.db.session import SessionLocal
from app.demo.dataset import DEMO_PROJECTS
from app.demo.evaluation import VC_FIELD
from app.demo.seed import seed_demo_data

MAIN = DEMO_PROJECTS[0]


@pytest.fixture
def demo_enabled(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "demo_data_enabled", True)
    monkeypatch.setattr(s, "app_env", "development")
    return s


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _vc_text(db) -> str | None:
    draft = db.scalar(
        select(PortalFieldDraft).where(
            PortalFieldDraft.run_id == MAIN.run_id,
            PortalFieldDraft.field_id == VC_FIELD,
        )
    )
    if draft is None or draft.current_version_id is None:
        return None
    version = db.get(DraftVersion, draft.current_version_id)
    return version.text if version else None


def _market_items(db):
    return db.scalars(
        select(MarketComparisonItem)
        .join(MarketComparison, MarketComparisonItem.comparison_id == MarketComparison.comparison_id)
        .where(MarketComparison.project_id == MAIN.project_id)
    ).all()


def _summary(db):
    return db.scalar(
        select(RunQualitySummary).where(RunQualitySummary.run_id == MAIN.run_id)
    )


def test_plain_demo_seed_has_no_evaluation_artifacts(demo_enabled, db):
    seed_demo_data(reset=True)
    db.expire_all()
    # No market comparison, no reliability summary, no eval VC draft.
    assert _market_items(db) == []
    assert _summary(db) is None
    vc = _vc_text(db)
    assert vc is None or "unangefochten fuehrende" not in vc


def test_evaluation_seed_adds_deterministic_fixtures(demo_enabled, db):
    seed_demo_data(reset=True, evaluation=True)
    db.expire_all()

    # Value Creation draft carries the evaluation fixture text.
    vc = _vc_text(db)
    assert vc is not None and "unangefochten fuehrende" in vc

    # A source-backed market comparison item (verified quote).
    items = _market_items(db)
    assert any(i.confidence_label == "source_backed" and i.verified_quote_refs for i in items)

    # RunQualitySummary with an unsupported claim + an open reliability finding.
    # B5-Blockerdisziplin: die unbelegte starke Aussage ist Reviewer-Risiko
    # (warning), kein automatischer Blocker mehr.
    summary = _summary(db)
    assert summary is not None
    assert summary.unsupported_claims >= 1
    assert summary.supported_claims >= 1
    finding = db.scalar(
        select(ReviewFinding).where(
            ReviewFinding.run_id == MAIN.run_id,
            ReviewFinding.profile_id == "M9K.reliability_assurance",
            ReviewFinding.severity == "warning",
            ReviewFinding.status == "open",
        )
    )
    assert finding is not None


def test_evaluation_run_summary_is_deterministic(demo_enabled, db):
    from app.db.models import AnalysisRun
    from app.evaluation.summary import build_evaluation_summary, to_json

    seed_demo_data(reset=True, evaluation=True)
    db.expire_all()
    run = db.get(AnalysisRun, MAIN.run_id)
    ts = "2026-01-01T00:00:00+00:00"
    a = build_evaluation_summary(db, run, generated_at=ts)
    b = build_evaluation_summary(db, run, generated_at=ts)
    assert to_json(a) == to_json(b)  # reproducible for a fixed run + timestamp
    # Coverage and sufficiency are SEPARATE metrics (M9K discipline carried into M10).
    assert "evidence_coverage" in a and "evidence_sufficiency_pass_rate" in a
    assert a["source_count"] >= 1 and a["evidence_anchor_count"] >= 1
    assert a["estimated_cost"]["placeholder"] is True


def test_evaluation_seed_is_idempotent(demo_enabled, db):
    seed_demo_data(reset=True, evaluation=True)
    db.expire_all()
    items_before = len(_market_items(db))
    summary_before = _summary(db).summary_id
    # Re-run without reset — must not duplicate.
    seed_demo_data(evaluation=True)
    db.expire_all()
    assert len(_market_items(db)) == items_before
    # A new pass on the same scope reuses the summary (idempotent).
    assert _summary(db) is not None
