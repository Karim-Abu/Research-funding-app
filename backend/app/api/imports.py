"""Imports router (R3.2): Kandidaten erzeugen / auflisten / entscheiden.

Der Datei-Upload selbst läuft über den bestehenden Quellen-Endpoint
(``POST /projects/{id}/sources/files``) mit allen Guards; hier wird eine
bereits verarbeitete Quelle deterministisch auf die Portal-Felder gemappt
und der HITL-Entscheidungsfluss abgewickelt.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.contracts.imports import (
    ImportCandidate,
    ImportCandidatesCreate,
    ImportDecisionRequest,
    StructuredImportCandidate,
    StructuredImportDecisionRequest,
    StructuredImportSummary,
)
from app.db.models import ImportCandidate as ImportCandidateRow
from app.db.models import StructuredImportCandidate as StructuredImportCandidateRow
from app.db.session import get_db
from app.imports import service as import_service
from app.repositories import idempotency
from app.repositories import projects as projects_repo
from app.repositories import runs as runs_repo
from app.repositories import sources as sources_repo
from app.security.deps import AuthContext, require_session, require_unsafe_guards

router = APIRouter(tags=["Imports"])

_IDEMPOTENCY = Header(..., alias="Idempotency-Key", min_length=8, max_length=128)


def _require_project(db: Session, project_id: str, workspace_id: str):
    project = projects_repo.get_scoped(db, project_id, workspace_id)
    if project is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Project not found.",
        )
    return project


def _idempotent_replay(db, scope, key, fingerprint):
    existing = idempotency.get(db, scope, key)
    if existing is None:
        return None
    if existing.request_fingerprint != fingerprint:
        raise ProblemException(
            status=409, code="idempotency_conflict", title="Conflict",
            detail="Idempotency-Key reused with a different request.",
        )
    return existing


@router.get(
    "/projects/{project_id}/imports", response_model=list[ImportCandidate]
)
def list_import_candidates(
    project_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> list[ImportCandidate]:
    _require_project(db, project_id, context.user.workspace_id)
    rows = import_service.list_candidates(db, project_id)
    return [import_service.to_contract(row) for row in rows]


@router.get(
    "/projects/{project_id}/structured-imports",
    response_model=list[StructuredImportCandidate],
)
def list_structured_import_candidates(
    project_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> list[StructuredImportCandidate]:
    _require_project(db, project_id, context.user.workspace_id)
    rows = import_service.list_structured_candidates(db, project_id)
    return [import_service.to_structured_contract(db, row) for row in rows]


@router.get(
    "/projects/{project_id}/structured-imports/summary",
    response_model=StructuredImportSummary,
)
def structured_import_summary(
    project_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> StructuredImportSummary:
    _require_project(db, project_id, context.user.workspace_id)
    return import_service.structured_summary(db, project_id)


@router.post(
    "/projects/{project_id}/imports",
    response_model=list[ImportCandidate],
    status_code=201,
)
def create_import_candidates(
    project_id: str,
    payload: ImportCandidatesCreate,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = _IDEMPOTENCY,
) -> list[ImportCandidate]:
    _require_project(db, project_id, context.user.workspace_id)
    source = sources_repo.get_scoped(db, payload.source_id, context.user.workspace_id)
    if source is None or source.project_id != project_id:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Source not found.",
        )

    scope = f"{context.user.workspace_id}:{context.user.id}:POST:/imports"
    fingerprint = idempotency.fingerprint(
        "POST", f"/projects/{project_id}/imports", payload.model_dump_json()
    )
    existing = _idempotent_replay(db, scope, idempotency_key, fingerprint)
    if existing is not None:
        return [ImportCandidate(**item) for item in existing.response_body["candidates"]]

    rows = import_service.create_candidates(
        db, source=source, actor_user_id=context.user.id
    )
    body = {
        "candidates": [
            import_service.to_contract(row).model_dump(mode="json") for row in rows
        ]
    }
    idempotency.save(
        db, scope=scope, key=idempotency_key, request_fingerprint=fingerprint,
        response_status=201, response_body=body,
        resource_id=source.source_id,
    )
    db.commit()
    return [import_service.to_contract(row) for row in rows]


@router.post(
    "/imports/{candidate_id}/decision", response_model=ImportCandidate
)
def decide_import_candidate(
    candidate_id: str,
    payload: ImportDecisionRequest,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = _IDEMPOTENCY,
) -> ImportCandidate:
    candidate = db.get(ImportCandidateRow, candidate_id)
    if candidate is None or candidate.workspace_id != context.user.workspace_id:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Import candidate not found.",
        )

    run = None
    if payload.run_id is not None:
        run = runs_repo.get_scoped(db, payload.run_id, context.user.workspace_id)
        if run is None or run.project_id != candidate.project_id:
            raise ProblemException(
                status=404, code="not_found", title="Resource not found",
                detail="Run not found.",
            )

    scope = f"{context.user.workspace_id}:{context.user.id}:POST:/imports/decision"
    fingerprint = idempotency.fingerprint(
        "POST", f"/imports/{candidate_id}/decision", payload.model_dump_json()
    )
    existing = _idempotent_replay(db, scope, idempotency_key, fingerprint)
    if existing is not None:
        return ImportCandidate(**existing.response_body)

    try:
        row = import_service.decide_candidate(
            db, candidate=candidate, decision=payload.decision, run=run,
            confirm_overwrite=payload.confirm_overwrite,
            actor_user_id=context.user.id,
            edited_text=payload.edited_text,
        )
    except ProblemException:
        # Konflikt-Markierung (decision="conflict") muss persistiert werden,
        # damit die UI den Zustand anzeigen kann.
        db.commit()
        raise
    result = import_service.to_contract(row)
    idempotency.save(
        db, scope=scope, key=idempotency_key, request_fingerprint=fingerprint,
        response_status=200, response_body=result.model_dump(mode="json"),
        resource_id=row.import_candidate_id,
    )
    db.commit()
    return result


@router.post(
    "/structured-imports/{candidate_id}/decision",
    response_model=StructuredImportCandidate,
)
def decide_structured_import_candidate(
    candidate_id: str,
    payload: StructuredImportDecisionRequest,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = _IDEMPOTENCY,
) -> StructuredImportCandidate:
    candidate = db.get(StructuredImportCandidateRow, candidate_id)
    if candidate is None or candidate.workspace_id != context.user.workspace_id:
        raise ProblemException(
            status=404,
            code="not_found",
            title="Resource not found",
            detail="Structured import candidate not found.",
        )

    scope = (
        f"{context.user.workspace_id}:{context.user.id}:"
        "POST:/structured-imports/decision"
    )
    fingerprint = idempotency.fingerprint(
        "POST",
        f"/structured-imports/{candidate_id}/decision",
        payload.model_dump_json(),
    )
    existing = _idempotent_replay(db, scope, idempotency_key, fingerprint)
    if existing is not None:
        return StructuredImportCandidate(**existing.response_body)

    try:
        row = import_service.decide_structured_candidate(
            db,
            candidate=candidate,
            decision=payload.decision,
            actor_user_id=context.user.id,
            edited_payload_json=payload.edited_payload_json,
            confirm_overwrite=payload.confirm_overwrite,
        )
    except ProblemException:
        db.commit()
        raise
    result = import_service.to_structured_contract(db, row)
    idempotency.save(
        db,
        scope=scope,
        key=idempotency_key,
        request_fingerprint=fingerprint,
        response_status=200,
        response_body=result.model_dump(mode="json"),
        resource_id=row.candidate_id,
    )
    db.commit()
    return result
