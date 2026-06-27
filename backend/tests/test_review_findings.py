"""Deterministic review findings + ReviewPackage assembly + graph stages."""
from __future__ import annotations

from sqlalchemy import func, select

from app.db.models import AnalysisRun, ControlResult, ReviewFinding
from app.db.session import SessionLocal
from app.review import package as review_package
from tests.review_helpers import ABSTRACT, get_review, setup_completed_run


def test_review_package_contract_shape(client):
    _csrf, _pid, run_id = setup_completed_run(client)
    pkg = get_review(client, run_id)
    assert pkg["run_id"] == run_id
    for key in (
        "requirements", "fields", "findings", "approval_status", "blocker_count",
        "warning_count", "open_issues", "review_package_version",
        "current_approval_scope_hash", "recheck_required", "stale_finding_count",
    ):
        assert key in pkg, key
    assert pkg["recheck_required"] is False  # fresh run, nothing edited yet
    assert pkg["review_package_version"].startswith("rpv-")
    assert len(pkg["current_approval_scope_hash"]) == 64


def test_template_placeholders_are_blocker_findings(client):
    _csrf, _pid, run_id = setup_completed_run(client)
    pkg = get_review(client, run_id)
    placeholder_findings = [
        f for f in pkg["findings"] if f["severity"] == "blocker" and f["field_id"]
    ]
    assert placeholder_findings, "untouched template fields must block"
    # Fresh templates with placeholders → approval is blocked.
    assert pkg["approval_status"] == "blocked"
    assert pkg["blocker_count"] >= 1
    # Findings only carry contract fields (no internal source/target leak).
    assert set(placeholder_findings[0]) == {
        "finding_id", "profile_id", "field_id", "requirement_id", "severity",
        "description", "suggested_improvement", "status", "advisory",
    }


def test_missing_research_partner_is_blocker(client):
    _csrf, _pid, run_id = setup_completed_run(client, with_research_partner=False)
    pkg = get_review(client, run_id)
    assert any(i["severity"] == "blocker" for i in pkg["open_issues"])
    assert any(
        f["requirement_id"] == "REQ.INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE"
        for f in pkg["findings"]
        if f["severity"] == "blocker"
    )


def test_findings_are_all_deterministic_source(client):
    _csrf, _pid, run_id = setup_completed_run(client)
    db = SessionLocal()
    try:
        sources = {
            row.source
            for row in db.scalars(
                select(ReviewFinding).where(ReviewFinding.run_id == run_id)
            )
        }
        assert sources == {"deterministic_review"}  # no human/semantic findings yet
    finally:
        db.close()


def test_aggregator_is_idempotent(client):
    _csrf, _pid, run_id = setup_completed_run(client)
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        before = db.scalar(
            select(func.count(ReviewFinding.finding_id)).where(
                ReviewFinding.run_id == run_id
            )
        )
        review_package.apply_findings(db, run)
        review_package.apply_findings(db, run)
        db.flush()
        after = db.scalar(
            select(func.count(ReviewFinding.finding_id)).where(
                ReviewFinding.run_id == run_id
            )
        )
        assert after == before  # no duplicates on re-run
    finally:
        db.rollback()
        db.close()


def test_graph_recorded_review_stages_and_a3_disabled(client):
    _csrf, pid, run_id = setup_completed_run(client)
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        assert run.current_stage == "finalize_run"
        assert run.progress_percent == 100
        a3 = db.scalar(
            select(ControlResult).where(
                ControlResult.project_id == pid,
                ControlResult.control_id == "CTRL.DATA_POLICY",
                ControlResult.detail.like("a3_disabled%"),
            )
        )
        assert a3 is not None and a3.status == "passed"
    finally:
        db.close()


def test_resolved_finding_clears_after_fix(client):
    csrf, _pid, run_id = setup_completed_run(client)
    from tests.review_helpers import clean_field, run_recheck

    before = get_review(client, run_id)
    abstract_blockers = [
        f for f in before["findings"]
        if f["field_id"] == ABSTRACT and f["severity"] == "blocker"
    ]
    assert abstract_blockers  # placeholder present initially

    clean_field(client, csrf, run_id, ABSTRACT, "Kurzfassung ohne Platzhalter.")
    assert run_recheck(client, csrf, run_id).status_code == 202

    after = get_review(client, run_id)
    assert not [
        f for f in after["findings"]
        if f["field_id"] == ABSTRACT and f["severity"] == "blocker"
    ]
