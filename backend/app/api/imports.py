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
    ImportUndoRequest,
    StructuredImportCandidate,
    StructuredImportDecisionRequest,
    StructuredImportSummary,
    StructuredImportUndoRequest,
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


def _require_import_candidate(db: Session, candidate_id: str, workspace_id: str):
    candidate = db.get(ImportCandidateRow, candidate_id)
    if candidate is None or candidate.workspace_id != workspace_id:
        raise ProblemException(
            status=404,
            code="import_candidate_not_found",
            title="Resource not found",
            detail="Import candidate not found.",
        )
    return candidate


def _require_structured_candidate(
    db: Session, candidate_id: str, workspace_id: str
):
    candidate = db.get(StructuredImportCandidateRow, candidate_id)
    if candidate is None or candidate.workspace_id != workspace_id:
        raise ProblemException(
            status=404,
            code="import_candidate_not_found",
            title="Resource not found",
            detail="Structured import candidate not found.",
        )
    return candidate


def _optional_run(db: Session, run_id: str | None, candidate, workspace_id: str):
    if run_id is None:
        return None
    run = runs_repo.get_scoped(db, run_id, workspace_id)
    if run is None or run.project_id != candidate.project_id:
        raise ProblemException(
            status=409,
            code="import_project_source_mismatch",
            title="Conflict",
            detail="Der Analyse-Lauf gehört nicht zum Projekt des Importkandidaten.",
        )
    return run


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
    candidate = _require_import_candidate(
        db, candidate_id, context.user.workspace_id
    )
    import_service.validate_mutation_scope(
        candidate,
        project_id=payload.project_id,
        source_id=payload.source_id,
        expected_revision_id=payload.expected_revision_id,
        require_preconditions=True,
    )

    run = _optional_run(
        db, payload.run_id, candidate, context.user.workspace_id
    )

    scope = f"{context.user.workspace_id}:{context.user.id}:POST:/imports/decision"
    fingerprint = idempotency.fingerprint(
        "POST", f"/imports/{candidate_id}/decision", payload.model_dump_json()
    )
    existing = _idempotent_replay(db, scope, idempotency_key, fingerprint)
    if existing is not None:
        return ImportCandidate(**existing.response_body).model_copy(
            update={"idempotent_replay": True}
        )

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
    candidate = _require_structured_candidate(
        db, candidate_id, context.user.workspace_id
    )
    import_service.validate_mutation_scope(
        candidate,
        project_id=payload.project_id,
        source_id=payload.source_id,
        expected_revision_id=payload.expected_revision_id,
        require_preconditions=True,
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
        return StructuredImportCandidate(**existing.response_body).model_copy(
            update={"idempotent_replay": True}
        )

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


@router.patch("/imports/{candidate_id}/decision", response_model=ImportCandidate)
def revise_import_candidate(
    candidate_id: str,
    payload: ImportDecisionRequest,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = _IDEMPOTENCY,
) -> ImportCandidate:
    candidate = _require_import_candidate(db, candidate_id, context.user.workspace_id)
    import_service.validate_mutation_scope(
        candidate,
        project_id=payload.project_id,
        source_id=payload.source_id,
        expected_revision_id=payload.expected_revision_id,
        require_preconditions=True,
    )
    run = _optional_run(db, payload.run_id, candidate, context.user.workspace_id)
    scope = f"{context.user.workspace_id}:{context.user.id}:PATCH:/imports/decision"
    fingerprint = idempotency.fingerprint(
        "PATCH", f"/imports/{candidate_id}/decision", payload.model_dump_json()
    )
    existing = _idempotent_replay(db, scope, idempotency_key, fingerprint)
    if existing is not None:
        return ImportCandidate(**existing.response_body).model_copy(
            update={"idempotent_replay": True}
        )
    try:
        row, replay = import_service.revise_candidate(
            db,
            candidate=candidate,
            decision=payload.decision,
            run=run,
            confirm_overwrite=payload.confirm_overwrite,
            actor_user_id=context.user.id,
            edited_text=payload.edited_text,
        )
    except ProblemException:
        db.commit()
        raise
    result = import_service.to_contract(row, idempotent_replay=replay)
    idempotency.save(
        db,
        scope=scope,
        key=idempotency_key,
        request_fingerprint=fingerprint,
        response_status=200,
        response_body=result.model_dump(mode="json"),
        resource_id=row.import_candidate_id,
    )
    db.commit()
    return result


def _narrative_control_mutation(
    *,
    action: str,
    candidate_id: str,
    payload: ImportUndoRequest,
    context: AuthContext,
    db: Session,
    idempotency_key: str,
) -> ImportCandidate:
    candidate = _require_import_candidate(db, candidate_id, context.user.workspace_id)
    import_service.validate_mutation_scope(
        candidate,
        project_id=payload.project_id,
        source_id=payload.source_id,
        expected_revision_id=payload.expected_revision_id,
        require_preconditions=True,
    )
    scope = f"{context.user.workspace_id}:{context.user.id}:POST:/imports/{action}"
    path = f"/imports/{candidate_id}/{action}"
    fingerprint = idempotency.fingerprint("POST", path, payload.model_dump_json())
    existing = _idempotent_replay(db, scope, idempotency_key, fingerprint)
    if existing is not None:
        return ImportCandidate(**existing.response_body).model_copy(
            update={"idempotent_replay": True}
        )
    try:
        if action == "reset":
            run = _optional_run(
                db, payload.run_id, candidate, context.user.workspace_id
            )
            row, replay = import_service.reset_candidate(
                db,
                candidate=candidate,
                run=run,
                confirm_overwrite=payload.confirm_overwrite,
                actor_user_id=context.user.id,
            )
        else:
            row, replay = import_service.undo_candidate(
                db, candidate=candidate, actor_user_id=context.user.id
            )
    except ProblemException:
        db.commit()
        raise
    result = import_service.to_contract(row, idempotent_replay=replay)
    idempotency.save(
        db,
        scope=scope,
        key=idempotency_key,
        request_fingerprint=fingerprint,
        response_status=200,
        response_body=result.model_dump(mode="json"),
        resource_id=row.import_candidate_id,
    )
    db.commit()
    return result


@router.post("/imports/{candidate_id}/reset", response_model=ImportCandidate)
def reset_import_candidate(
    candidate_id: str,
    payload: ImportUndoRequest,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = _IDEMPOTENCY,
) -> ImportCandidate:
    return _narrative_control_mutation(
        action="reset",
        candidate_id=candidate_id,
        payload=payload,
        context=context,
        db=db,
        idempotency_key=idempotency_key,
    )


@router.post("/imports/{candidate_id}/undo", response_model=ImportCandidate)
def undo_import_candidate(
    candidate_id: str,
    payload: ImportUndoRequest,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = _IDEMPOTENCY,
) -> ImportCandidate:
    return _narrative_control_mutation(
        action="undo",
        candidate_id=candidate_id,
        payload=payload,
        context=context,
        db=db,
        idempotency_key=idempotency_key,
    )


@router.patch(
    "/structured-imports/{candidate_id}/decision",
    response_model=StructuredImportCandidate,
)
def revise_structured_import_candidate(
    candidate_id: str,
    payload: StructuredImportDecisionRequest,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = _IDEMPOTENCY,
) -> StructuredImportCandidate:
    candidate = _require_structured_candidate(
        db, candidate_id, context.user.workspace_id
    )
    import_service.validate_mutation_scope(
        candidate,
        project_id=payload.project_id,
        source_id=payload.source_id,
        expected_revision_id=payload.expected_revision_id,
        require_preconditions=True,
    )
    scope = (
        f"{context.user.workspace_id}:{context.user.id}:"
        "PATCH:/structured-imports/decision"
    )
    fingerprint = idempotency.fingerprint(
        "PATCH",
        f"/structured-imports/{candidate_id}/decision",
        payload.model_dump_json(),
    )
    existing = _idempotent_replay(db, scope, idempotency_key, fingerprint)
    if existing is not None:
        return StructuredImportCandidate(**existing.response_body).model_copy(
            update={"idempotent_replay": True}
        )
    try:
        row, replay = import_service.revise_structured_candidate(
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
    result = import_service.to_structured_contract(
        db, row, idempotent_replay=replay
    )
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


def _structured_control_mutation(
    *,
    action: str,
    candidate_id: str,
    payload: StructuredImportUndoRequest,
    context: AuthContext,
    db: Session,
    idempotency_key: str,
) -> StructuredImportCandidate:
    candidate = _require_structured_candidate(
        db, candidate_id, context.user.workspace_id
    )
    import_service.validate_mutation_scope(
        candidate,
        project_id=payload.project_id,
        source_id=payload.source_id,
        expected_revision_id=payload.expected_revision_id,
        require_preconditions=True,
    )
    scope = (
        f"{context.user.workspace_id}:{context.user.id}:"
        f"POST:/structured-imports/{action}"
    )
    path = f"/structured-imports/{candidate_id}/{action}"
    fingerprint = idempotency.fingerprint("POST", path, payload.model_dump_json())
    existing = _idempotent_replay(db, scope, idempotency_key, fingerprint)
    if existing is not None:
        return StructuredImportCandidate(**existing.response_body).model_copy(
            update={"idempotent_replay": True}
        )
    try:
        if action == "reset":
            row, replay = import_service.reset_structured_candidate(
                db,
                candidate=candidate,
                actor_user_id=context.user.id,
                confirm_overwrite=payload.confirm_overwrite,
            )
        else:
            row, replay = import_service.undo_structured_candidate(
                db, candidate=candidate, actor_user_id=context.user.id
            )
    except ProblemException:
        db.commit()
        raise
    result = import_service.to_structured_contract(
        db, row, idempotent_replay=replay
    )
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


@router.post(
    "/structured-imports/{candidate_id}/reset",
    response_model=StructuredImportCandidate,
)
def reset_structured_import_candidate(
    candidate_id: str,
    payload: StructuredImportUndoRequest,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = _IDEMPOTENCY,
) -> StructuredImportCandidate:
    return _structured_control_mutation(
        action="reset",
        candidate_id=candidate_id,
        payload=payload,
        context=context,
        db=db,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/structured-imports/{candidate_id}/undo",
    response_model=StructuredImportCandidate,
)
def undo_structured_import_candidate(
    candidate_id: str,
    payload: StructuredImportUndoRequest,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = _IDEMPOTENCY,
) -> StructuredImportCandidate:
    return _structured_control_mutation(
        action="undo",
        candidate_id=candidate_id,
        payload=payload,
        context=context,
        db=db,
        idempotency_key=idempotency_key,
    )
