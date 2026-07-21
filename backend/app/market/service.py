"""Market comparison service (Milestone 9I-B): create / read / list + contract mapping.

Generation runs in ``app.market.executor.comparison_executor``. Public/synthetic only;
the comparison is built only from imported public sources and never mutates drafts,
requirement assessments or approvals.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.contracts.market import (
    EvidenceQuote,
    MarketComparison as MarketComparisonContract,
    MarketComparisonItem as MarketComparisonItemContract,
    MarketComparisonView,
)
from app.contracts.run import AsyncAccepted
from app.db.models import (
    AsyncOperation,
    MarketComparison,
    MarketComparisonItem,
    Project,
)
from app.market import recording, source_scope
from app.research.policy import evaluate_web_research


class ComparisonBlocked(Exception):
    def __init__(self, code: str, detail: str, status: int = 422) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def comparison_allowed(classification: dict) -> bool:
    decision = evaluate_web_research(
        classification=classification or {},
        processing_mode=(classification or {}).get("processing_mode", ""),
        settings=get_settings(),
    )
    return not decision.blocked


def create_comparison(
    db: Session,
    *,
    project: Project,
    actor_user_id: str,
    comparison_id: str | None = None,
    operation_id: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[MarketComparison, AsyncOperation, AsyncAccepted]:
    if not comparison_allowed(project.data_classification or {}):
        raise ComparisonBlocked(
            "market_comparison_blocked",
            "Markt- und Konkurrenzvergleich ist für diese Datenklasse nicht erlaubt.",
        )
    actual_id = comparison_id or str(uuid.uuid4())
    actual_op = operation_id or str(uuid.uuid4())
    sources = source_scope.imported_public_sources(
        db, project.project_id, project.workspace_id
    )
    lineage = source_scope.provenance(db, sources)

    comparison = MarketComparison(
        comparison_id=actual_id,
        project_id=project.project_id,
        workspace_id=project.workspace_id,
        run_id=None,
        research_task_ids=lineage["research_task_ids"],
        research_brief_id=lineage["research_brief_id"],
        query_approval_ids=lineage["query_approval_ids"],
        source_version_ids=lineage["source_version_ids"],
        status="draft",
        research_gaps=[],
        warnings=[],
        comparison_version=1,
        source_scope_hash=source_scope.source_scope_hash(sources),
        generation_status=None,
        operation_id=actual_op,
        created_by=actor_user_id,
    )
    db.add(comparison)

    operation = AsyncOperation(
        operation_id=actual_op,
        workspace_id=project.workspace_id,
        project_id=project.project_id,
        resource_type="market_comparison",
        resource_id=actual_id,
        status="queued",
        idempotency_key=idempotency_key,
    )
    db.add(operation)
    recording.record_audit(
        db, workspace_id=project.workspace_id, actor_user_id=actor_user_id,
        action="market_comparison.requested", comparison_id=actual_id,
        detail={"source_count": len(sources)},
    )
    accepted = AsyncAccepted(
        operation_id=actual_op, resource_type="market_comparison",
        resource_id=actual_id, status="queued",
        poll_url=f"/api/v1/operations/{actual_op}",
    )
    return comparison, operation, accepted


def get_comparison(
    db: Session, comparison_id: str, workspace_id: str
) -> MarketComparison | None:
    return db.scalar(
        select(MarketComparison).where(
            MarketComparison.comparison_id == comparison_id,
            MarketComparison.workspace_id == workspace_id,
        )
    )


def latest_for_project(
    db: Session, project_id: str, workspace_id: str
) -> MarketComparison | None:
    return db.scalar(
        select(MarketComparison)
        .where(
            MarketComparison.project_id == project_id,
            MarketComparison.workspace_id == workspace_id,
        )
        .order_by(MarketComparison.created_at.desc())
    )


def list_items(db: Session, comparison_id: str) -> list[MarketComparisonItem]:
    return list(
        db.scalars(
            select(MarketComparisonItem)
            .where(MarketComparisonItem.comparison_id == comparison_id)
            .order_by(MarketComparisonItem.created_at, MarketComparisonItem.item_id)
        )
    )


def get_item(
    db: Session, item_id: str, workspace_id: str
) -> MarketComparisonItem | None:
    return db.scalar(
        select(MarketComparisonItem).where(
            MarketComparisonItem.item_id == item_id,
            MarketComparisonItem.workspace_id == workspace_id,
        )
    )


def update_item_status(
    db: Session, item: MarketComparisonItem, status: str,
    support_status: str | None = None,
) -> None:
    comparison = db.get(MarketComparison, item.comparison_id)
    if (
        status == "accepted" and comparison is not None
        and comparison.generation_kind == "fake_demo"
    ):
        raise ComparisonBlocked(
            "demo_comparison_not_acceptable",
            "Demo-Ergebnisse können nicht als Live-Recherche übernommen werden.",
            status=409,
        )
    item.status = status
    if support_status is not None:
        item.support_status = support_status
    recording.record_audit(
        db, workspace_id=item.workspace_id, actor_user_id=None,
        action="market_comparison_item.status", comparison_id=item.comparison_id,
        detail={"item_id": item.item_id, "status": status},
    )


# --- contract mapping -------------------------------------------------------


def _item_count(db: Session, comparison_id: str) -> int:
    return db.scalar(
        select(func.count(MarketComparisonItem.item_id)).where(
            MarketComparisonItem.comparison_id == comparison_id
        )
    ) or 0


def comparison_to_contract(
    db: Session, comparison: MarketComparison
) -> MarketComparisonContract:
    return MarketComparisonContract(
        comparison_id=comparison.comparison_id,
        project_id=comparison.project_id,
        workspace_id=comparison.workspace_id,
        status=comparison.status,
        comparison_version=comparison.comparison_version,
        generation_status=comparison.generation_status,
        generation_kind=comparison.generation_kind,
        research_brief_id=comparison.research_brief_id,
        research_task_ids=list(comparison.research_task_ids or []),
        query_approval_ids=list(comparison.query_approval_ids or []),
        source_version_ids=list(comparison.source_version_ids or []),
        provider=comparison.provider,
        model_ref=comparison.model_ref,
        prompt_version=comparison.prompt_version,
        context_hash=comparison.context_hash,
        stale_reason=comparison.stale_reason,
        consequences=list(comparison.consequences or []),
        research_gaps=list(comparison.research_gaps or []),
        warnings=list(comparison.warnings or []),
        item_count=_item_count(db, comparison.comparison_id),
        created_at=comparison.created_at,
        updated_at=comparison.updated_at,
        error=comparison.safe_error_detail,
    )


def item_to_contract(item: MarketComparisonItem) -> MarketComparisonItemContract:
    quotes = [
        EvidenceQuote(
            quote=r["quote"],
            source_document_id=r["source_document_id"],
            source_version_id=r["source_version_id"],
            linked_evidence_anchor_id=r.get("linked_evidence_anchor_id"),
            source_url=r.get("source_url"),
        )
        for r in (item.verified_quote_refs or [])
        if r.get("quote")
    ]
    return MarketComparisonItemContract(
        item_id=item.item_id,
        name=item.name,
        category=item.category,
        description=item.description,
        target_customer_segment=item.target_customer_segment,
        offering_summary=item.offering_summary,
        strengths=item.strengths,
        weaknesses=item.weaknesses,
        differentiation_relevance=item.differentiation_relevance,
        solution_type=(item.comparison_dimensions or {}).get("solution_type"),
        centralization=(item.comparison_dimensions or {}).get("centralization", "unclear"),
        data_access_model=(item.comparison_dimensions or {}).get("data_access_model"),
        swiss_relevance=(item.comparison_dimensions or {}).get("swiss_relevance"),
        core_problem_or_benefit=(item.comparison_dimensions or {}).get("core_problem_or_benefit"),
        relevant_functions=list((item.comparison_dimensions or {}).get("relevant_functions") or []),
        price_business_model=(item.comparison_dimensions or {}).get(
            "price_business_model", "nicht \u00f6ffentlich belegt"
        ),
        uncertainty=item.uncertainty,
        relation_to_project=item.relation_to_project,
        confidence_label=item.confidence_label,
        status=item.status,
        source_document_ids=list(item.source_document_ids or []),
        evidence_quotes=quotes,
        external_evidence_anchor_ids=list(item.evidence_anchor_ids or []),
        cell_evidence=dict(item.cell_evidence or {}),
        coverage_status=item.coverage_status,
        support_status=item.support_status,
    )


def view(db: Session, comparison: MarketComparison) -> MarketComparisonView:
    base = comparison_to_contract(db, comparison)
    items = [item_to_contract(i) for i in list_items(db, comparison.comparison_id)]
    return MarketComparisonView(**base.model_dump(), items=items)
