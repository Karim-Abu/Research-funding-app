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
from app.research import brief_service
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
    brief = brief_service.active_approved(db, project)
    if brief is None:
        raise ProblemException(
            status=422, code="research_brief_required", title="Research brief required",
            detail="Bitte prüfen und bestätigen Sie zuerst den öffentlichen Recherchebrief.",
        )
    try:
        planned = brief_service.plan_queries(db, brief, context.user.id)
    except brief_service.BriefError as exc:
        raise ProblemException(
            status=exc.status, code=exc.code, title="Research request refused", detail=exc.detail,
        ) from exc
    db.commit()
    topic = brief_service._market_topic(brief)
    market_queries = [q for q in planned.queries if q.module != "swiss_research_partners"]

    return MarketResearchPlanResponse(
        topic=MarketTopicDto(
            application_domain=topic.application_domain,
            technology_area=topic.technology_area,
            target_customers=topic.target_customers,
            region=topic.region,
        ),
        queries=[QueryCandidateDto(
            query_text=q.query_text, purpose=q.planner_purpose, public_safe=True,
            approval_required=True, approval_id=q.approval_id, status=q.status,
        ) for q in market_queries],
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
    brief = brief_service.active_approved(db, project)
    if brief is None:
        raise ProblemException(
            status=422, code="research_brief_required", title="Research brief required",
            detail="Bitte prüfen und bestätigen Sie zuerst den öffentlichen Recherchebrief.",
        )
    purpose = payload.purpose or "market_size"
    module = {
        "market_size": "market_growth",
        "regulatory_demand_drivers": "market_growth",
        "competitors_alternatives": "competition_alternatives",
        "customer_pain": "customer_problem",
        "state_of_the_art": "state_of_the_art",
    }.get(purpose)
    if module is None:
        raise ProblemException(
            status=422, code="query_not_derived_from_brief", title="Search query refused",
            detail="Diese Query gehört zu keinem freigegebenen Recherchemodul.",
        )
    try:
        # preview_query liefert eine ResearchQueryView (nicht die Approval-Row);
        # query_text ist darin bereits der bereinigte (sanitized) Text.
        view = brief_service.preview_query(
            db, brief, context.user.id, module=module, planner_purpose=purpose,
            query_text=payload.query_text,
        )
        db.commit()
        return QueryCandidateDto(
            query_text=view.query_text, purpose=purpose,
            public_safe=view.status != "blocked" and view.approval_id is not None,
            approval_required=True, approval_id=view.approval_id, status=view.status,
        )
    except brief_service.BriefError as exc:
        db.rollback()
        raise ProblemException(
            status=exc.status, code=exc.code, title="Search query refused", detail=exc.detail,
        ) from exc


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
    data_class = derive_data_class(project.data_classification)
    if is_external_blocked(data_class):
        raise ProblemException(
            status=403, code="web_research_class_blocked", title="Search query refused",
            detail="Öffentliche Recherche ist für diese Datenklasse gesperrt.",
        )
    brief = brief_service.active_approved(db, project)
    if brief is None:
        raise ProblemException(
            status=422, code="research_brief_required", title="Research brief required",
            detail="Bitte prüfen und bestätigen Sie zuerst den öffentlichen Recherchebrief.",
        )

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
    requested_ids = list(dict.fromkeys(payload.approval_ids))
    approvals = [
        a for approval_id in dict.fromkeys(payload.approval_ids)
        if (a := approval_service.get_scoped(db, approval_id, context.user.workspace_id))
        is not None
        and a.project_id == project_id
        and a.research_brief_id == brief.research_brief_id
        and a.research_module != "swiss_research_partners"
        and a.status == "approved"
    ]
    if not approvals or len(approvals) != len(requested_ids):
        raise ProblemException(
            status=422, code="approval_required", title="Search query refused",
            detail="Alle angeforderten Queries müssen zum aktiven Brief gehören und "
                   "freigegeben sein.",
        )

    try:
        run_outcome = brief_service.run(
            db, brief, context.user.id, [a.approval_id for a in approvals]
        )
    except (service.ResearchBlocked, brief_service.BriefError) as exc:
        db.commit()  # persist the firewall control/audit records
        raise ProblemException(
            status=exc.status, code=exc.code, title="Search query refused",
            detail=exc.detail,
        ) from exc

    current = brief_service.workspace(db, project)
    task_set = set(run_outcome.task_ids)
    selected = [r for r in current.results if r.task_id in task_set]
    response = MarketResearchRunResponse(
        task_ids=run_outcome.task_ids, result_count=run_outcome.result_count,
        tool_invocation_count=len(run_outcome.task_ids), credits_used=0,
        candidates=[MarketCandidateDto(
            result_id=r.result_id, purpose=r.planner_purpose or "market_signal",
            candidate_type={
                "market_size": "market_size_candidate",
                "competitors_alternatives": "competitor_or_alternative",
                "regulatory_demand_drivers": "market_driver_candidate",
                "customer_pain": "customer_segment",
                "state_of_the_art": "state_of_the_art_candidate",
            }.get(r.planner_purpose or "", "market_signal"),
            title=r.title, source_url=r.final_url or r.source_url, snippet=r.snippet,
            confidence="low", status=r.status, human_review_required=True,
        ) for r in selected],
        blocked_queries=0,
        provider="fake" if run_outcome.execution_mode == "fake_demo" else "live",
    )
    idempotency.save(
        db, scope=scope, key=idempotency_key, request_fingerprint=fingerprint,
        response_status=201, response_body=response.model_dump(mode="json"),
        resource_id=run_outcome.task_ids[0] if run_outcome.task_ids else None,
    )
    db.commit()
    return response
