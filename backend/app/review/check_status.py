"""ReviewCheckStatusView (Teil A) — autoritative Check-Status je Prüfbereich.

Read-only View-Builder. Es existiert kein Ausführungsprotokoll je Check —
ob ein Bereich «lief», wird präkonditionsbasiert abgeleitet (fail-closed):

- Deterministische Bereiche (Pflichtfelder, Zeichenlimits, Platzhalter):
  eine ``ReviewPackage``-Zeile existiert (wird nur von ``refresh_package``
  nach ``apply_findings`` geschrieben) und ``run.recheck_required`` ist False.
- Fördervoraussetzungen/Budget: zusätzlich existieren Requirement-Assessments
  (bzw. mindestens eines zu einer Anforderung der Registry-Kategorie budget).
- Evidenz-Bereiche: eine AKTUELLE (nicht stale) RunQualitySummary existiert;
  stale ⇒ ``not_run`` mit ``reason="stale"`` (F3, fail-closed).
- Inhaltliche Konsistenz: Rubric-Heuristiken liefen (Flag) oder ein
  Reliability-Pass lief (Drift-Scan).
- Export: abgeleitet — failed sobald irgendein Bereich failed; passed nur,
  wenn ALLE Bereiche passed sind; sonst warning («mit Warnungen kopierbar»,
  nie grün als fachlich freigegeben).

``passed`` wird NIE aus der blossen Abwesenheit von Findings abgeleitet:
Abwesenheit ohne gelaufenen Check ist ``not_run``. Bereiche mit offenen
Findings bleiben failed/warning, auch wenn die Prüfung veraltet ist — der
Befund verschwindet nicht durch eine Textänderung (``stale`` signalisiert die
Veraltung separat).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.contracts.review import CheckAreaStatus, ReviewCheckStatusView
from app.db.models import (
    AnalysisRun,
    RequirementAssessment,
    ReviewFinding,
    ReviewPackage,
)
from app.registry import get_registry
from app.review import package as review_package
from app.review.fingerprint import (
    CHECK_AREAS,
    area_for_finding,
    finding_code_family,
)
from app.review.fix_queue import _row_severity_class, build_fix_queue


def build_check_status(db: Session, run: AnalysisRun) -> ReviewCheckStatusView:
    """Autoritativer Status der neun Prüfbereiche. Pure read."""
    registry = get_registry()
    package = db.get(ReviewPackage, run.run_id)
    deterministic_ran = package is not None and not run.recheck_required

    # Offene Findings je Bereich zählen (Zuordnung über Familie +
    # severity_class — deterministisch, keine Keyword-Heuristik).
    blockers: dict[str, int] = {area: 0 for area in CHECK_AREAS}
    warnings: dict[str, int] = {area: 0 for area in CHECK_AREAS}
    for row in db.scalars(
        select(ReviewFinding).where(
            ReviewFinding.run_id == run.run_id,
            ReviewFinding.status == "open",
        )
    ):
        family = finding_code_family(row.finding_code)
        area = area_for_finding(family, _row_severity_class(row, registry))
        if area is None:
            continue
        if row.severity == "blocker":
            blockers[area] += 1
        elif row.severity == "warning":
            warnings[area] += 1

    # Reliability-Zustand (lazy Import wie in review.package — kein Zyklus).
    from app.reliability import approval as reliability_approval

    summary = reliability_approval.current_summary(db, run)
    reliability_stale = reliability_approval.is_stale(db, run)
    reliability_ran = summary is not None

    assessments = db.scalars(
        select(RequirementAssessment).where(
            RequirementAssessment.run_id == run.run_id
        )
    ).all()
    has_budget_assessment = any(
        (req := registry.requirements.get(a.requirement_id)) is not None
        and req.category == "budget"
        for a in assessments
    )

    ran_by_area: dict[str, bool] = {
        "pflichtfelder": deterministic_ran,
        "zeichenlimits": deterministic_ran,
        "platzhalter": deterministic_ran,
        "voraussetzungen": deterministic_ran and bool(assessments),
        "budget": deterministic_ran and has_budget_assessment,
        "evidenz_coverage": reliability_ran,
        "evidenz_suffizienz": reliability_ran,
        "konsistenz": (
            (deterministic_ran and get_settings().rubric_v0_enabled)
            or reliability_ran
        ),
    }

    def _not_run_reason(area: str) -> str:
        if area in ("evidenz_coverage", "evidenz_suffizienz") and reliability_stale:
            return "stale"
        if package is not None and run.recheck_required:
            return "stale"
        return "not_executed"

    areas: list[CheckAreaStatus] = []
    for area in CHECK_AREAS:
        if area == "export":
            continue  # abgeleitet, unten
        n_blocker, n_warning = blockers[area], warnings[area]
        # Coverage-Disziplin: eine aktuelle Summary mit unbelegten
        # evidenzpflichtigen Claims kann nie «Bestanden» ergeben — auch
        # unabhängig von den Finding-Zählern (Belt-and-Braces).
        coverage_incomplete = (
            area == "evidenz_coverage"
            and summary is not None
            and summary.claim_count > 0
            and (
                summary.unsupported_claims > 0
                or (summary.evidence_coverage or 0.0) < 1.0
            )
        )
        if n_blocker > 0:
            status = "failed"
        elif n_warning > 0 or coverage_incomplete:
            status = "warning"
        elif ran_by_area[area]:
            status = "passed"
        else:
            status = "not_run"
        areas.append(
            CheckAreaStatus(
                area=area,  # type: ignore[arg-type]
                status=status,  # type: ignore[arg-type]
                open_blockers=n_blocker,
                open_warnings=n_warning,
                reason=_not_run_reason(area) if status == "not_run" else None,
            )
        )

    # Export-/Kopierbereitschaft (A6): failed bei irgendeinem failed-Bereich
    # oder eigenen Export-Blockern; passed NUR wenn alle Bereiche passed und
    # nichts veraltet ist; sonst «mit Warnungen kopierbar» (warning).
    export_blockers = blockers["export"]
    export_warnings = warnings["export"]
    if package is None:
        export_status = "not_run"
    elif export_blockers > 0 or any(a.status == "failed" for a in areas):
        export_status = "failed"
    elif (
        all(a.status == "passed" for a in areas)
        and export_warnings == 0
        and not run.recheck_required
        and not reliability_stale
    ):
        export_status = "passed"
    else:
        export_status = "warning"
    areas.append(
        CheckAreaStatus(
            area="export",
            status=export_status,  # type: ignore[arg-type]
            open_blockers=export_blockers,
            open_warnings=export_warnings,
            reason=_not_run_reason("export") if export_status == "not_run" else None,
        )
    )

    fix_queue = build_fix_queue(db, run)
    scope_hash = review_package.compute_scope_hash(db, run)
    return ReviewCheckStatusView(
        run_id=run.run_id,
        areas=areas,
        stale=bool(run.recheck_required or reliability_stale),
        blocking_task_count=fix_queue.blocking_task_count,
        evidence_note_count=fix_queue.evidence_note_count,
        review_package_version=review_package.package_version(scope_hash),
    )
