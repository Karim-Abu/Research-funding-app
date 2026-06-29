"""Research router (Milestone 9I-A) — createResearchTask / getResearchTask /
listResearchResults / importResearchResult.

Role note (binding correction 2): the OpenAPI marks createResearchTask lead_admin-only;
this implementation allows member OR lead_admin to start a research task on accessible
public/synthetic projects, as an authorized, documented beta-usability deviation. The
data policy still gates the actual external call. Web research is public/synthetic only.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.contracts.research import (
    ResearchResult as ResearchResultContract,
    ResearchTask as ResearchTaskContract,
    ResearchTaskCreate,
)
from app.contracts.run import AsyncAccepted
from app.contracts.source import SourceDocument
from app.config.settings import Settings
from app.db.session import get_db
from app.repositories import idempotency
from app.repositories import projects as projects_repo
from app.repositories import sources as sources_repo
from app.research import import_service, service
from app.research.executor import research_executor
from app.security.deps import (
    AuthContext,
    require_session,
    require_unsafe_guards,
    settings_dep,
)

router = APIRouter(tags=["Research"])


def _require_project(db: Session, project_id: str, workspace_id: str):
    project = projects_repo.get_scoped(db, project_id, workspace_id)
    if project is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Project not found.",
        )
    return project


def _require_web_research_enabled(settings: Settings) -> None:
    available = settings.web_research_enabled and (
        settings.web_research_fake_provider or bool(settings.firecrawl_api_key)
    )
    if not available:
        raise ProblemException(
            status=503, code="web_research_unavailable", title="Service Unavailable",
            detail="Öffentliche Recherche ist in dieser Umgebung nicht verfügbar.",
        )


@router.post("/projects/{project_id}/research-tasks", status_code=202)
def create_research_task(
    project_id: str,
    payload: ResearchTaskCreate,
    background: BackgroundTasks,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=8, max_length=128
    ),
) -> AsyncAccepted:
    project = _require_project(db, project_id, context.user.workspace_id)
    _require_web_research_enabled(settings)

    fingerprint = idempotency.fingerprint(
        "POST", f"/projects/{project_id}/research-tasks", payload.model_dump_json()
    )
    scope = f"{context.user.workspace_id}:{context.user.id}:POST:/research-tasks"
    existing = idempotency.get(db, scope, idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ProblemException(
                status=409, code="idempotency_conflict", title="Conflict",
                detail="Idempotency-Key reused with a different request.",
            )
        return AsyncAccepted(**existing.response_body)

    _task, _op, accepted = service.create_research_task(
        db, project=project, payload=payload, actor_user_id=context.user.id,
        idempotency_key=idempotency_key,
    )
    db.commit()
    idempotency.save(
        db, scope=scope, key=idempotency_key, request_fingerprint=fingerprint,
        response_status=202, response_body=accepted.model_dump(mode="json"),
        resource_id=accepted.resource_id,
    )
    db.commit()
    background.add_task(research_executor, accepted.resource_id, accepted.operation_id)
    return accepted


@router.get("/research-tasks/{task_id}", response_model=ResearchTaskContract)
def get_research_task(
    task_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> ResearchTaskContract:
    task = service.get_task(db, task_id, context.user.workspace_id)
    if task is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Research task not found.",
        )
    return service.task_to_contract(task)


@router.get(
    "/projects/{project_id}/research-results",
    response_model=list[ResearchResultContract],
)
def list_research_results(
    project_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> list[ResearchResultContract]:
    _require_project(db, project_id, context.user.workspace_id)
    results = service.list_results(db, project_id, context.user.workspace_id)
    return [service.result_to_contract(r) for r in results]


@router.post("/research-results/{result_id}/import", status_code=201,
             response_model=SourceDocument)
def import_research_result(
    result_id: str,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=8, max_length=128
    ),
) -> SourceDocument:
    _require_web_research_enabled(settings)
    result = service.get_result(db, result_id, context.user.workspace_id)
    if result is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Research result not found.",
        )
    scope = f"{context.user.workspace_id}:{context.user.id}:POST:/research-results/import"
    fingerprint = idempotency.fingerprint("POST", f"/research-results/{result_id}/import", "")
    existing = idempotency.get(db, scope, idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ProblemException(
                status=409, code="idempotency_conflict", title="Conflict",
                detail="Idempotency-Key reused with a different request.",
            )
        return SourceDocument(**existing.response_body)

    task = service.get_task(db, result.research_task_id, context.user.workspace_id)
    project = _require_project(db, task.project_id, context.user.workspace_id)
    try:
        doc = import_service.import_result(
            db, result=result, task=task, project=project, actor_user_id=context.user.id,
        )
    except import_service.ImportBlocked as exc:
        db.commit()  # persist control/audit + result status changes
        raise ProblemException(
            status=exc.status, code=exc.code, title="Import refused", detail=exc.detail,
        ) from exc

    contract = sources_repo.to_contract(doc)
    idempotency.save(
        db, scope=scope, key=idempotency_key, request_fingerprint=fingerprint,
        response_status=201, response_body=contract.model_dump(mode="json"),
        resource_id=doc.source_id,
    )
    db.commit()
    return contract
