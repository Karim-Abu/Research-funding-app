"""Projects router — list/create/get/update, workspace-scoped + idempotent create."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.contracts.processing import ProcessingConfirmation, ProcessingConfirmationCreate
from app.contracts.project import Project, ProjectCreate, ProjectList, ProjectPatch
from app.db.session import get_db
from app.repositories import audit, controls, idempotency, projects
from app.repositories import processing_confirmations as confirmations_repo
from app.runs import cloud_policy
from app.runs.policy import POLICY_VERSION
from app.security.deps import AuthContext, require_session, require_unsafe_guards

router = APIRouter(tags=["Projects"])
_NOT_FOUND = "Resource not found"


@router.get("/projects", response_model=ProjectList)
def list_projects(
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> ProjectList:
    rows = projects.list_by_workspace(db, context.user.workspace_id)
    return ProjectList(
        items=[projects.to_contract(db, p) for p in rows],
        next_cursor=None,
    )


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
    body = projects.to_contract(db, project).model_dump(mode="json")
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
    return projects.to_contract(db, project)


@router.post(
    "/projects/{project_id}/processing-confirmations",
    response_model=ProcessingConfirmation,
    status_code=201,
)
def create_processing_confirmation(
    project_id: str,
    payload: ProcessingConfirmationCreate,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=8, max_length=128
    ),
) -> ProcessingConfirmation:
    """Milestone 9D.2: a per-run user acknowledgement that selected public/synthetic
    content may be sent to the configured cloud AI for one cloud_assisted run. Any
    project participant (member or lead_admin) may confirm. This is NOT an
    institutional approval — internal/confidential/NDA stay blocked."""
    project = projects.get_scoped(db, project_id, context.user.workspace_id)
    if project is None:
        raise ProblemException(
            status=404, code="not_found", title=_NOT_FOUND, detail="Project not found.",
        )
    # The confirmation cannot override the classification gate (corr #2).
    eligible, reason = cloud_policy.classification_eligible(project.data_classification)
    if not eligible:
        raise ProblemException(
            status=403, code="cloud_not_eligible_for_classification",
            title="Forbidden",
            detail=("Cloud-KI ist in dieser Beta nur für öffentliche oder synthetische "
                    "Daten verfügbar; interne, vertrauliche oder NDA-Inhalte sind blockiert."),
        )
    if payload.accepted_policy_version != POLICY_VERSION:
        raise ProblemException(
            status=422, code="policy_version_mismatch", title="Unprocessable Entity",
            detail="Die bestätigte Richtlinienversion ist nicht aktuell.",
        )
    project_versions = confirmations_repo.project_source_version_ids(db, project.project_id)
    if not set(payload.source_version_ids).issubset(project_versions):
        raise ProblemException(
            status=422, code="unknown_source_version", title="Unprocessable Entity",
            detail="Eine ausgewählte Quelle gehört nicht zu diesem Projekt.",
        )

    confirmation = confirmations_repo.create(
        db, project, created_by=context.user.id,
        source_version_ids=payload.source_version_ids,
        accepted_policy_version=payload.accepted_policy_version, purpose=payload.purpose,
        provider_route_class=cloud_policy.provider_route_class(),
        confirmation_text_version=cloud_policy.CONFIRMATION_TEXT_VERSION,
        data_classification_shown=dict(project.data_classification or {}),
    )
    controls.record(
        db, workspace_id=project.workspace_id, project_id=project.project_id,
        control_id="CTRL.DATA_POLICY", status="passed", detail="cloud_confirmation_created",
    )
    audit.record(
        db, workspace_id=project.workspace_id, actor_user_id=context.user.id,
        action="processing_confirmation.created", target_type="project",
        target_id=project.project_id,
        detail={
            "confirmation_id": confirmation.confirmation_id,
            "source_version_ids": list(payload.source_version_ids),
            "processing_mode": "cloud_assisted",
            "data_classification_shown": dict(project.data_classification or {}),
            "confirmation_text_version": cloud_policy.CONFIRMATION_TEXT_VERSION,
            "policy_version": POLICY_VERSION,
            "provider_route_class": confirmation.provider_route_class,
        },
    )
    db.commit()
    return confirmations_repo.to_contract(confirmation)


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
    return projects.to_contract(db, project)


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
    return projects.to_contract(db, project)
