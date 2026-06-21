"""Projects router — list/create/get/update, workspace-scoped + idempotent create."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.contracts.project import Project, ProjectCreate, ProjectList, ProjectPatch
from app.db.session import get_db
from app.repositories import audit, idempotency, projects
from app.security.deps import AuthContext, require_session, require_unsafe_guards

router = APIRouter(tags=["Projects"])


@router.get("/projects", response_model=ProjectList)
def list_projects(
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> ProjectList:
    rows = projects.list_by_workspace(db, context.user.workspace_id)
    return ProjectList(items=[projects.to_contract(p) for p in rows], next_cursor=None)


@router.post("/projects", response_model=Project, status_code=201)
def create_project(
    payload: ProjectCreate,
    response: Response,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=8, max_length=128
    ),
) -> Project:
    scope = f"{context.user.workspace_id}:{context.user.id}:POST:/projects"
    fingerprint = idempotency.fingerprint(
        "POST", "/api/v1/projects", payload.model_dump_json()
    )

    existing = idempotency.get(db, scope, idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ProblemException(
                status=409,
                code="idempotency_conflict",
                title="Conflict",
                detail="Idempotency-Key was reused with a different request.",
            )
        response.status_code = existing.response_status
        return Project(**existing.response_body)

    project = projects.create(
        db,
        workspace_id=context.user.workspace_id,
        created_by=context.user.id,
        data=payload,
    )
    body = projects.to_contract(project).model_dump(mode="json")
    idempotency.save(
        db,
        scope=scope,
        key=idempotency_key,
        request_fingerprint=fingerprint,
        response_status=201,
        response_body=body,
        resource_id=project.project_id,
    )
    audit.record(
        db,
        workspace_id=context.user.workspace_id,
        actor_user_id=context.user.id,
        action="project.create",
        target_type="project",
        target_id=project.project_id,
    )
    db.commit()
    return projects.to_contract(project)


@router.get("/projects/{project_id}", response_model=Project)
def get_project(
    project_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> Project:
    project = projects.get_scoped(db, project_id, context.user.workspace_id)
    if project is None:
        raise ProblemException(
            status=404,
            code="not_found",
            title="Resource not found",
            detail="Project not found.",
        )
    return projects.to_contract(project)


@router.patch("/projects/{project_id}", response_model=Project)
def update_project(
    project_id: str,
    payload: ProjectPatch,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> Project:
    project = projects.get_scoped(db, project_id, context.user.workspace_id)
    if project is None:
        raise ProblemException(
            status=404,
            code="not_found",
            title="Resource not found",
            detail="Project not found.",
        )
    projects.apply_patch(db, project, payload)
    audit.record(
        db,
        workspace_id=context.user.workspace_id,
        actor_user_id=context.user.id,
        action="project.update",
        target_type="project",
        target_id=project.project_id,
    )
    db.commit()
    return projects.to_contract(project)
