"""Public-safe research brief API over the existing research executor."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.contracts.research_brief import (
    ResearchBriefInput,
    ResearchBriefView,
    ResearchQueryEdit,
    ResearchQueryPlan,
    ResearchQueryView,
    ResearchRunRequest,
    ResearchRunResponse,
    ResearchWorkspace,
)
from app.db.models import ResearchBrief
from app.db.session import get_db
from app.repositories import projects as projects_repo
from app.research import brief_service
from app.security.deps import AuthContext, require_session, require_unsafe_guards

router = APIRouter(tags=["Research Briefs"])


def _project(db: Session, project_id: str, workspace_id: str):
    project = projects_repo.get_scoped(db, project_id, workspace_id)
    if project is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Project not found.",
        )
    return project


def _brief(db: Session, brief_id: str, workspace_id: str) -> ResearchBrief:
    brief = db.get(ResearchBrief, brief_id)
    if brief is None or brief.workspace_id != workspace_id:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Recherchebrief nicht gefunden.",
        )
    return brief


def _problem(exc: brief_service.BriefError) -> ProblemException:
    return ProblemException(
        status=exc.status, code=exc.code, title="Research request refused", detail=exc.detail
    )


@router.get("/projects/{project_id}/research-workspace", response_model=ResearchWorkspace)
def get_research_workspace(
    project_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> ResearchWorkspace:
    return brief_service.workspace(db, _project(db, project_id, context.user.workspace_id))


@router.post(
    "/projects/{project_id}/research-brief/suggest", response_model=ResearchBriefView
)
def suggest_research_brief(
    project_id: str,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> ResearchBriefView:
    project = _project(db, project_id, context.user.workspace_id)
    try:
        brief = brief_service.suggest(db, project, context.user.id)
        db.commit()
        return brief_service._view(brief)  # code-only beta contract
    except brief_service.BriefError as exc:
        db.rollback()
        raise _problem(exc) from exc


@router.put("/projects/{project_id}/research-brief", response_model=ResearchBriefView)
def save_research_brief(
    project_id: str,
    payload: ResearchBriefInput,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> ResearchBriefView:
    project = _project(db, project_id, context.user.workspace_id)
    try:
        brief = brief_service.save(db, project, context.user.id, payload)
        db.commit()
        return brief_service._view(brief)
    except brief_service.BriefError as exc:
        db.rollback()
        raise _problem(exc) from exc


@router.post("/research-briefs/{brief_id}/approve", response_model=ResearchBriefView)
def approve_research_brief(
    brief_id: str,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> ResearchBriefView:
    try:
        brief = brief_service.approve(
            db, _brief(db, brief_id, context.user.workspace_id), context.user.id
        )
        db.commit()
        return brief_service._view(brief)
    except brief_service.BriefError as exc:
        db.rollback()
        raise _problem(exc) from exc


@router.post("/research-briefs/{brief_id}/queries/plan", response_model=ResearchQueryPlan)
def plan_research_queries(
    brief_id: str,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> ResearchQueryPlan:
    try:
        plan = brief_service.plan_queries(
            db, _brief(db, brief_id, context.user.workspace_id), context.user.id
        )
        db.commit()
        return plan
    except brief_service.BriefError as exc:
        db.rollback()
        raise _problem(exc) from exc


@router.post("/research-briefs/{brief_id}/queries/preview", response_model=ResearchQueryView)
def preview_research_query(
    brief_id: str,
    payload: ResearchQueryEdit,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> ResearchQueryView:
    try:
        approval = brief_service.preview_query(
            db, _brief(db, brief_id, context.user.workspace_id), context.user.id,
            module=payload.module, planner_purpose=payload.planner_purpose,
            query_text=payload.query_text,
            supersedes_approval_id=payload.supersedes_approval_id,
        )
        db.commit()
        return brief_service._query_view(approval)
    except brief_service.BriefError as exc:
        db.rollback()
        raise _problem(exc) from exc


@router.post("/research-briefs/{brief_id}/run", response_model=ResearchRunResponse)
def run_research_brief(
    brief_id: str,
    payload: ResearchRunRequest,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> ResearchRunResponse:
    try:
        return brief_service.run(
            db, _brief(db, brief_id, context.user.workspace_id),
            context.user.id, payload.approval_ids,
        )
    except (brief_service.BriefError, brief_service.service.ResearchBlocked) as exc:
        db.rollback()
        if isinstance(exc, brief_service.BriefError):
            raise _problem(exc) from exc
        raise ProblemException(
            status=exc.status, code=exc.code, title="Research request refused", detail=exc.detail
        ) from exc
