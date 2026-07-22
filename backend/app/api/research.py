"""Research router (Milestone 9I-A) — createResearchTask / getResearchTask /
listResearchResults / importResearchResult.

The legacy createResearchTask route remains for compatibility, but it can no longer
execute a client-provided free query. It delegates only a server-loaded, approved query
bound to an approved public research brief into the existing market/partner task services.
The data policy still gates the external call.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.contracts.research import (
    ExternalAnchorCreate,
    ExternalAnchorPassageView,
    ExternalAnchorView,
    ResearchHandoffSource,
    ResearchHandoffView,
    ResearchResult as ResearchResultContract,
    ResearchTask as ResearchTaskContract,
    ResearchTaskCreate,
)
from app.contracts.run import AsyncAccepted
from app.contracts.research_brief import (
    PartnerEligibilityReviewInput, PartnerEligibilityReviewView,
)
from app.contracts.source import SourceDocument
from app.config.settings import Settings
from app.db.models import (
    EvidenceAnchor, MarketComparison, ResearchBrief, ResearchResult, ResearchTask,
    SearchQueryApproval, SourceDocument as SourceDocumentModel, SourceFragment,
    SourceVersion,
)
from app.db.session import get_db
from app.repositories import idempotency
from app.repositories import projects as projects_repo
from app.repositories import sources as sources_repo
from app.research import import_service, service
from app.market import verify as market_verify
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


@router.get(
    "/research-results/{result_id}/anchor-passages",
    response_model=list[ExternalAnchorPassageView],
)
def list_external_anchor_passages(
    result_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
    fragment_id: str | None = Query(default=None),
    start_offset: int | None = Query(default=None, ge=0),
    end_offset: int | None = Query(default=None, gt=0),
    quote_hash: str | None = Query(default=None, pattern=r"^[0-9a-f]{64}$"),
) -> list[ExternalAnchorPassageView]:
    """Return bounded exact passages from one current imported public source.

    This is the read-only human-review projection used before an exact external
    anchor is released. Search snippets are deliberately absent.
    """
    result = service.get_result(db, result_id, context.user.workspace_id)
    if result is None or result.status != "imported" or not result.source_document_id:
        raise ProblemException(
            status=409, code="external_anchor_source_not_ready", title="Anchor refused",
            detail="Only an imported public source can provide review passages.",
        )
    task = service.get_task(db, result.research_task_id, context.user.workspace_id)
    if task is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Research task not found.",
        )
    document = db.get(SourceDocumentModel, result.source_document_id)
    version = (
        db.get(SourceVersion, document.current_source_version_id)
        if document is not None and document.current_source_version_id else None
    )
    if (
        document is None or version is None
        or document.project_id != task.project_id
        or document.workspace_id != context.user.workspace_id
        or (document.data_classification or {}).get("origin") != "public_source"
        or version.content_safety_status not in ("passed", "human_released")
    ):
        raise ProblemException(
            status=409, code="external_anchor_source_not_ready", title="Anchor refused",
            detail="The current public source version is not safe for passage review.",
        )
    domain = (urlparse(result.final_url or result.source_url).hostname or "").casefold()
    selector_values = (fragment_id, start_offset, end_offset, quote_hash)
    exact_selector = any(value is not None for value in selector_values)
    if exact_selector and not all(value is not None for value in selector_values):
        raise ProblemException(
            status=422,
            code="external_anchor_passage_selector_invalid",
            title="Passage selection refused",
            detail="Fragment, offsets and quote hash must be supplied together.",
        )
    if exact_selector:
        fragment = db.get(SourceFragment, fragment_id)
        text = fragment.normalized_text if fragment is not None else None
        if (
            fragment is None
            or fragment.source_version_id != version.source_version_id
            or text is None
            or start_offset is None
            or end_offset is None
            or start_offset >= end_offset
            or end_offset > len(text)
            or end_offset - start_offset > 300
        ):
            raise ProblemException(
                status=422,
                code="external_anchor_passage_selector_invalid",
                title="Passage selection refused",
                detail="The requested bounded passage is not part of the current source version.",
            )
        excerpt = text[start_offset:end_offset]
        if (
            not excerpt.strip()
            or excerpt != excerpt.strip()
            or hashlib.sha256(excerpt.encode("utf-8")).hexdigest() != quote_hash
        ):
            raise ProblemException(
                status=409,
                code="external_anchor_passage_changed",
                title="Passage selection refused",
                detail="The exact reviewed passage no longer matches the current source version.",
            )
        return [ExternalAnchorPassageView(
            result_id=result.result_id,
            source_id=document.source_id,
            source_version_id=version.source_version_id,
            fragment_id=fragment.fragment_id,
            start_offset=start_offset,
            end_offset=end_offset,
            public_domain=domain,
            page_title=result.title or document.name,
            excerpt=excerpt,
            quote_hash=quote_hash,
            safety_status=version.content_safety_status,
            content_review_status=version.content_review_status,
        )]

    rows = db.scalars(
        select(SourceFragment).where(
            SourceFragment.source_version_id == version.source_version_id
        ).order_by(SourceFragment.ordinal)
    )
    passages: list[ExternalAnchorPassageView] = []
    for fragment in rows:
        text = (fragment.normalized_text or "").strip()
        if not text:
            continue
        excerpt = text[:300]
        if len(text) > 300:
            boundary = excerpt.rfind(" ")
            excerpt = excerpt[:boundary if boundary >= 80 else 300].rstrip()
        start = (fragment.normalized_text or "").find(excerpt)
        if start < 0:
            continue
        passages.append(ExternalAnchorPassageView(
            result_id=result.result_id,
            source_id=document.source_id,
            source_version_id=version.source_version_id,
            fragment_id=fragment.fragment_id,
            start_offset=start,
            end_offset=start + len(excerpt),
            public_domain=domain,
            page_title=result.title or document.name,
            excerpt=excerpt,
            quote_hash=hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            safety_status=version.content_safety_status,
            content_review_status=version.content_review_status,
        ))
        if len(passages) == 10:
            break
    return passages


@router.post(
    "/research-results/{result_id}/external-anchors",
    response_model=ExternalAnchorView,
)
def create_external_anchor(
    result_id: str,
    payload: ExternalAnchorCreate,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> ExternalAnchorView:
    """Verify one user-selected passage from an imported, reviewed source.

    The resulting existing EvidenceAnchor is selectable by RUN 3C, but remains
    ``scope=external`` and can never satisfy application requirements.
    """
    result = service.get_result(db, result_id, context.user.workspace_id)
    if result is None or result.status != "imported" or not result.source_document_id:
        raise ProblemException(
            status=409, code="external_anchor_source_not_ready", title="Anchor refused",
            detail="Nur \u00fcbernommene und gepr\u00fcfte Quellen k\u00f6nnen verankert werden.",
        )
    task = service.get_task(db, result.research_task_id, context.user.workspace_id)
    if task is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Research task not found.",
        )
    project = _require_project(db, task.project_id, context.user.workspace_id)
    fragment = db.get(SourceFragment, payload.fragment_id)
    if fragment is None:
        raise ProblemException(
            status=404, code="fragment_not_found", title="Anchor refused",
            detail="Die ausgew\u00e4hlte Fundstelle wurde nicht gefunden.",
        )
    ref = market_verify.verify_quote(
        db, fragment=fragment, source_document_id=result.source_document_id,
        quote=payload.quote, project_id=project.project_id,
        workspace_id=project.workspace_id, research_task_id=task.research_task_id,
    )
    anchor_id = ref.get("linked_evidence_anchor_id") if ref else None
    if not anchor_id:
        raise ProblemException(
            status=422, code="external_anchor_exact_match_required", title="Anchor refused",
            detail="Die Passage ist keine exakte Fundstelle der aktuellen Quellenversion.",
        )
    db.commit()
    return ExternalAnchorView(
        anchor_id=anchor_id, project_id=project.project_id,
        workspace_id=project.workspace_id, research_task_id=task.research_task_id,
        source_id=result.source_document_id,
        source_version_id=ref["source_version_id"], fragment_id=ref["fragment_id"],
    )


@router.post(
    "/research-results/{result_id}/partner-eligibility-review",
    response_model=PartnerEligibilityReviewView,
)
def review_partner_eligibility(
    result_id: str,
    payload: PartnerEligibilityReviewInput,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> PartnerEligibilityReviewView:
    result = service.get_result(db, result_id, context.user.workspace_id)
    if result is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Research result not found.",
        )
    task = service.get_task(db, result.research_task_id, context.user.workspace_id)
    document = db.get(SourceDocumentModel, result.source_document_id) if result.source_document_id else None
    anchor = db.get(EvidenceAnchor, payload.anchor_id)
    current_version_id = document.current_source_version_id if document else None
    source_host = (urlparse(result.final_url or result.source_url).hostname or "").casefold()
    official_host = (urlparse(payload.official_url).hostname or "").casefold()
    valid = (
        task is not None
        and task.purpose == "partner_research_org_topic"
        and result.status == "imported"
        and result.content_review_status == "reviewed"
        and document is not None
        and anchor is not None
        and anchor.workspace_id == context.user.workspace_id
        and anchor.project_id == task.project_id
        and anchor.research_task_id == task.research_task_id
        and anchor.source_id == document.source_id
        and anchor.source_version_id == current_version_id
        and anchor.scope == "external"
        and anchor.verification_status in ("exact_verified", "human_verified")
        and bool(source_host and official_host and (
            source_host == official_host
            or source_host.endswith(f".{official_host}")
            or official_host.endswith(f".{source_host}")
        ))
    )
    if not valid:
        raise ProblemException(
            status=409, code="partner_eligibility_evidence_invalid", title="Review refused",
            detail="Die Best\u00e4tigung ben\u00f6tigt eine aktuelle offizielle Fundstelle derselben Quelle.",
        )
    now = datetime.now(timezone.utc)
    result.partner_candidate_status = "research_partner_candidate"
    result.eligibility_status = "verified_against_official_source"
    result.eligibility_anchor_id = anchor.anchor_id
    result.eligibility_source_version_id = anchor.source_version_id
    result.eligibility_official_url = payload.official_url
    result.eligibility_source_location = payload.source_location.strip()
    result.eligibility_last_checked = now
    result.eligibility_reviewed_by = context.user.id
    result.eligibility_reviewed_at = now
    db.commit()
    return PartnerEligibilityReviewView(
        result_id=result.result_id,
        eligibility_status="verified_against_official_source",
        anchor_id=anchor.anchor_id,
        source_version_id=anchor.source_version_id,
        last_checked=now,
    )


@router.get(
    "/projects/{project_id}/research-handoff",
    response_model=ResearchHandoffView,
)
def research_handoff(
    project_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> ResearchHandoffView:
    """Version-pinned, snippet-free RUN-3C input inventory."""
    project = _require_project(db, project_id, context.user.workspace_id)
    rows = list(db.execute(
        select(ResearchResult, ResearchTask, SourceDocumentModel, SourceVersion)
        .join(ResearchTask, ResearchTask.research_task_id == ResearchResult.research_task_id)
        .join(SourceDocumentModel, SourceDocumentModel.source_id == ResearchResult.source_document_id)
        .join(SourceVersion, SourceVersion.source_version_id == SourceDocumentModel.current_source_version_id)
        .where(
            ResearchTask.project_id == project.project_id,
            ResearchTask.workspace_id == project.workspace_id,
            ResearchResult.status == "imported",
            ResearchTask.execution_mode == "live",
        )
        .order_by(ResearchResult.created_at)
    ).all())
    source_views: list[ResearchHandoffSource] = []
    task_ids: set[str] = set()
    approval_ids: set[str] = set()
    version_ids: set[str] = set()
    brief_ids: set[str] = set()
    for result, task, document, version in rows:
        if not task.firewall_approval_id:
            continue
        task_ids.add(task.research_task_id)
        approval_ids.add(task.firewall_approval_id)
        version_ids.add(version.source_version_id)
        if task.research_brief_id:
            brief_ids.add(task.research_brief_id)
        source_views.append(ResearchHandoffSource(
            source_id=document.source_id,
            source_version_id=version.source_version_id,
            research_task_id=task.research_task_id,
            approval_id=task.firewall_approval_id,
            content_review_status=version.content_review_status,
            content_safety_status=version.content_safety_status,
            stale=False,
            stale_reason=None,
        ))
    anchor_ids = list(db.scalars(select(EvidenceAnchor.anchor_id).where(
        EvidenceAnchor.project_id == project.project_id,
        EvidenceAnchor.workspace_id == project.workspace_id,
        EvidenceAnchor.scope == "external",
        EvidenceAnchor.verification_status.in_(("exact_verified", "human_verified")),
        EvidenceAnchor.source_version_id.in_(version_ids) if version_ids else False,
    ).order_by(EvidenceAnchor.created_at, EvidenceAnchor.anchor_id)))
    comparison = db.scalar(select(MarketComparison).where(
        MarketComparison.project_id == project.project_id,
        MarketComparison.workspace_id == project.workspace_id,
    ).order_by(MarketComparison.created_at.desc()))
    return ResearchHandoffView(
        project_id=project.project_id,
        workspace_id=project.workspace_id,
        research_brief_id=next(iter(brief_ids)) if len(brief_ids) == 1 else None,
        research_run_ids=sorted(task_ids),
        research_task_ids=sorted(task_ids),
        approval_ids=sorted(approval_ids),
        current_source_version_ids=sorted(version_ids),
        external_evidence_anchor_ids=anchor_ids,
        current_market_comparison_id=comparison.comparison_id if comparison else None,
        market_comparison_status=comparison.status if comparison else None,
        market_comparison_stale_reason=comparison.stale_reason if comparison else None,
        sources=source_views,
    )
