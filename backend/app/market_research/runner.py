"""Market research runner (RESEARCH.1a).

Plans public market queries, runs each through the EXISTING research vertical
(``create_market_research_task`` → Search Query Firewall → ``research_executor`` →
Fake/Firecrawl provider), and collects the results as MarketCandidates. The runner never
touches the web directly and never imports results as evidence — a result stays a
``candidate`` ResearchResult until a human/import step (out of scope here).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Project, ResearchResult, ToolInvocation
from app.market_research.candidates import MarketCandidate, to_market_candidates
from app.market_research.planner import MarketTopic, QueryCandidate, plan_market_queries
from app.research import service
from app.research.executor import research_executor


@dataclass
class MarketResearchOutcome:
    case_id: str
    data_mode: str
    provider: str | None
    queries: list[QueryCandidate]
    task_ids: list[str] = field(default_factory=list)
    result_count: int = 0
    tool_invocation_count: int = 0
    credits_used: float = 0.0
    candidates: list[MarketCandidate] = field(default_factory=list)
    imported_source_count: int = 0
    blocked_queries: int = 0


def run_market_research(
    db: Session,
    *,
    project: Project,
    actor_user_id: str,
    topic: MarketTopic,
    case_id: str,
    data_mode: str = "synthetic_eval",
    max_results: int = 3,
) -> MarketResearchOutcome:
    """Plan + execute market research for one project and return the candidate view.

    Each planned query becomes an internal ``market_comparison`` ResearchTask that passes
    through the same firewall as the public flow. A confidential/NDA/unknown project makes
    ``create_market_research_task`` raise ``ResearchBlocked`` — the caller decides how to
    surface that (the runner does not silently downgrade the data class).
    """
    queries = plan_market_queries(topic, data_mode=data_mode)
    purpose_by_task_id: dict[str, str] = {}
    task_ids: list[str] = []
    blocked = 0

    for candidate in queries:
        if not candidate.public_safe:
            blocked += 1
            continue
        task_id = str(uuid.uuid4())
        operation_id = str(uuid.uuid4())
        service.create_market_research_task(
            db, project=project, query_preview=candidate.query_text,
            actor_user_id=actor_user_id, max_results=max_results,
            task_id=task_id, operation_id=operation_id,
        )
        db.commit()  # the executor runs in its own session and reads committed rows
        research_executor(task_id, operation_id)
        purpose_by_task_id[task_id] = candidate.purpose
        task_ids.append(task_id)

    db.expire_all()
    results = (
        list(
            db.scalars(
                select(ResearchResult)
                .where(ResearchResult.research_task_id.in_(task_ids))
                .order_by(ResearchResult.research_task_id, ResearchResult.provider_rank)
            )
        )
        if task_ids
        else []
    )
    tool_count = (
        db.scalar(
            select(func.count(ToolInvocation.invocation_id)).where(
                ToolInvocation.research_task_id.in_(task_ids)
            )
        )
        if task_ids
        else 0
    ) or 0

    provider = None
    credits = 0.0
    for tid in task_ids:
        task = service.get_task(db, tid, project.workspace_id)
        if task is not None:
            provider = task.provider or provider
            usage = task.provider_usage or {}
            credits += float(usage.get("credits_used", 0.0) or 0.0)

    candidates = to_market_candidates(purpose_by_task_id, results)
    return MarketResearchOutcome(
        case_id=case_id,
        data_mode=data_mode,
        provider=provider,
        queries=queries,
        task_ids=task_ids,
        result_count=len(results),
        tool_invocation_count=int(tool_count),
        credits_used=credits,
        candidates=candidates,
        imported_source_count=sum(1 for r in results if r.status == "imported"),
        blocked_queries=blocked,
    )
