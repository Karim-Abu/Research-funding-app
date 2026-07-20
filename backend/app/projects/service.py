"""Central mutations for project-owned fields."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.contracts.project import ProjectPatch
from app.db.models import Project
from app.projects.duration import ProjectDateRangeInvalid, derive_project_duration
from app.repositories import projects as projects_repo
from app.runs import project_snapshot


def mutate_project(
    db: Session,
    *,
    project: Project,
    patch: ProjectPatch,
    actor_user_id: str,
    stale_reason: str = "project_input_changed",
) -> tuple[Project, set[str]]:
    """Validate and apply a project patch, then invalidate current run state."""
    data = patch.model_dump(exclude_unset=True)
    if "duration_months" in data:
        raise ProblemException(
            status=422,
            code="duration_read_only",
            title="Unprocessable Entity",
            detail="Die Projektdauer wird aus Start- und Enddatum abgeleitet und kann nicht separat bearbeitet werden.",
        )

    candidate_start = data.get("start_date", project.start_date)
    candidate_end = data.get("end_date", project.end_date)
    try:
        derive_project_duration(candidate_start, candidate_end)
    except ProjectDateRangeInvalid as exc:
        raise ProblemException(
            status=422,
            code="project_date_range_invalid",
            title="Unprocessable Entity",
            detail="Das Projektende darf nicht vor dem Projektstart liegen.",
        ) from exc

    changed = {
        field
        for field, value in data.items()
        if field != "duration_months" and getattr(project, field) != value
    }
    projects_repo.apply_patch(db, project, patch)
    if changed:
        project_snapshot.mark_current_runs_stale(
            db,
            project=project,
            actor_user_id=actor_user_id,
            reason=stale_reason,
        )
    return project, changed
