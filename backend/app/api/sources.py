"""Sources router — list / upload files / create text / import url / get / delete."""
from __future__ import annotations

import json
import ipaddress
from urllib.parse import urlparse

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    Response,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.config.settings import Settings
from app.contracts.classification import DataClassification
from app.contracts.source import SourceDocument, TextSourceCreate, UrlSourceCreate
from app.db.session import get_db
from app.ingestion.pipeline import process_source_version
from app.ingestion.signatures import UnsupportedFileError, detect_source_type
from app.policy.classification import resolve_effective_classification
from app.repositories import audit, idempotency
from app.repositories import projects as projects_repo
from app.repositories import sources as sources_repo
from app.security.deps import (
    AuthContext,
    require_session,
    require_unsafe_guards,
    settings_dep,
)
from app.sources import service as source_service
from app.storage import get_storage

router = APIRouter(tags=["Sources"])

def _sha256(data: bytes) -> str:
    return source_service.sha256_bytes(data)


def _require_project(db: Session, project_id: str, workspace_id: str):
    project = projects_repo.get_scoped(db, project_id, workspace_id)
    if project is None:
        raise ProblemException(
            status=404,
            code="not_found",
            title="Resource not found",
            detail="Project not found.",
        )
    return project


def _parse_classification(raw: str | dict) -> dict:
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        return DataClassification(**data).model_dump()
    except Exception as exc:  # noqa: BLE001
        raise ProblemException(
            status=422,
            code="invalid_classification",
            title="Unprocessable Entity",
            detail="data_classification is missing or invalid.",
        ) from exc


def _record_upload_controls(db, doc, version, downgrade: bool) -> None:
    source_service.record_upload_controls(db, doc, version, downgrade)


def _idempotency_scope(context: AuthContext, path: str) -> str:
    return f"{context.user.workspace_id}:{context.user.id}:POST:{path}"


# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/sources", response_model=list[SourceDocument]
)
def list_sources(
    project_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> list[SourceDocument]:
    _require_project(db, project_id, context.user.workspace_id)
    rows = sources_repo.list_by_project(db, project_id, context.user.workspace_id)
    return [sources_repo.to_contract(row) for row in rows]


@router.post(
    "/projects/{project_id}/sources/files",
    response_model=list[SourceDocument],
    status_code=202,
)
async def upload_files(
    project_id: str,
    response: Response,
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    data_classification_json: str = Form(...),
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=8, max_length=128
    ),
) -> list[SourceDocument]:
    project = _require_project(db, project_id, context.user.workspace_id)
    source_dc = _parse_classification(data_classification_json)

    if len(files) > settings.max_files_per_request:
        raise ProblemException(
            status=413, code="too_many_files", title="Payload Too Large",
            detail="Too many files in one request.",
        )

    # Read + validate all files first (atomic — no partial ingestion).
    prepared: list[tuple[str, str, bytes]] = []  # (filename, type, data)
    total = 0
    for upload in files:
        data = await upload.read()
        total += len(data)
        if len(data) > settings.max_upload_bytes or total > settings.max_total_request_bytes:
            raise ProblemException(
                status=413, code="file_too_large", title="Payload Too Large",
                detail="A file exceeds the configured upload limit.",
            )
        try:
            source_type = detect_source_type(upload.filename or "", data)
        except UnsupportedFileError as exc:
            raise ProblemException(
                status=415, code="unsupported_media_type",
                title="Unsupported Media Type",
                detail="Unsupported or mismatched file type.",
            ) from exc
        prepared.append((upload.filename or "unnamed", source_type, data))

    fingerprint = idempotency.fingerprint(
        "POST",
        f"/projects/{project_id}/sources/files",
        json.dumps(
            {
                "dc": source_dc,
                "files": [(n, len(d)) for n, _, d in prepared],
            },
            sort_keys=True,
        ),
    )
    scope = _idempotency_scope(context, "/sources/files")
    existing = idempotency.get(db, scope, idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ProblemException(
                status=409, code="idempotency_conflict", title="Conflict",
                detail="Idempotency-Key reused with a different request.",
            )
        response.status_code = existing.response_status
        return [SourceDocument(**item) for item in existing.response_body["sources"]]

    effective, downgrade = resolve_effective_classification(
        project.data_classification, source_dc
    )
    storage = get_storage()
    created = []
    for filename, source_type, data in prepared:
        ref = storage.put(data)
        doc = sources_repo.create_document(
            db, project_id=project_id, workspace_id=context.user.workspace_id,
            created_by=context.user.id, name=filename, source_type=source_type,
            classification=effective, status="uploaded",
        )
        version = sources_repo.create_version(
            db, document=doc, original_content_hash=_sha256(data),
            classification=effective, storage_ref=ref, original_filename=filename,
            byte_size=len(data), mime_type=f"application/{source_type}",
            status="uploaded",
        )
        _record_upload_controls(db, doc, version, downgrade)
        audit.record(
            db, workspace_id=doc.workspace_id, actor_user_id=context.user.id,
            action="source.create", target_type="source", target_id=doc.source_id,
        )
        created.append((doc, version))

    body = {"sources": [sources_repo.to_contract(d).model_dump(mode="json") for d, _ in created]}
    idempotency.save(
        db, scope=scope, key=idempotency_key, request_fingerprint=fingerprint,
        response_status=202, response_body=body, resource_id=created[0][0].source_id,
    )
    db.commit()

    for _, version in created:
        background.add_task(process_source_version, version.source_version_id)
    return [sources_repo.to_contract(doc) for doc, _ in created]


@router.post(
    "/projects/{project_id}/sources/text",
    response_model=SourceDocument,
    status_code=201,
)
def create_text_source(
    project_id: str,
    payload: TextSourceCreate,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=8, max_length=128
    ),
) -> SourceDocument:
    project = _require_project(db, project_id, context.user.workspace_id)

    fingerprint = idempotency.fingerprint(
        "POST", f"/projects/{project_id}/sources/text", payload.model_dump_json()
    )
    scope = _idempotency_scope(context, "/sources/text")
    existing = idempotency.get(db, scope, idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ProblemException(
                status=409, code="idempotency_conflict", title="Conflict",
                detail="Idempotency-Key reused with a different request.",
            )
        return SourceDocument(**existing.response_body)

    doc, version = source_service.prepare_text_source(
        db,
        project=project,
        payload=payload,
        actor_user_id=context.user.id,
    )
    db.commit()

    # Text is processed synchronously (no I/O-heavy step) → 201 with status.
    process_source_version(version.source_version_id)
    db.expire_all()
    doc = sources_repo.get_scoped(db, doc.source_id, context.user.workspace_id)
    result = sources_repo.to_contract(doc)
    idempotency.save(
        db, scope=scope, key=idempotency_key, request_fingerprint=fingerprint,
        response_status=201, response_body=result.model_dump(mode="json"),
        resource_id=doc.source_id,
    )
    db.commit()
    return result


def _validate_manual_source_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ProblemException(
            status=422, code="invalid_public_url", title="Unprocessable Entity",
            detail="Bitte eine öffentliche HTTPS-URL ohne Zugangsdaten angeben.",
        )
    host = parsed.hostname.casefold().rstrip(".")
    if host == "localhost" or host.endswith(".localhost"):
        raise ProblemException(
            status=422, code="invalid_public_url", title="Unprocessable Entity",
            detail="Lokale URLs können nicht als öffentliche Quelle importiert werden.",
        )
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ProblemException(
                status=422, code="invalid_public_url", title="Unprocessable Entity",
                detail="Private Netzwerkadressen sind nicht zulässig.",
            )
    except ValueError:
        pass
    return value.strip()


@router.post(
    "/projects/{project_id}/sources/url", response_model=SourceDocument, status_code=201
)
def import_url_source(
    project_id: str,
    payload: UrlSourceCreate,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=8, max_length=128
    ),
) -> SourceDocument:
    project = _require_project(db, project_id, context.user.workspace_id)
    if not payload.manual_content or not payload.manual_content.strip():
        raise ProblemException(
            status=503,
            code="url_import_unavailable",
            title="Service Unavailable",
            detail=(
                "Ein automatischer URL-Abruf ist nicht verfügbar. Bitte den öffentlichen "
                "Seiteninhalt manuell einfügen oder ein PDF hochladen."
            ),
        )
    source_url = _validate_manual_source_url(payload.url)
    fingerprint = idempotency.fingerprint(
        "POST", f"/projects/{project_id}/sources/url", payload.model_dump_json()
    )
    scope = _idempotency_scope(context, "/sources/url")
    existing = idempotency.get(db, scope, idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ProblemException(
                status=409, code="idempotency_conflict", title="Conflict",
                detail="Idempotency-Key reused with a different request.",
            )
        return SourceDocument(**existing.response_body)

    doc, version = source_service.prepare_text_source(
        db,
        project=project,
        payload=TextSourceCreate(
            name=payload.name or (urlparse(source_url).hostname or "Webquelle"),
            text=payload.manual_content,
            data_classification=payload.data_classification,
        ),
        actor_user_id=context.user.id,
    )
    doc.type = "url"
    doc.source_url = source_url
    db.commit()
    process_source_version(version.source_version_id)
    db.expire_all()
    doc = sources_repo.get_scoped(db, doc.source_id, context.user.workspace_id)
    result = sources_repo.to_contract(doc)
    idempotency.save(
        db, scope=scope, key=idempotency_key, request_fingerprint=fingerprint,
        response_status=201, response_body=result.model_dump(mode="json"),
        resource_id=doc.source_id,
    )
    db.commit()
    return result


@router.get("/sources/{source_id}", response_model=SourceDocument)
def get_source(
    source_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> SourceDocument:
    doc = sources_repo.get_scoped(db, source_id, context.user.workspace_id)
    if doc is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Source not found.",
        )
    return sources_repo.to_contract(doc)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(
    source_id: str,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> Response:
    doc = sources_repo.get_scoped(db, source_id, context.user.workspace_id)
    if doc is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Source not found.",
        )
    if doc.status == "processing":
        raise ProblemException(
            status=409, code="SOURCE_PROCESSING", title="Conflict",
            detail="The source is still being processed.",
        )
    # A source frozen into an analysis-run snapshot must not be physically
    # removed (run reproducibility / auditability).
    from app.runs import snapshot as run_snapshot

    if run_snapshot.is_source_referenced(db, source_id):
        raise ProblemException(
            status=409, code="SOURCE_IN_USE", title="Conflict",
            detail="The source is referenced by an analysis run and cannot be deleted.",
        )
    storage = get_storage()
    refs = sources_repo.physically_delete(db, doc)
    audit.record(
        db, workspace_id=context.user.workspace_id, actor_user_id=context.user.id,
        action="source.delete", target_type="source", target_id=source_id,
    )
    db.commit()
    for ref in refs:
        try:
            storage.delete(ref)
        except Exception:  # noqa: BLE001 — storage cleanup is best-effort
            pass
    return Response(status_code=204)
