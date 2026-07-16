"""Market research runner (RESEARCH.1a; Freigabepflicht R8).

Plans public market queries, runs each through the EXISTING research vertical
(``create_market_research_task`` → Search Query Firewall → ``research_executor`` →
Fake/Firecrawl provider), and collects the results as MarketCandidates. The runner never
touches the web directly and never imports results as evidence — a result stays a
``candidate`` ResearchResult until a human/import step (out of scope here).

R8 — Freigabepflicht: der Normalpfad führt NUR menschlich freigegebene Queries aus
(``approvals``; exakt ``approval.sanitized_query``, single-use). Der freigabelose
Auto-Pfad existiert nur noch für den deterministischen Fake-/CI-Pfad —
ein realer Provider ohne Freigabe wird hart abgelehnt: ohne Freigabe kein
Firecrawl-Aufruf.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models import Project, ResearchResult, SearchQueryApproval, ToolInvocation
from app.market_research.candidates import MarketCandidate, to_market_candidates
from app.market_research.planner import (
    QUERY_PURPOSES,
    MarketTopic,
    QueryCandidate,
    plan_market_queries,
)
from app.research import service
from app.research.executor import research_executor
from app.research.service import ResearchBlocked

# Approval-Purpose-Präfix: „market_comparison:<planner_purpose>" — erhält den
# feingranularen Planner-Zweck auf der Freigabe, während ResearchTask.purpose der
# grobe interne ``market_comparison``-String bleibt (A2-Kontext-Filter unverändert).
MARKET_APPROVAL_PURPOSE_PREFIX = "market_comparison"


def market_approval_purpose(planner_purpose: str | None) -> str:
    if planner_purpose in QUERY_PURPOSES:
        return f"{MARKET_APPROVAL_PURPOSE_PREFIX}:{planner_purpose}"
    return MARKET_APPROVAL_PURPOSE_PREFIX


def planner_purpose_of(approval: SearchQueryApproval) -> str:
    purpose = approval.purpose or ""
    _, _, suffix = purpose.partition(":")
    return suffix if suffix in QUERY_PURPOSES else MARKET_APPROVAL_PURPOSE_PREFIX


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
    max_queries: int | None = None,
    approvals: list[SearchQueryApproval] | None = None,
) -> MarketResearchOutcome:
    """Execute market research for one project and return the candidate view.

    Normalpfad (R8): ``approvals`` — nur menschlich freigegebene Queries werden
    ausgeführt (exakt ``approval.sanitized_query``, single-use im Firewall-Chokepoint);
    eine nicht mehr gültige Freigabe wird fail-closed übersprungen und als
    ``blocked_queries`` gezählt. Ohne ``approvals`` plant der Runner selbst — dieser
    Auto-Pfad ist auf den deterministischen Fake-Provider (CI/Eval) begrenzt; ein realer Provider ohne
    Freigabe wird mit ``ResearchBlocked(approval_required)`` abgelehnt.

    Each executed query becomes an internal ``market_comparison`` ResearchTask that
    passes through the same firewall as the public flow. A confidential/NDA/unknown
    project makes ``create_market_research_task`` raise ``ResearchBlocked`` — the caller
    decides how to surface that (the runner does not silently downgrade the data class).
    ``max_queries`` begrenzt die Zahl der ausgeführten Suchanfragen (Run-Budget
    ``max_web_calls``); ``None`` = unverändert alle geplanten/freigegebenen Queries.
    """
    purpose_by_task_id: dict[str, str] = {}
    task_ids: list[str] = []
    blocked = 0

    if approvals is not None:
        queries = []
        for approval in approvals:
            planner_purpose = planner_purpose_of(approval)
            queries.append(
                QueryCandidate(
                    query_text=approval.sanitized_query,
                    purpose=planner_purpose,
                    source="approved_query",
                    data_mode=data_mode,
                    approval_required=True,
                    public_safe=True,
                    blocked_reason=None,
                )
            )
            if max_queries is not None and len(task_ids) >= max_queries:
                continue
            task_id = str(uuid.uuid4())
            operation_id = str(uuid.uuid4())
            try:
                service.create_market_research_task(
                    db, project=project, query_preview=approval.sanitized_query,
                    actor_user_id=actor_user_id, max_results=max_results,
                    task_id=task_id, operation_id=operation_id, approval=approval,
                )
            except ResearchBlocked as refused:
                # Klassen-Block betrifft den ganzen Lauf; eine einzelne ungültige
                # Freigabe (verbraucht/abgelehnt) nur diese Query (fail-closed).
                # Commit persistiert die metadaten-only Firewall-Audit-Records.
                if refused.code == "web_research_class_blocked":
                    raise
                db.commit()
                blocked += 1
                continue
            db.commit()  # the executor runs in its own session and reads committed rows
            research_executor(task_id, operation_id)
            purpose_by_task_id[task_id] = planner_purpose
            task_ids.append(task_id)
    else:
        settings = get_settings()
        if not settings.web_research_fake_provider:
            # Ohne Freigabe kein Firecrawl-Aufruf (R8) — der freigabelose Auto-Pfad
            # bleibt dem deterministischen Fake-Provider (CI/Eval) vorbehalten.
            raise ResearchBlocked(
                "approval_required",
                "Suchanfragen benötigen eine menschliche Freigabe, bevor ein realer "
                "Web-Provider aufgerufen werden darf.",
                status=422,
            )
        queries = plan_market_queries(topic, data_mode=data_mode)
        for candidate in queries:
            if not candidate.public_safe:
                blocked += 1
                continue
            if max_queries is not None and len(task_ids) >= max_queries:
                break
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
