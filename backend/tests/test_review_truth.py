"""Review-Truth — Gruppierung und Zählwert-Parität der Qualitätsprüfung.

Ergänzt gezielt die bestehenden Wahrheits-Invarianten:
- «not_run ≠ bestanden» und «Coverage 0 ≠ bestanden» sind in
  tests/test_z_check_status_view.py gepinnt;
- «exact_verified ohne Stützstatus = location_found (Textstelle gefunden),
  nie supports_*» ist in tests/test_evidence_support_status.py gepinnt.

Hier neu:
1. Massen-Findings derselben Familie erzeugen genau EINE gruppierte
   Hauptaufgabe (B2), nie hunderte unpriorisierte Blocker.
2. Ein echter Blocker steht VOR der Massen-Gruppe (deterministische Priorität).
3. Die Zahl «blockierende Aufgaben» ist über alle Read-Models identisch
   (Fix Queue, ReviewStatusView, ReviewCheckStatusView) — die Quelle der
   Zahlen auf Review-, Export- und Dashboard-Screens.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.models import ReviewFinding
from app.db.session import SessionLocal
from app.review.check_status import build_check_status
from app.review.fix_queue import build_fix_queue
from app.review.service import read_status_view
from tests.reliability_fixtures.builders import completed_run_with_draft


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _add_open_finding(
    db,
    run,
    *,
    finding_code: str,
    severity: str = "warning",
    field_id: str = "SOL.INNOVATION_SOLUTION.EDITOR",
    target_type: str | None = "draft_claim",
    target_id: str | None = None,
) -> None:
    db.add(
        ReviewFinding(
            finding_id="rt-" + uuid.uuid4().hex[:12],
            run_id=run.run_id,
            workspace_id=run.workspace_id,
            profile_id="deterministic_review",
            field_id=field_id,
            requirement_id=None,
            severity=severity,
            description="Aussage ist nicht mit verifizierten Belegen verknüpft.",
            status="open",
            advisory=False,
            source="deterministic_review",
            finding_code=finding_code,
            target_type=target_type,
            target_id=target_id or finding_code.rsplit(":", 1)[-1],
        )
    )


def _mass_findings(db, run, count: int = 100) -> None:
    for index in range(count):
        _add_open_finding(
            db, run, finding_code=f"reliability:unsupported:claim-{index:03d}"
        )
    db.flush()


def test_hundred_similar_claims_group_to_one_task(db):
    run, _draft, _version = completed_run_with_draft(
        db, draft_text="Ein Text mit vielen gleichartigen unbelegten Aussagen."
    )
    _mass_findings(db, run, 100)

    queue = build_fix_queue(db, run)
    assert queue.total_open_findings == 100
    # B2: EINE Hauptaufgabe pro Feld × Familie × Severity — nie 100 Aufgaben.
    assert len(queue.grouped_findings) == 1
    group = queue.grouped_findings[0]
    assert group.count == 100
    assert group.severity == "warning"
    assert group.severity_class == "evidence_risk"
    assert len(group.examples) <= 5
    # Warnungen sind keine Blocker-Aufgaben; die Claims bleiben Evidenzhinweise.
    assert queue.blocking_task_count == 0
    assert queue.evidence_note_count == 100


def test_real_blocker_is_prioritized_before_mass_group(db):
    run, _draft, _version = completed_run_with_draft(
        db, draft_text="Ein Text mit vielen Hinweisen und einem echten Blocker."
    )
    _mass_findings(db, run, 100)
    _add_open_finding(
        db,
        run,
        finding_code="draft_placeholder:SOL.INNOVATION_SOLUTION.EDITOR",
        severity="blocker",
        target_type="portal_field_draft",
        target_id="SOL.INNOVATION_SOLUTION.EDITOR",
    )
    db.flush()

    queue = build_fix_queue(db, run)
    assert len(queue.grouped_findings) == 2
    # Deterministische Priorität: der Export-Blocker steht vor der
    # Evidenz-Massengruppe — unabhängig von deren Grösse.
    first = queue.grouped_findings[0]
    assert first.severity == "blocker"
    assert first.severity_class == "export_blocker"
    assert first.count == 1
    assert queue.blocking_task_count == 1


def test_blocking_task_count_agrees_across_all_read_models(db):
    run, _draft, _version = completed_run_with_draft(
        db, draft_text="Ein Text für die Zählwert-Parität aller Read-Models."
    )
    _mass_findings(db, run, 25)
    _add_open_finding(
        db,
        run,
        finding_code="draft_placeholder:SOL.INNOVATION_SOLUTION.EDITOR",
        severity="blocker",
        target_type="portal_field_draft",
        target_id="SOL.INNOVATION_SOLUTION.EDITOR",
    )
    db.flush()

    queue = build_fix_queue(db, run)
    status_view = read_status_view(db, run)
    check_status = build_check_status(db, run)

    # Eine Quelle der Wahrheit: Review-, Export- und Dashboard-Zahlen kommen
    # aus diesen drei Read-Models und müssen identisch sein.
    assert queue.blocking_task_count == 1
    assert status_view.blocking_task_count == queue.blocking_task_count
    assert check_status.blocking_task_count == queue.blocking_task_count
    assert status_view.evidence_note_count == queue.evidence_note_count
    assert check_status.evidence_note_count == queue.evidence_note_count
