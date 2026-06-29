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
)
from app.research import recording


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query or "").strip()


def _query_hash(query: str) -> str:
    return hashlib.sha256(normalize_query(query).encode("utf-8")).hexdigest()


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
    query = normalize_query(payload.query_preview)

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
    )
    db.add(task)

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
