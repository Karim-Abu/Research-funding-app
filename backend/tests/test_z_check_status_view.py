"""Teil A — ReviewCheckStatusView: autoritative Check-Status je Prüfbereich.

Kerninvariante: ``passed`` nur nach tatsächlich gelaufenem Check. Abwesenheit
von Findings ohne gelaufenen Check ⇒ ``not_run`` — nie «Bestanden».
"""
from __future__ import annotations

import uuid

import pytest

from app.db.models import DraftVersion
from app.db.session import SessionLocal
from app.reliability.executor import run_reliability_pass
from app.review import package as review_package
from app.review.check_status import build_check_status
from app.review.fingerprint import CHECK_AREAS
from tests.reliability_fixtures.builders import (
    completed_run_with_draft,
    link_anchor_to_draft,
)
from tests.review_helpers import setup_completed_run


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _areas(view):
    return {a.area: a for a in view.areas}


def _run_review(db, run):
    review_package.apply_findings(db, run)
    review_package.refresh_package(db, run)
    db.flush()


# --- not_run-Disziplin ------------------------------------------------------

def test_all_areas_not_run_without_any_check(db):
    run, _d, _v = completed_run_with_draft(
        db, draft_text="Ein Entwurfstext, der noch nie geprüft wurde.")
    view = build_check_status(db, run)
    assert {a.area for a in view.areas} == set(CHECK_AREAS)
    assert [a.area for a in view.areas] == list(CHECK_AREAS)  # feste Reihenfolge
    assert all(a.status == "not_run" for a in view.areas)
    assert all(a.reason == "not_executed" for a in view.areas)


def test_evidence_areas_not_run_without_reliability_pass(db):
    run, _d, _v = completed_run_with_draft(
        db, draft_text="Sauberer kurzer Text ohne offene Punkte.")
    _run_review(db, run)
    areas = _areas(build_check_status(db, run))
    # Deterministische Prüfung lief ⇒ Formalbereiche ehrlich bestanden.
    assert areas["pflichtfelder"].status == "passed"
    assert areas["zeichenlimits"].status == "passed"
    assert areas["platzhalter"].status == "passed"
    # Ohne Reliability-Pass sind die Evidenz-Bereiche NICHT bestanden.
    assert areas["evidenz_coverage"].status == "not_run"
    assert areas["evidenz_suffizienz"].status == "not_run"
    assert areas["evidenz_coverage"].reason == "not_executed"
    # Keine Assessments in dieser Fixture ⇒ Voraussetzungen/Budget nicht geprüft.
    assert areas["voraussetzungen"].status == "not_run"
    assert areas["budget"].status == "not_run"
    # Export nie grün, solange Prüfbereiche nicht gelaufen sind.
    assert areas["export"].status == "warning"


def test_coverage_zero_cannot_pass(db):
    run, _d, _v = completed_run_with_draft(
        db, draft_text="Der Markt für Robotik wächst um 40 Prozent pro Jahr.")
    _run_review(db, run)
    run_reliability_pass(db, run)
    db.commit()
    areas = _areas(build_check_status(db, run))
    assert areas["evidenz_coverage"].status != "passed"
    assert areas["evidenz_suffizienz"].status != "passed"
    assert areas["evidenz_suffizienz"].open_warnings >= 1


def test_stale_summary_yields_not_run_with_reason(db):
    run, draft, v = completed_run_with_draft(
        db, draft_text="Unser Verfahren erreicht eine Genauigkeit von 95 Prozent.")
    link_anchor_to_draft(
        db, run, v,
        quote="Die gemessene Genauigkeit des Verfahrens betrug 95 Prozent im Test.")
    _run_review(db, run)
    run_reliability_pass(db, run)
    db.commit()
    areas = _areas(build_check_status(db, run))
    assert areas["evidenz_suffizienz"].status == "passed"  # gestützt, keine Findings

    # Entwurf ändern ⇒ Summary stale ⇒ fail-closed not_run mit Grund.
    new_v = "ver-" + uuid.uuid4().hex[:8]
    db.add(DraftVersion(
        draft_version_id=new_v, draft_id=draft.draft_id,
        text="Ein völlig neuer Text ohne die geprüfte Genauigkeitsangabe.",
        character_count=10, created_by="user", content_hash="h" + new_v))
    draft.current_version_id = new_v
    db.commit()
    view = build_check_status(db, run)
    areas = _areas(view)
    assert areas["evidenz_suffizienz"].status == "not_run"
    assert areas["evidenz_suffizienz"].reason == "stale"
    assert areas["evidenz_coverage"].status == "not_run"
    assert view.stale is True
    assert areas["export"].status != "passed"


def test_recheck_required_clears_passed(db):
    run, _d, _v = completed_run_with_draft(
        db, draft_text="Sauberer kurzer Text ohne offene Punkte.")
    _run_review(db, run)
    assert _areas(build_check_status(db, run))["pflichtfelder"].status == "passed"
    run.recheck_required = True
    db.flush()
    view = build_check_status(db, run)
    assert not any(a.status == "passed" for a in view.areas)
    assert _areas(view)["pflichtfelder"].reason == "stale"
    assert view.stale is True


# --- failed/warning + Export-Disziplin ---------------------------------------

def test_placeholder_blocker_fails_area_and_export(db):
    run, _d, _v = completed_run_with_draft(
        db, draft_text="Einleitung mit [[Angabe ergänzen: Zielgruppe]] im Text.")
    _run_review(db, run)
    areas = _areas(build_check_status(db, run))
    assert areas["platzhalter"].status == "failed"
    assert areas["platzhalter"].open_blockers >= 1
    assert areas["export"].status == "failed"


def test_evidence_warnings_keep_export_copyable_with_warnings(db):
    run, _d, _v = completed_run_with_draft(
        db, draft_text="Der Markt für Robotik wächst um 40 Prozent pro Jahr.")
    _run_review(db, run)
    run_reliability_pass(db, run)
    db.commit()
    areas = _areas(build_check_status(db, run))
    # Formal sauber, aber Evidenz-/Reviewer-Risiken offen ⇒ «mit Warnungen
    # kopierbar» — nie grün als fachlich freigegeben, aber auch kein Blocker.
    assert areas["platzhalter"].status == "passed"
    assert areas["export"].status == "warning"


# --- API ---------------------------------------------------------------------

def test_endpoint_is_read_only_and_stable(client):
    _csrf, _pid, run_id = setup_completed_run(client)
    first = client.get(f"/api/v1/runs/{run_id}/review/check-status")
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["run_id"] == run_id
    assert [a["area"] for a in body["areas"]] == list(CHECK_AREAS)
    # Template-Platzhalter der Fixture ⇒ Bereich rot, Export rot.
    by_area = {a["area"]: a for a in body["areas"]}
    assert by_area["platzhalter"]["status"] == "failed"
    assert by_area["export"]["status"] == "failed"
    # Doppel-GET identisch (read-only).
    second = client.get(f"/api/v1/runs/{run_id}/review/check-status")
    assert second.json() == body
