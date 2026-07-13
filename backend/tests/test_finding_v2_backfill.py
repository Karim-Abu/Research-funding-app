"""R2.3 — fingerprint + severity_class bei neu erzeugten Findings.

Enthält die FINDINGS-IDEMPOTENZ-REGRESSION (dauerhaftes Merge-Gate ab R2):
ein erneuter Review-/Recheck-Lauf über denselben Zustand erzeugt KEINE
zusätzlichen Finding-Rows. finding_code bleibt unverändert das
Idempotenz-Format; fingerprint/severity_class sind rein additive Felder.
"""
from __future__ import annotations

from sqlalchemy import select

from app.db.models import ReviewFinding
from app.db.session import SessionLocal
from app.review.fingerprint import (
    SEVERITY_CLASSES,
    classify_severity_class,
    finding_code_family,
)
from tests.review_helpers import get_review, run_recheck, setup_completed_run


def _rows(run_id: str) -> list[ReviewFinding]:
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(ReviewFinding).where(ReviewFinding.run_id == run_id)
            )
        )


class TestIdempotenzRegression:
    """Merge-Gate: Re-Run erzeugt keine zusätzlichen Rows."""

    def test_rerun_creates_no_additional_rows(self, client) -> None:
        csrf, _project_id, run_id = setup_completed_run(client)
        get_review(client, run_id)
        first = _rows(run_id)
        assert first, "Setup erzeugt Findings (Template-Platzhalter)"
        first_count = len(first)
        first_ids = {f.finding_id for f in first}

        # Re-Run über unveränderten Zustand: Review erneut lesen + Recheck.
        get_review(client, run_id)
        assert run_recheck(client, csrf, run_id).status_code in (200, 202)
        get_review(client, run_id)

        again = _rows(run_id)
        assert len(again) == first_count, "Re-Run darf keine neuen Rows erzeugen"
        assert {f.finding_id for f in again} == first_ids

    def test_fingerprint_stable_across_reruns(self, client) -> None:
        csrf, _project_id, run_id = setup_completed_run(client)
        get_review(client, run_id)
        before = {f.finding_code: f.fingerprint for f in _rows(run_id)}
        assert run_recheck(client, csrf, run_id).status_code in (200, 202)
        get_review(client, run_id)
        after = {f.finding_code: f.fingerprint for f in _rows(run_id)}
        assert before == after

    def test_finding_code_format_unchanged(self, client) -> None:
        _csrf, _project_id, run_id = setup_completed_run(client)
        get_review(client, run_id)
        codes = {f.finding_code for f in _rows(run_id)}
        # Bestehende Formate (Familie:Ziel-ID) bleiben exakt erhalten.
        assert any(c.startswith("draft_placeholder:") for c in codes)
        for code in codes:
            assert ":" in code or code == "open_issue_blocker"


class TestBackfillValues:
    def test_new_findings_carry_fingerprint_class_and_last_seen(self, client) -> None:
        _csrf, _project_id, run_id = setup_completed_run(client)
        get_review(client, run_id)
        rows = _rows(run_id)
        assert rows
        for row in rows:
            assert row.fingerprint, f"{row.finding_code} ohne fingerprint"
            assert len(row.fingerprint) == 64
            assert row.severity_class in SEVERITY_CLASSES, row.finding_code
            assert row.last_seen_at is not None

    def test_placeholder_is_export_blocker(self, client) -> None:
        _csrf, _project_id, run_id = setup_completed_run(client)
        get_review(client, run_id)
        placeholder_rows = [
            f for f in _rows(run_id)
            if f.finding_code.startswith("draft_placeholder:")
        ]
        assert placeholder_rows
        assert all(f.severity_class == "export_blocker" for f in placeholder_rows)

    def test_missing_research_partner_is_eligibility_blocker(self, client) -> None:
        _csrf, _project_id, run_id = setup_completed_run(
            client, with_research_partner=False, title="Ohne Forschungspartner"
        )
        get_review(client, run_id)
        blocker_rows = [
            f for f in _rows(run_id)
            if f.finding_code.startswith("open_issue_blocker:")
        ]
        assert blocker_rows, "fehlender Forschungspartner erzeugt Blocker-Issue"
        assert all(
            f.severity_class in ("eligibility_blocker", "budget_blocker")
            for f in blocker_rows
        )
        assert any(
            f.severity_class == "eligibility_blocker" for f in blocker_rows
        )


class TestClassifierUnit:
    def test_exactly_six_classes(self) -> None:
        assert len(SEVERITY_CLASSES) == 6

    def test_family_mapping(self) -> None:
        assert classify_severity_class("draft_placeholder:INTRO.APP.ABSTRACT") == "export_blocker"
        assert classify_severity_class("draft_over_limit:X") == "export_blocker"
        assert classify_severity_class("draft_empty:X") == "export_blocker"
        assert classify_severity_class("reliability:quantified:c1") == "evidence_risk"
        assert classify_severity_class("reliability:market:c2") == "evidence_risk"
        assert classify_severity_class("stale_evidence_link:l1") == "evidence_risk"
        assert classify_severity_class("a3:abc123") == "evidence_risk"
        assert classify_severity_class("comment:uuid") == "style_risk"

    def test_open_issue_by_requirement_category(self) -> None:
        assert classify_severity_class("open_issue_blocker:i1", "budget") == "budget_blocker"
        assert classify_severity_class("open_issue_blocker:i1", "partner_eligibility") == "eligibility_blocker"
        assert classify_severity_class("open_issue_blocker:i1", None) == "eligibility_blocker"

    def test_family_derivation(self) -> None:
        assert finding_code_family("draft_placeholder:INTRO.APP.ABSTRACT") == "draft_placeholder"
        assert finding_code_family("reliability:quantified:c-1") == "reliability:quantified"
        assert finding_code_family("reliability:false_consensus:c-2") == "reliability:false_consensus"
        assert finding_code_family("comment:0000") == "comment"
        assert finding_code_family("a3:deadbeef") == "a3"
