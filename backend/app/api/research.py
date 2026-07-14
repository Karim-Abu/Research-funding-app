"""Research router (Milestone 9I-A) — createResearchTask / getResearchTask /
listResearchResults / importResearchResult.

The legacy createResearchTask route remains for compatibility, but it can no longer
execute a client-provided free query. It delegates only a server-loaded, approved query
bound to an approved public research brief into the existing market/partner task services.
The data policy still gates the external call.
"""
from __future__ import annotations

import uuid

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
from app.db.models import ResearchBrief, SearchQueryApproval
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
from app.security.data_class import derive_data_class, is_external_blocked

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


def _require_brief_approval(
    db: Session, *, project_id: str, workspace_id: str, approval_id: str | None
) -> tuple[ResearchBrief, SearchQueryApproval]:
    approval = db.get(SearchQueryApproval, approval_id) if approval_id else None
    brief = (
        db.get(ResearchBrief, approval.research_brief_id)
        if approval is not None and approval.research_brief_id
        else None
    )
    provenance_invalid = (
        approval is None
        or brief is None
        or approval.project_id != project_id
        or approval.workspace_id != workspace_id
        or brief.project_id != project_id
        or brief.workspace_id != workspace_id
        or brief.status != "approved"
        or approval.research_module not in (brief.modules or [])
    )
    if provenance_invalid:
        raise ProblemException(
            status=422,
            code="research_brief_approval_required",
            title="Research request refused",
            detail=(
                "Die Recherche muss aus einem freigegebenen öffentlichen "
                "Recherchebrief und einer freigegebenen Query gestartet werden."
            ),
        )
    assert approval is not None and brief is not None
    if approval.status == "used":
        raise ProblemException(
            status=409, code="approval_already_used", title="Research request refused",
            detail="Diese Query-Freigabe wurde bereits verwendet.",
        )
    if approval.status != "approved":
        raise ProblemException(
            status=422, code="approval_not_approved", title="Research request refused",
            detail="Die gebundene Query ist nicht freigegeben.",
        )
    return brief, approval


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
    if is_external_blocked(derive_data_class(project.data_classification or {})):
        raise ProblemException(
            status=403, code="web_research_class_blocked", title="Research request refused",
            detail="Webrecherche ist für diese Datenklasse gesperrt.",
        )
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

    _brief, approval = _require_brief_approval(
        db,
        project_id=project.project_id,
        workspace_id=project.workspace_id,
        approval_id=payload.approval_id,
    )

    try:
        task_id = str(uuid.uuid4())
        operation_id = str(uuid.uuid4())
        create = (
            service.create_partner_research_task
            if approval.research_module == "swiss_research_partners"
            else service.create_market_research_task
        )
        _task, _op = create(
            db,
            project=project,
            query_preview=approval.sanitized_query,
            actor_user_id=context.user.id,
            max_results=payload.max_results,
            task_id=task_id,
            operation_id=operation_id,
            idempotency_key=idempotency_key,
            approval=approval,
        )
        accepted = AsyncAccepted(
            operation_id=operation_id,
            resource_type="research_task",
            resource_id=task_id,
            status="queued",
            poll_url=f"/api/v1/operations/{operation_id}",
        )
    except service.ResearchBlocked as exc:
        db.commit()  # persist the firewall control/audit records
        raise ProblemException(
            status=exc.status, code=exc.code, title="Search query refused",
            detail=exc.detail,
        ) from exc
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


@router.post("/research-results/{result_id}/discard",
             response_model=ResearchResultContract)
def discard_research_result(
    result_id: str,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> ResearchResultContract:
    """R8 (Anforderung 9): Ergebnis-Kandidat explizit verwerfen (persistiert) —
    verworfene Ergebnisse werden nie A2-Kontext und bleiben nach Reload verworfen."""
    result = service.get_result(db, result_id, context.user.workspace_id)
    if result is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Research result not found.",
        )
    try:
        service.discard_result(db, result=result, actor_user_id=context.user.id)
    except service.ResearchBlocked as exc:
        raise ProblemException(
            status=exc.status, code=exc.code, title="Discard refused", detail=exc.detail,
        ) from exc
    db.commit()
    return service.result_to_contract(result)


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
