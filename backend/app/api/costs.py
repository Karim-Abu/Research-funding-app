"""Authenticated project cost history backed by persisted provider usage."""
from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.contracts.costs import CostExecution, ProjectCostRun, ProjectCostView, UsageCost
from app.db.models import (
    AgentInvocation,
    AgentInvocationAttempt,
    AnalysisRun,
    ResearchTask,
    RunPolicySnapshot,
    ToolInvocation,
    UsageRecord,
    User,
)
from app.db.session import get_db
from app.evaluation.pricing import (
    COST_STATUS_NOT_APPLICABLE,
    COST_STATUS_PRICED,
    SNB_USD_CHF_REFERENCE_DATE,
    SNB_USD_CHF_REFERENCE_RATE,
    SNB_USD_CHF_SOURCE_URL,
)
from app.repositories import projects as projects_repo
from app.security.deps import AuthContext, require_session


router = APIRouter(tags=["Costs"])

# Public web-research tools served by Firecrawl. These are research-task scoped
# (never run scoped) and credit-based, so they are counted, not USD-priced.
_FIRECRAWL_TOOL_IDS = ("search_public_professional_sources", "fetch_validated_public_url")


def _cost(records: list[UsageRecord]) -> UsageCost:
    external = [record for record in records if record.cost_status != COST_STATUS_NOT_APPLICABLE]
    priced = [
        record for record in records
        if record.cost_status == COST_STATUS_PRICED and record.cost_usd is not None
    ]
    known_usd = round(sum(float(record.cost_usd or 0.0) for record in priced), 8)
    known_chf = round(sum(float(record.cost_chf or 0.0) for record in priced), 8)
    unpriced = len(external) - len(priced)
    if not external:
        status = "not_applicable"
    elif unpriced == 0:
        status = "priced"
    elif priced:
        status = "partial"
    else:
        status = "unknown_price"
    return UsageCost(
        status=status,
        usd=known_usd if status == "priced" else None,
        chf_reference=known_chf if status == "priced" else None,
        known_usd=known_usd,
        known_chf_reference=known_chf,
        unpriced_call_count=unpriced,
    )


@router.get("/projects/{project_id}/costs", response_model=ProjectCostView)
def get_project_costs(
    project_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> ProjectCostView:
    project = projects_repo.get_scoped(db, project_id, context.user.workspace_id)
    if project is None:
        raise ProblemException(
            status=404,
            code="not_found",
            title="Resource not found",
            detail="Project not found.",
        )
    research_task_ids = list(db.scalars(
        select(ResearchTask.research_task_id).where(
            ResearchTask.project_id == project_id,
            ResearchTask.workspace_id == context.user.workspace_id,
        )
    ))
    web_research_calls = int(db.scalar(
        select(func.count())
        .select_from(ToolInvocation)
        .where(
            ToolInvocation.research_task_id.in_(research_task_ids),
            ToolInvocation.tool_id.in_(_FIRECRAWL_TOOL_IDS),
        )
    ) or 0) if research_task_ids else 0
    runs = list(db.scalars(
        select(AnalysisRun)
        .where(AnalysisRun.project_id == project_id, AnalysisRun.workspace_id == context.user.workspace_id)
        .order_by(AnalysisRun.created_at.desc())
    ))
    run_ids = [run.run_id for run in runs]
    if not run_ids:
        return ProjectCostView(
            project_id=project_id,
            chf_reference_source=SNB_USD_CHF_SOURCE_URL,
            chf_reference_rate=SNB_USD_CHF_REFERENCE_RATE,
            chf_reference_as_of=SNB_USD_CHF_REFERENCE_DATE,
            web_research_calls=web_research_calls,
            runs=[],
        )
    usages = list(db.scalars(select(UsageRecord).where(UsageRecord.run_id.in_(run_ids))))
    usages_by_run: dict[str, list[UsageRecord]] = defaultdict(list)
    for usage in usages:
        if usage.run_id:
            usages_by_run[usage.run_id].append(usage)
    usage_ids = [usage.usage_record_id for usage in usages]
    attempts_by_usage = {
        attempt.usage_record_id: attempt
        for attempt in db.scalars(select(AgentInvocationAttempt).where(AgentInvocationAttempt.usage_record_id.in_(usage_ids)))
        if attempt.usage_record_id
    } if usage_ids else {}
    invocation_ids = {attempt.invocation_id for attempt in attempts_by_usage.values()}
    roles_by_invocation = {
        invocation.invocation_id: invocation.role_id
        for invocation in db.scalars(select(AgentInvocation).where(AgentInvocation.invocation_id.in_(invocation_ids)))
    } if invocation_ids else {}
    web_counts = {
        run_id: int(count)
        for run_id, count in db.execute(
            select(ToolInvocation.run_id, func.count())
            .where(ToolInvocation.run_id.in_(run_ids))
            .group_by(ToolInvocation.run_id)
        ).all()
        if run_id
    }
    users = {
        user.id: user.name
        for user in db.scalars(select(User).where(User.id.in_([run.created_by for run in runs])))
    }
    limits = {
        policy.run_id: policy.max_cost_chf
        for policy in db.scalars(select(RunPolicySnapshot).where(RunPolicySnapshot.run_id.in_(run_ids)))
    }
    output: list[ProjectCostRun] = []
    for run in runs:
        run_usages = usages_by_run.get(run.run_id, [])
        executions = []
        for usage in run_usages:
            attempt = attempts_by_usage.get(usage.usage_record_id)
            executions.append(CostExecution(
                id=usage.usage_record_id,
                role_label=(attempt.route_alias if attempt else "KI-Aufruf"),
                role_id=(roles_by_invocation.get(attempt.invocation_id) if attempt else None),
                provider=usage.provider,
                model=usage.model,
                status=(attempt.status if attempt else "recorded"),
                input_tokens=usage.input_tokens,
                cached_input_tokens=usage.cached_input_tokens,
                cache_write_input_tokens=usage.cache_write_input_tokens,
                output_tokens=usage.output_tokens,
                latency_ms=(attempt.latency_ms if attempt else None),
                cost=_cost([usage]),
                price_version=usage.price_version,
            ))
        output.append(ProjectCostRun(
            id=run.run_id,
            started_at=run.started_at or run.created_at,
            ended_at=run.ended_at,
            status=run.status,
            stop_reason=run.stop_reason,
            processing_mode=run.processing_mode,
            user=users.get(run.created_by, "Unbekannt"),
            max_cost_chf=limits.get(run.run_id),
            input_tokens=sum(usage.input_tokens for usage in run_usages),
            cached_input_tokens=sum(usage.cached_input_tokens for usage in run_usages),
            cache_write_input_tokens=sum(usage.cache_write_input_tokens for usage in run_usages),
            output_tokens=sum(usage.output_tokens for usage in run_usages),
            llm_calls=len(run_usages),
            web_calls=web_counts.get(run.run_id, 0),
            cost=_cost(run_usages),
            executions=executions,
        ))
    return ProjectCostView(
        project_id=project_id,
        chf_reference_source=SNB_USD_CHF_SOURCE_URL,
        chf_reference_rate=SNB_USD_CHF_REFERENCE_RATE,
        chf_reference_as_of=SNB_USD_CHF_REFERENCE_DATE,
        web_research_calls=web_research_calls,
        runs=output,
    )
