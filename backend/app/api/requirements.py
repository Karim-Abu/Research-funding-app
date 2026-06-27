"""Requirements router — listRequirements (run-scoped RequirementAssessments)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends

from app.api.errors import ProblemException
from app.contracts.requirement import RequirementAssessment
from app.db.models import RunProjectSnapshot
from app.db.session import get_db
from app.repositories import requirements as requirements_repo
from app.repositories import runs as runs_repo
from app.runs import project_snapshot
from app.security.deps import AuthContext, require_session

router = APIRouter(tags=["Requirements"])


@router.get(
    "/runs/{run_id}/requirements", response_model=list[RequirementAssessment]
)
def list_requirements(
    run_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> list[RequirementAssessment]:
    run = runs_repo.get_scoped(db, run_id, context.user.workspace_id)
    if run is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Run not found.",
        )
    snapshot = db.get(RunProjectSnapshot, run_id)
    stale = snapshot is not None and project_snapshot.is_stale(db, snapshot)
    return requirements_repo.to_contracts(db, run_id, stale=stale)
