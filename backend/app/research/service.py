"""ResearchTask service (Milestone 9I-A): create / read / list + contract mapping.

The async search itself runs in ``app.research.executor.research_executor``. ``query_text``
stores ONLY the user-confirmed public ``query_preview`` — never raw project text.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.research import (
    PartnerRoleSuggestion,
    ProfessionalEvidence,
    ResearchResult as ResearchResultContract,
    ResearchTask as ResearchTaskContract,
    ResearchTaskCreate,
)
from app.contracts.run import AsyncAccepted
from app.db.models import (
    AsyncOperation,
    Project,
    ResearchResult,
    ResearchTask,
    SearchQueryApproval,
)
from app.repositories import controls
from app.research import recording
from app.security import approval_service
from app.security.approval_service import CTRL_QUERY_FIREWALL, ApprovalError
from app.security.data_class import DataClass, derive_data_class, is_external_blocked
from app.security.search_query_firewall import evaluate_query, raw_query_hash


class ResearchBlocked(Exception):
    """The Search Query Firewall refused this web-research request (M9J). ``status``
    maps to an HTTP problem in the API layer."""

    def __init__(self, code: str, detail: str, *, status: int = 422) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query or "").strip()


def _query_hash(query: str) -> str:
    return hashlib.sha256(normalize_query(query).encode("utf-8")).hexdigest()


def _firewall_query(
    db: Session,
    *,
    project: Project,
    query_preview: str,
    purpose: str,
    approval_id: str | None,
    actor_user_id: str,
    task_id: str,
    approval: SearchQueryApproval | None = None,
) -> tuple[str, DataClass, str | None]:
    """Enforce the Search Query Firewall at the single web-research chokepoint.

    Returns ``(query_text, data_class, approval_id)``. The RAW query is hashed and
    discarded — for D1/D2 only the firewall-sanitized, human-approved query is returned;
    for D3/UNKNOWN and blocked queries it raises ``ResearchBlocked``. This runs in the
    SERVICE (not just the API) so an agent using the service cannot bypass it. Takes the
    query/purpose/approval as explicit args so both the public ``ResearchTaskCreate`` flow
    and the internal market-research flow share this single chokepoint (RESEARCH.1a).

    ``approval`` (R8, Markt-Query-Freigabe): a SERVER-loaded, human-approved
    ``SearchQueryApproval``. Only ``approval.sanitized_query`` is executed — there is no
    client query to re-hash. D0-only by design (the market vertical never runs for
    confidential classes); scope and single-use are enforced here in the chokepoint.
    """
    data_class = derive_data_class(project.data_classification)
    qhash = raw_query_hash(query_preview)

    def _blocked(code: str, detail: str, *, status: int, reason: str) -> ResearchBlocked:
        controls.record(
            db, workspace_id=project.workspace_id, project_id=project.project_id,
            control_id=CTRL_QUERY_FIREWALL, status="blocked",
            detail=f"{data_class}:{reason}", research_task_id=task_id,
        )
        recording.record_audit(
            db, workspace_id=project.workspace_id, actor_user_id=actor_user_id,
            action="research_task.firewall_blocked", research_task_id=task_id,
            detail={"data_class": str(data_class), "reason": reason, "raw_query_hash": qhash},
        )
        return ResearchBlocked(code, detail, status=status)

    # D3 (NDA) / UNKNOWN never reach an external tool.
    if is_external_blocked(data_class):
        raise _blocked(
            "web_research_class_blocked",
            "Öffentliche Recherche ist für diese Datenklasse gesperrt.",
            status=403, reason="class_blocked",
        )

    # Server-seitige Markt-Query-Freigabe (R8): exakt der freigegebene Text wird
    # ausgeführt; Scope + Single-Use fail-closed. D0-only — vertrauliche Klassen
    # erreichen den Markt-Vertikal weiterhin nie über diesen Pfad.
    if approval is not None:
        if (
            approval.project_id != project.project_id
            or approval.workspace_id != project.workspace_id
            or data_class != DataClass.D0_PUBLIC
        ):
            raise _blocked(
                "approval_required",
                "Für diese Suchanfrage liegt keine gültige Freigabe vor.",
                status=422, reason="approval_required",
            )
        try:
            query = approval_service.consume_approved(
                db, approval=approval, research_task_id=task_id
            )
        except ApprovalError as exc:
            raise ResearchBlocked(exc.code, exc.detail, status=exc.status) from exc
        return normalize_query(query), data_class, approval.approval_id

    def _consume() -> str:
        if not approval_id:
            raise _blocked(
                "approval_required",
                "Für vertrauliche Projekte ist eine geprüfte, bereinigte Suchanfrage "
                "erforderlich.",
                status=422, reason="approval_required",
            )
        try:
            return approval_service.consume_for_task(
                db, approval_id=approval_id, workspace_id=project.workspace_id,
                project_id=project.project_id, raw_query_hash=qhash,
                research_task_id=task_id,
            )
        except ApprovalError as exc:
            raise ResearchBlocked(exc.code, exc.detail, status=exc.status) from exc

    if data_class == DataClass.D0_PUBLIC:
        fw = evaluate_query(
            db, project_id=project.project_id, workspace_id=project.workspace_id,
            actor_user_id=actor_user_id, raw_query=query_preview,
            data_class=data_class, intended_tool="firecrawl", purpose=purpose,
        )
        if fw.decision == "allow":
            return normalize_query(query_preview), data_class, None
        if fw.decision == "block":
            raise _blocked(
                "web_research_query_blocked",
                "Die Suchanfrage enthält gesperrte Angaben. Bitte allgemeiner formulieren.",
                status=422, reason="query_blocked",
            )
        # require_human_approval: consume the approved sanitized query.
        return _consume(), data_class, approval_id

    # D1 / D2 — confidential: only an approved sanitized query may proceed.
    return _consume(), data_class, approval_id


def create_research_task(
    db: Session,
    *,
    project: Project,
    payload: ResearchTaskCreate,
    actor_user_id: str,
    task_id: str | None = None,
    operation_id: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[ResearchTask, AsyncOperation, AsyncAccepted]:
    actual_task_id = task_id or str(uuid.uuid4())
    actual_operation_id = operation_id or str(uuid.uuid4())

    # Search Query Firewall — the raw query is hashed and discarded; ``query`` is the
    # public-safe query that may be stored/sent (== normalized preview for a benign D0).
    query, data_class, approval_id = _firewall_query(
        db, project=project, query_preview=payload.query_preview,
        purpose=payload.purpose, approval_id=payload.approval_id,
        actor_user_id=actor_user_id, task_id=actual_task_id,
    )

    task = ResearchTask(
        research_task_id=actual_task_id,
        project_id=project.project_id,
        workspace_id=project.workspace_id,
        created_by=actor_user_id,
        operation_id=actual_operation_id,
        purpose=payload.purpose,
        subject_type=payload.subject_type,
        subject_name=payload.subject_name,
        query_text=query,
        normalized_query_hash=_query_hash(query),
        status="queued",
        preferred_domains=list(payload.preferred_domains),
        disallowed_domains=[],
        competence_needs=list(payload.competence_needs),
        requested_partner_roles=list(payload.requested_partner_roles),
        max_results=payload.max_results,
        max_pages=1,
        result_count=0,
        internal_public_confirmation_id=payload.internal_public_confirmation_id,
        firewall_data_class=str(data_class),
        firewall_approval_id=approval_id,
    )
    db.add(task)
    controls.record(
        db, workspace_id=project.workspace_id, project_id=project.project_id,
        control_id=CTRL_QUERY_FIREWALL, status="passed",
        detail=f"{data_class}:sanitized_ok", research_task_id=actual_task_id,
    )

    operation = AsyncOperation(
        operation_id=actual_operation_id,
        workspace_id=project.workspace_id,
        project_id=project.project_id,
        resource_type="research_task",
        resource_id=actual_task_id,
        status="queued",
        idempotency_key=idempotency_key,
    )
    db.add(operation)

    recording.record_audit(
        db, workspace_id=project.workspace_id, actor_user_id=actor_user_id,
        action="research_task.requested", research_task_id=actual_task_id,
        detail={"purpose": payload.purpose, "subject_type": payload.subject_type},
    )

    accepted = AsyncAccepted(
        operation_id=actual_operation_id,
        resource_type="research_task",
        resource_id=actual_task_id,
        status="queued",
        poll_url=f"/api/v1/operations/{actual_operation_id}",
    )
    return task, operation, accepted


# Internal-only research purpose for the market-research MVP (RESEARCH.1a). Stored on
# the free ORM ``ResearchTask.purpose`` String column ONLY — it is deliberately NOT added
# to the frozen public ``ResearchTaskCreate.purpose`` enum, so no frozen contract changes
# and the public create-API surface is untouched.
MARKET_RESEARCH_PURPOSE = "market_comparison"


def create_market_research_task(
    db: Session,
    *,
    project: Project,
    query_preview: str,
    actor_user_id: str,
    max_results: int,
    task_id: str | None = None,
    operation_id: str | None = None,
    idempotency_key: str | None = None,
    approval: SearchQueryApproval | None = None,
) -> tuple[ResearchTask, AsyncOperation]:
    """Create an internal market-research ResearchTask through the SAME Search Query
    Firewall chokepoint as the public flow (RESEARCH.1a). No public ``ResearchTaskCreate``
    contract is used; ``purpose`` is the internal ``market_comparison`` String. D0-only:
    a confidential/NDA/unknown class raises ``ResearchBlocked`` (approval_required /
    class_blocked) just like the public path. ``approval`` (R8): the human-approved
    query record — the chokepoint consumes it single-use and executes exactly its
    ``sanitized_query``.
    """
    actual_task_id = task_id or str(uuid.uuid4())
    actual_operation_id = operation_id or str(uuid.uuid4())

    query, data_class, approval_id = _firewall_query(
        db, project=project, query_preview=query_preview,
        purpose=MARKET_RESEARCH_PURPOSE, approval_id=None,
        actor_user_id=actor_user_id, task_id=actual_task_id,
        approval=approval,
    )

    task = ResearchTask(
        research_task_id=actual_task_id,
        project_id=project.project_id,
        workspace_id=project.workspace_id,
        created_by=actor_user_id,
        operation_id=actual_operation_id,
        purpose=MARKET_RESEARCH_PURPOSE,
        subject_type="topic",
        subject_name=None,
        query_text=query,
        normalized_query_hash=_query_hash(query),
        status="queued",
        preferred_domains=[],
        disallowed_domains=[],
        competence_needs=[],
        requested_partner_roles=[],
        max_results=max_results,
        max_pages=1,
        result_count=0,
        firewall_data_class=str(data_class),
        firewall_approval_id=approval_id,
    )
    db.add(task)
    controls.record(
        db, workspace_id=project.workspace_id, project_id=project.project_id,
        control_id=CTRL_QUERY_FIREWALL, status="passed",
        detail=f"{data_class}:sanitized_ok", research_task_id=actual_task_id,
    )

    operation = AsyncOperation(
        operation_id=actual_operation_id,
        workspace_id=project.workspace_id,
        project_id=project.project_id,
        resource_type="research_task",
        resource_id=actual_task_id,
        status="queued",
        idempotency_key=idempotency_key,
    )
    db.add(operation)

    recording.record_audit(
        db, workspace_id=project.workspace_id, actor_user_id=actor_user_id,
        action="research_task.requested", research_task_id=actual_task_id,
        detail={"purpose": MARKET_RESEARCH_PURPOSE, "subject_type": "topic"},
    )
    return task, operation


# Internal-only research purpose for the partner-research MVP (RESEARCH.2). Same
# rationale as MARKET_RESEARCH_PURPOSE: stored on the free ORM ``ResearchTask.purpose``
# String column only — deliberately distinct from the public ``partner_role_suggestion``
# enum value, so importing a result from this task never triggers the existing A1 Public
# Competence Research LLM synthesis (which runs unconditionally on import and is not
# gated by ``purpose``/``subject_type``). No frozen contract change.
PARTNER_RESEARCH_PURPOSE = "partner_research_org_topic"


def create_partner_research_task(
    db: Session,
    *,
    project: Project,
    query_preview: str,
    actor_user_id: str,
    max_results: int,
    task_id: str | None = None,
    operation_id: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[ResearchTask, AsyncOperation]:
    """Create an internal partner-research ResearchTask through the SAME Search Query
    Firewall chokepoint as the public flow (RESEARCH.2). Organisation/topic queries only —
    ``subject_type="topic"``, never a person. D0-only: a confidential/NDA/unknown class
    raises ``ResearchBlocked`` (approval_required / class_blocked) just like the public path.
    """
    actual_task_id = task_id or str(uuid.uuid4())
    actual_operation_id = operation_id or str(uuid.uuid4())

    query, data_class, approval_id = _firewall_query(
        db, project=project, query_preview=query_preview,
        purpose=PARTNER_RESEARCH_PURPOSE, approval_id=None,
        actor_user_id=actor_user_id, task_id=actual_task_id,
    )

    task = ResearchTask(
        research_task_id=actual_task_id,
        project_id=project.project_id,
        workspace_id=project.workspace_id,
        created_by=actor_user_id,
        operation_id=actual_operation_id,
        purpose=PARTNER_RESEARCH_PURPOSE,
        subject_type="topic",
        subject_name=None,
        query_text=query,
        normalized_query_hash=_query_hash(query),
        status="queued",
        preferred_domains=[],
        disallowed_domains=[],
        competence_needs=[],
        requested_partner_roles=[],
        max_results=max_results,
        max_pages=1,
        result_count=0,
        firewall_data_class=str(data_class),
        firewall_approval_id=approval_id,
    )
    db.add(task)
    controls.record(
        db, workspace_id=project.workspace_id, project_id=project.project_id,
        control_id=CTRL_QUERY_FIREWALL, status="passed",
        detail=f"{data_class}:sanitized_ok", research_task_id=actual_task_id,
    )

    operation = AsyncOperation(
        operation_id=actual_operation_id,
        workspace_id=project.workspace_id,
        project_id=project.project_id,
        resource_type="research_task",
        resource_id=actual_task_id,
        status="queued",
        idempotency_key=idempotency_key,
    )
    db.add(operation)

    recording.record_audit(
        db, workspace_id=project.workspace_id, actor_user_id=actor_user_id,
        action="research_task.requested", research_task_id=actual_task_id,
        detail={"purpose": PARTNER_RESEARCH_PURPOSE, "subject_type": "topic"},
    )
    return task, operation


def get_task(db: Session, task_id: str, workspace_id: str) -> ResearchTask | None:
    return db.scalar(
        select(ResearchTask).where(
            ResearchTask.research_task_id == task_id,
            ResearchTask.workspace_id == workspace_id,
        )
    )


def list_results(
    db: Session, project_id: str, workspace_id: str
) -> list[ResearchResult]:
    return list(
        db.scalars(
            select(ResearchResult)
            .join(ResearchTask, ResearchResult.research_task_id == ResearchTask.research_task_id)
            .where(
                ResearchTask.project_id == project_id,
                ResearchResult.workspace_id == workspace_id,
            )
            .order_by(ResearchResult.created_at, ResearchResult.provider_rank)
        )
    )


def get_result(db: Session, result_id: str, workspace_id: str) -> ResearchResult | None:
    return db.scalar(
        select(ResearchResult).where(
            ResearchResult.result_id == result_id,
            ResearchResult.workspace_id == workspace_id,
        )
    )


def discard_result(
    db: Session, *, result: ResearchResult, actor_user_id: str
) -> ResearchResult:
    """R8 (Anforderung 9): ein Research-Ergebnis explizit verwerfen — persistiert
    ``candidate`` → ``rejected``. Verworfene Ergebnisse werden nie A2-Kontext und
    tauchen nach einem Reload nicht wieder als Kandidat auf. Audit metadata-only."""
    if result.status != "candidate":
        raise ResearchBlocked(
            "result_not_discardable",
            "Nur offene Ergebnis-Kandidaten können verworfen werden.",
            status=409,
        )
    result.status = "rejected"
    recording.record_audit(
        db, workspace_id=result.workspace_id, actor_user_id=actor_user_id,
        action="research_result.discarded",
        research_task_id=result.research_task_id,
        detail={"result_id": result.result_id},
    )
    return result


# --- contract mapping -------------------------------------------------------


def task_to_contract(task: ResearchTask) -> ResearchTaskContract:
    return ResearchTaskContract(
        task_id=task.research_task_id,
        project_id=task.project_id,
        operation_id=task.operation_id,
        status=_public_status(task.status),
        purpose=task.purpose,
        created_at=task.created_at,
        completed_at=task.finished_at,
        result_count=task.result_count,
        error=task.safe_error_detail,
    )


def _public_status(status: str) -> str:
    # The internal 'blocked' state is surfaced as 'failed' in the public contract
    # (which has no 'blocked' enum); the safe detail carries the reason.
    return "failed" if status == "blocked" else status


def result_to_contract(result: ResearchResult) -> ResearchResultContract:
    return ResearchResultContract(
        result_id=result.result_id,
        task_id=result.research_task_id,
        source_url=result.source_url,
        title=result.title,
        snippet=result.snippet,
        accessed_at=result.retrieved_at,
        status="rejected" if result.status == "failed" else result.status,
        professional_evidence=[
            ProfessionalEvidence(**e) for e in (result.professional_evidence or [])
        ],
        partner_role_suggestions=[
            PartnerRoleSuggestion(**s) for s in (result.partner_role_suggestions or [])
        ],
        identity_match_status=result.identity_match_status,
    )
