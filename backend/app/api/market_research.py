"""Market Research API (RESEARCH.1b; Freigabepflicht R8).

Synchronous endpoints, no polling, no background task:

- ``POST /projects/{id}/market-research/plan`` — preview + Freigabe-Anbahnung: plant
  public-safe Query-Kandidaten und legt für ein D0-Projekt je Query eine ``pending``
  ``SearchQueryApproval`` an (R8: jede ausgehende Query wird gesehen und freigegeben;
  Entscheid über die bestehenden ``/search-query-approvals/{id}/approve|reject``).
- ``POST /projects/{id}/market-research/queries/preview`` — bearbeitete Query erneut
  durch die Firewall (inkl. Projekt-Lexikon auch für D0) + neue pending Freigabe; die
  alte Freigabe wird vom Client abgelehnt (und ist durch die Hash-Bindung ohnehin
  unbrauchbar).
- ``POST /projects/{id}/market-research/run`` — führt NUR freigegebene Queries über den
  EXISTING research vertical aus (Search Query Firewall → ResearchExecutor →
  Fake/Firecrawl); ohne Freigaben → 422 ``approval_required``. A confidential/NDA/unknown
  project surfaces the same firewall refusal as the public research flow.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.config.settings import Settings
from app.contracts.market_research import (
    MarketCandidateDto,
    MarketQueryPreviewInput,
    MarketResearchPlanResponse,
    MarketResearchRunRequest,
    MarketResearchRunResponse,
    MarketTopicDto,
    MarketTopicInput,
    ProviderMode,
    QueryCandidateDto,
)
from app.db.models import SearchQueryApproval
from app.db.session import get_db
from app.market_research.candidates import MarketCandidate
from app.market_research.planner import MarketTopic, QueryCandidate, plan_market_queries
from app.market_research.runner import market_approval_purpose, run_market_research
from app.market_research.topic import suggest_market_topic
from app.repositories import idempotency
from app.repositories import projects as projects_repo
from app.research import service
from app.security import approval_service
from app.security.data_class import DataClass, derive_data_class, is_external_blocked
from app.security.deps import AuthContext, require_unsafe_guards, settings_dep

router = APIRouter(tags=["Market Research"])


def _require_project(db: Session, project_id: str, workspace_id: str):
    project = projects_repo.get_scoped(db, project_id, workspace_id)
    if project is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Project not found.",
        )
    return project


def _provider_mode(settings: Settings) -> ProviderMode:
    if not settings.web_research_enabled:
        return "unavailable"
    if settings.web_research_fake_provider:
        return "fake"
    if settings.firecrawl_api_key:
        return "firecrawl_live"
    return "unavailable"


def _require_web_research_enabled(settings: Settings) -> None:
    if _provider_mode(settings) == "unavailable":
        raise ProblemException(
            status=503, code="web_research_unavailable", title="Service Unavailable",
            detail="Marktrecherche ist in dieser Umgebung nicht verfügbar.",
        )


def _query_dto(q: QueryCandidate, *, approval_id: str | None = None) -> QueryCandidateDto:
    return QueryCandidateDto(
        query_text=q.query_text, purpose=q.purpose, public_safe=q.public_safe,
        approval_required=q.approval_required, blocked_reason=q.blocked_reason,
        approval_id=approval_id,
    )


def _require_d0(project) -> None:
    """Markt-Vertikal ist D0-only (R8): D3/UNKNOWN → 403, D1/D2 → 422 wie bisher."""
    data_class = derive_data_class(project.data_classification)
    if is_external_blocked(data_class):
        raise ProblemException(
            status=403, code="web_research_class_blocked", title="Search query refused",
            detail="Öffentliche Recherche ist für diese Datenklasse gesperrt.",
        )
    if data_class != DataClass.D0_PUBLIC:
        raise ProblemException(
            status=422, code="approval_required", title="Search query refused",
            detail="Für vertrauliche Projekte ist eine geprüfte, bereinigte "
                   "Suchanfrage erforderlich.",
        )


def _candidate_dto(c: MarketCandidate) -> MarketCandidateDto:
    return MarketCandidateDto(
        result_id=c.result_id, purpose=c.purpose, candidate_type=c.candidate_type,
        title=c.title, source_url=c.source_url, snippet=c.snippet,
        confidence=c.confidence, status=c.status,
        human_review_required=c.human_review_required,
    )


def _resolve_topic(project, override: MarketTopicInput | None) -> MarketTopic:
    suggested = suggest_market_topic(project)
    if override is None:
        return suggested
    data = override.model_dump(exclude_none=True)
    return MarketTopic(
        application_domain=data.get("application_domain", suggested.application_domain),
        technology_area=data.get("technology_area", suggested.technology_area),
        target_customers=data.get("target_customers", suggested.target_customers),
        region=data.get("region", suggested.region),
    )


@router.post(
    "/projects/{project_id}/market-research/plan",
    response_model=MarketResearchPlanResponse,
)
def plan_market_research(
    project_id: str,
    payload: MarketTopicInput | None = None,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
) -> MarketResearchPlanResponse:
    project = _require_project(db, project_id, context.user.workspace_id)
    topic = _resolve_topic(project, payload)
    queries = plan_market_queries(topic, data_mode="live_project")

    # R8 Freigabepflicht: für ein D0-Projekt erhält jede public_safe Query eine
    # pending Freigabe (Entscheid via /search-query-approvals/{id}/approve|reject).
    # Nicht-D0-Projekte sehen weiterhin nur die Vorschau — ohne Freigabe kein Lauf.
    approval_ids: dict[int, str | None] = {}
    if derive_data_class(project.data_classification) == DataClass.D0_PUBLIC:
        for i, q in enumerate(queries):
            if not q.public_safe:
                continue
            outcome = approval_service.run_preview(
                db, project=project, actor_user_id=context.user.id,
                raw_query=q.query_text, intended_tool="firecrawl",
                purpose=market_approval_purpose(q.purpose), force_approval=True,
            )
            if outcome.approval is not None:
                approval_ids[i] = outcome.approval.approval_id
        db.commit()

    return MarketResearchPlanResponse(
        topic=MarketTopicDto(
            application_domain=topic.application_domain,
            technology_area=topic.technology_area,
            target_customers=topic.target_customers,
            region=topic.region,
        ),
        queries=[
            _query_dto(q, approval_id=approval_ids.get(i))
            for i, q in enumerate(queries)
        ],
        provider_mode=_provider_mode(settings),
    )


@router.post(
    "/projects/{project_id}/market-research/queries/preview",
    response_model=QueryCandidateDto,
)
def preview_market_query(
    project_id: str,
    payload: MarketQueryPreviewInput,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> QueryCandidateDto:
    """Bearbeitete Markt-Query erneut prüfen (R8): Firewall (inkl. Projekt-Lexikon
    auch für D0) + neue pending Freigabe. Die Antwort zeigt IMMER den bereinigten
    Text — nur dieser würde ausgeführt."""
    project = _require_project(db, project_id, context.user.workspace_id)
    _require_d0(project)
    outcome = approval_service.run_preview(
        db, project=project, actor_user_id=context.user.id,
        raw_query=payload.query_text, intended_tool="firecrawl",
        purpose=market_approval_purpose(payload.purpose), force_approval=True,
        apply_project_lexicon=True,
    )
    db.commit()
    result = outcome.result
    blocked = result.decision == "block"
    return QueryCandidateDto(
        query_text=result.sanitized_query,
        purpose=payload.purpose or "market_signal",
        public_safe=not blocked,
        approval_required=True,
        blocked_reason=(result.reasons[0] if blocked and result.reasons else None),
        approval_id=outcome.approval.approval_id if outcome.approval else None,
    )


@router.post(
    "/projects/{project_id}/market-research/run",
    response_model=MarketResearchRunResponse,
)
def run_market_research_endpoint(
    project_id: str,
    payload: MarketResearchRunRequest,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=8, max_length=128
    ),
) -> MarketResearchRunResponse:
    project = _require_project(db, project_id, context.user.workspace_id)
    _require_web_research_enabled(settings)
    _require_d0(project)

    fingerprint = idempotency.fingerprint(
        "POST", f"/projects/{project_id}/market-research/run", payload.model_dump_json()
    )
    scope = f"{context.user.workspace_id}:{context.user.id}:POST:/market-research/run"
    existing = idempotency.get(db, scope, idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ProblemException(
                status=409, code="idempotency_conflict", title="Conflict",
                detail="Idempotency-Key reused with a different request.",
            )
        return MarketResearchRunResponse(**existing.response_body)

    # R8 Freigabepflicht: nur freigegebene Queries werden ausgeführt (workspace-,
    # projekt- und zweck-gebunden; Single-Use im Firewall-Chokepoint).
    approvals = [
        a for approval_id in dict.fromkeys(payload.approval_ids)
        if (a := approval_service.get_scoped(db, approval_id, context.user.workspace_id))
        is not None
        and a.project_id == project_id
        and (a.purpose or "").startswith("market_comparison")
    ]
    if not approvals:
        raise ProblemException(
            status=422, code="approval_required", title="Search query refused",
            detail="Suchanfragen benötigen eine menschliche Freigabe, bevor die "
                   "Recherche starten kann.",
        )

    topic = MarketTopic(
        application_domain=payload.application_domain,
        technology_area=payload.technology_area,
        target_customers=payload.target_customers,
        region=payload.region,
    )
    try:
        outcome = run_market_research(
            db, project=project, actor_user_id=context.user.id, topic=topic,
            case_id=project_id, data_mode="live_project", max_results=3,
            approvals=approvals,
        )
    except service.ResearchBlocked as exc:
        db.commit()  # persist the firewall control/audit records
        raise ProblemException(
            status=exc.status, code=exc.code, title="Search query refused",
            detail=exc.detail,
        ) from exc

    response = MarketResearchRunResponse(
        task_ids=outcome.task_ids,
        result_count=outcome.result_count,
        tool_invocation_count=outcome.tool_invocation_count,
        credits_used=outcome.credits_used,
        candidates=[_candidate_dto(c) for c in outcome.candidates],
        blocked_queries=outcome.blocked_queries,
        provider=outcome.provider,
    )
    idempotency.save(
        db, scope=scope, key=idempotency_key, request_fingerprint=fingerprint,
        response_status=201, response_body=response.model_dump(mode="json"),
        resource_id=outcome.task_ids[0] if outcome.task_ids else None,
    )
    db.commit()
    return response
