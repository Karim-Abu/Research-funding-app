"""Versioned public-safe research brief over the existing research vertical."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.contracts.research_brief import (
    ResearchBriefInput,
    ResearchBriefState,
    ResearchBriefView,
    ResearchQueryPlan,
    ResearchQueryView,
    ResearchPartnerCandidateView,
    ResearchResultView,
    ResearchRunResponse,
    ResearchSourceLocation,
    ResearchWorkspace,
)
from app.db.models import (
    Project,
    ResearchBrief,
    ResearchResult,
    ResearchTask,
    SearchQueryApproval,
    SourceDocument,
    SourceFragment,
)
from app.market_research.planner import MarketTopic, plan_market_queries
from app.partner_research.planner import QUERY_PURPOSES, PartnerTopic, plan_partner_queries
from app.partner_research.candidates import to_partner_candidates
from app.repositories import audit
from app.research import service
from app.research.executor import research_executor
from app.security import approval_service
from app.security.data_class import DataClass, derive_data_class, is_external_blocked
from app.security.search_query_firewall import evaluate_query

MODULE_PURPOSES = {
    "market_growth": {"market_size"},
    "competition_alternatives": {"competitors_alternatives"},
    "customer_problem": {"customer_pain"},
    "state_of_the_art": {"state_of_the_art"},
}
PARTNER_MODULE = "swiss_research_partners"
_GENERIC_QUERY_TERMS = {
    "market", "size", "growth", "wettbewerb", "competitors", "alternatives",
    "customer", "customers", "problem", "need", "needs", "pain", "challenges",
    "state", "art", "research", "group", "lab", "university", "institute",
    "competence", "center", "applied", "sciences", "swiss", "switzerland",
    "schweiz", "technology", "solution", "solutions", "trend", "trends",
}
_WORD = re.compile(r"[\wäöüéèàç-]+", re.IGNORECASE)


class BriefError(Exception):
    def __init__(self, code: str, detail: str, *, status: int = 422) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalized_payload(payload: ResearchBriefInput) -> dict:
    return {
        "application_domain": _clean(payload.application_domain),
        "technology_class": _clean(payload.technology_class),
        "target_customer_segments": [_clean(v) for v in payload.target_customer_segments if _clean(v)],
        "region": _clean(payload.region),
        "competence_needs": [_clean(v) for v in payload.competence_needs if _clean(v)],
        "modules": list(dict.fromkeys(payload.modules)),
    }


def _content_hash(data: dict) -> str:
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _risk_label(score: int) -> str:
    return "low" if score <= 2 else "medium" if score <= 6 else "high"


def _view(brief: ResearchBrief | None) -> ResearchBriefView | None:
    if brief is None:
        return None
    return ResearchBriefView(
        research_brief_id=brief.research_brief_id,
        version=brief.version,
        status=brief.status,
        application_domain=brief.application_domain,
        technology_class=brief.technology_class,
        target_customer_segments=list(brief.target_customer_segments or []),
        region=brief.region,
        competence_needs=list(brief.competence_needs or []),
        modules=list(brief.modules or []),
        approved_at=brief.approved_at,
    )


def latest(db: Session, project: Project) -> ResearchBrief | None:
    return db.scalar(
        select(ResearchBrief)
        .where(
            ResearchBrief.project_id == project.project_id,
            ResearchBrief.workspace_id == project.workspace_id,
        )
        .order_by(ResearchBrief.version.desc())
    )


def active_approved(db: Session, project: Project) -> ResearchBrief | None:
    return db.scalar(
        select(ResearchBrief)
        .where(
            ResearchBrief.project_id == project.project_id,
            ResearchBrief.workspace_id == project.workspace_id,
            ResearchBrief.status == "approved",
        )
        .order_by(ResearchBrief.version.desc())
    )


def _validate_public_safe(
    db: Session, project: Project, actor_user_id: str, data: dict
) -> None:
    data_class = derive_data_class(project.data_classification)
    if is_external_blocked(data_class):
        raise BriefError(
            "web_research_class_blocked",
            "Für diese Datenklasse darf kein öffentlicher Recherchebrief freigegeben werden.",
            status=403,
        )
    fields = [
        data["application_domain"], data["technology_class"], data["region"],
        *data["target_customer_segments"], *data["competence_needs"],
    ]
    for value in fields:
        if not value:
            continue
        result = evaluate_query(
            db,
            project_id=project.project_id,
            workspace_id=project.workspace_id,
            actor_user_id=actor_user_id,
            raw_query=value,
            data_class=data_class,
            intended_tool="firecrawl",
            purpose="research_brief_field",
            apply_project_lexicon=True,
        )
        if (
            result.decision == "block"
            or result.redaction_summary
            or _clean(result.sanitized_query).casefold() != _clean(value).casefold()
        ):
            raise BriefError(
                "research_brief_not_public_safe",
                "Der Recherchebrief enthält nicht öffentliche Angaben. Bitte allgemeiner formulieren.",
            )


def _validate_required(data: dict) -> None:
    if not data["application_domain"] or not data["technology_class"]:
        raise BriefError(
            "research_brief_incomplete",
            "Anwendungsdomäne und Technologieklasse sind erforderlich.",
        )
    if not data["modules"]:
        raise BriefError("research_brief_incomplete", "Mindestens ein Recherchemodul ist erforderlich.")
    market_modules = set(data["modules"]) - {PARTNER_MODULE, "state_of_the_art"}
    if market_modules and not data["target_customer_segments"]:
        raise BriefError(
            "research_brief_incomplete",
            "Für die Marktrecherche ist mindestens ein Zielkundensegment erforderlich.",
        )
    if PARTNER_MODULE in data["modules"] and not data["competence_needs"]:
        raise BriefError(
            "research_brief_incomplete",
            "Für die Partnerrecherche ist mindestens eine gesuchte Kompetenz erforderlich.",
        )


def suggest(db: Session, project: Project, actor_user_id: str) -> ResearchBrief:
    current = latest(db, project)
    if current is not None and current.status == "draft":
        return current
    field = _clean(project.innovation_field or "")
    parts = [p.strip() for p in re.split(r"\s*(?:/|,|\bund\b|\band\b)\s*", field, flags=re.I) if p.strip()]
    proposed = ResearchBriefInput(
        application_domain=parts[0] if parts else "",
        technology_class=parts[1] if len(parts) > 1 else (parts[0] if parts else ""),
        target_customer_segments=[],
        region="Schweiz",
        competence_needs=[],
        modules=["market_growth"],
    )
    data = _normalized_payload(proposed)
    # Unsafe project labels are not copied into the persisted brief.
    try:
        _validate_public_safe(db, project, actor_user_id, data)
    except BriefError:
        data["application_domain"] = ""
        data["technology_class"] = ""
    version = (current.version + 1) if current else 1
    brief = ResearchBrief(
        research_brief_id=str(uuid.uuid4()),
        project_id=project.project_id,
        workspace_id=project.workspace_id,
        version=version,
        status="draft",
        content_hash=_content_hash(data),
        created_by=actor_user_id,
        **data,
    )
    db.add(brief)
    audit.record(
        db, workspace_id=project.workspace_id, actor_user_id=actor_user_id,
        action="research_brief.suggested", target_type="research_brief",
        target_id=brief.research_brief_id,
        detail={"version": version, "module_count": len(data["modules"])},
    )
    return brief


def save(
    db: Session, project: Project, actor_user_id: str, payload: ResearchBriefInput
) -> ResearchBrief:
    data = _normalized_payload(payload)
    _validate_required(data)
    _validate_public_safe(db, project, actor_user_id, data)
    current = latest(db, project)
    wanted_hash = _content_hash(data)
    if current is not None and current.content_hash == wanted_hash:
        return current
    if current is not None and current.status == "draft":
        for key, value in data.items():
            setattr(current, key, value)
        current.content_hash = wanted_hash
        return current
    version = (current.version + 1) if current else 1
    brief = ResearchBrief(
        research_brief_id=str(uuid.uuid4()), project_id=project.project_id,
        workspace_id=project.workspace_id, version=version, status="draft",
        content_hash=wanted_hash, created_by=actor_user_id, **data,
    )
    db.add(brief)
    return brief


def approve(db: Session, brief: ResearchBrief, actor_user_id: str) -> ResearchBrief:
    if brief.status != "draft":
        raise BriefError("research_brief_not_draft", "Nur ein Entwurf kann freigegeben werden.", status=409)
    project = db.get(Project, brief.project_id)
    data = {
        "application_domain": brief.application_domain,
        "technology_class": brief.technology_class,
        "target_customer_segments": list(brief.target_customer_segments or []),
        "region": brief.region,
        "competence_needs": list(brief.competence_needs or []),
        "modules": list(brief.modules or []),
    }
    _validate_required(data)
    _validate_public_safe(db, project, actor_user_id, data)
    for old in db.scalars(
        select(ResearchBrief).where(
            ResearchBrief.project_id == brief.project_id,
            ResearchBrief.status == "approved",
            ResearchBrief.research_brief_id != brief.research_brief_id,
        )
    ):
        old.status = "superseded"
        for approval in db.scalars(
            select(SearchQueryApproval).where(
                SearchQueryApproval.research_brief_id == old.research_brief_id,
                SearchQueryApproval.status.in_(("pending", "approved")),
            )
        ):
            approval.status = "expired"
            approval.decided_at = _now()
    brief.status = "approved"
    brief.approved_by = actor_user_id
    brief.approved_at = _now()
    audit.record(
        db, workspace_id=brief.workspace_id, actor_user_id=actor_user_id,
        action="research_brief.approved", target_type="research_brief",
        target_id=brief.research_brief_id,
        detail={"version": brief.version, "content_hash": brief.content_hash,
                "module_count": len(brief.modules or [])},
    )
    return brief


def _market_topic(brief: ResearchBrief) -> MarketTopic:
    return MarketTopic(
        application_domain=brief.application_domain,
        technology_area=brief.technology_class,
        target_customers=", ".join(brief.target_customer_segments or []),
        region=brief.region,
    )


def _partner_topic(brief: ResearchBrief) -> PartnerTopic:
    return PartnerTopic(
        application_domain=brief.application_domain,
        technology_area=brief.technology_class,
        competence_areas=list(brief.competence_needs or []),
        region=brief.region,
    )


def _planned(brief: ResearchBrief) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    market = plan_market_queries(_market_topic(brief), include_state_of_the_art=True)
    for module, purposes in MODULE_PURPOSES.items():
        if module not in (brief.modules or []):
            continue
        rows.extend((module, q.purpose, q.query_text) for q in market if q.purpose in purposes)
    if PARTNER_MODULE in (brief.modules or []):
        rows.extend(
            (PARTNER_MODULE, q.purpose, q.query_text)
            for q in plan_partner_queries(_partner_topic(brief))
            if q.public_safe
        )
    return rows


def provider_mode() -> str:
    settings = get_settings()
    if not settings.web_research_enabled:
        return "unavailable"
    if settings.web_research_fake_provider:
        return "fake_demo"
    return "live" if settings.firecrawl_api_key else "unavailable"


def _query_view(approval: SearchQueryApproval, task: ResearchTask | None = None) -> ResearchQueryView:
    return ResearchQueryView(
        approval_id=approval.approval_id,
        research_brief_id=approval.research_brief_id or "",
        module=approval.research_module,
        planner_purpose=approval.planner_purpose or "",
        query_text=approval.sanitized_query,
        firewall_decision=approval.decision,
        risk_label=_risk_label(approval.risk_score),
        redaction_summary=list(approval.redaction_summary or []),
        status=approval.status,
        task_id=task.research_task_id if task else None,
        task_status=task.status if task else None,
        execution_mode=task.execution_mode if task else None,
    )


def plan_queries(
    db: Session, brief: ResearchBrief, actor_user_id: str
) -> ResearchQueryPlan:
    if brief.status != "approved":
        raise BriefError("research_brief_not_approved", "Der Recherchebrief muss zuerst freigegeben werden.")
    project = db.get(Project, brief.project_id)
    existing = list(db.scalars(select(SearchQueryApproval).where(
        SearchQueryApproval.research_brief_id == brief.research_brief_id,
        SearchQueryApproval.status.in_(("pending", "approved")),
    )))
    if existing:
        return ResearchQueryPlan(
            brief=_view(brief), queries=[_query_view(a) for a in existing],
            provider_mode=provider_mode(),
        )
    approvals: list[SearchQueryApproval] = []
    for module, planner_purpose, query in _planned(brief):
        outcome = approval_service.run_preview(
            db, project=project, actor_user_id=actor_user_id, raw_query=query,
            intended_tool="firecrawl", purpose=f"research:{module}:{planner_purpose}",
            force_approval=True, apply_project_lexicon=True,
        )
        if outcome.approval is None:
            continue
        outcome.approval.research_brief_id = brief.research_brief_id
        outcome.approval.research_module = module
        outcome.approval.planner_purpose = planner_purpose
        approvals.append(outcome.approval)
    return ResearchQueryPlan(
        brief=_view(brief), queries=[_query_view(a) for a in approvals],
        provider_mode=provider_mode(),
    )


def _brief_terms(brief: ResearchBrief) -> set[str]:
    text = " ".join([
        brief.application_domain, brief.technology_class, brief.region,
        *(brief.target_customer_segments or []), *(brief.competence_needs or []),
    ])
    return {m.group(0).casefold() for m in _WORD.finditer(text)}


def preview_query(
    db: Session, brief: ResearchBrief, actor_user_id: str, *, module: str,
    planner_purpose: str, query_text: str, supersedes_approval_id: str | None,
) -> SearchQueryApproval:
    if brief.status != "approved" or module not in (brief.modules or []):
        raise BriefError("research_brief_not_approved", "Keine gültige Brief-Freigabe für dieses Modul.")
    allowed_purposes = (
        set(QUERY_PURPOSES) if module == PARTNER_MODULE else MODULE_PURPOSES.get(module, set())
    )
    if planner_purpose not in allowed_purposes:
        raise BriefError(
            "planner_purpose_module_mismatch",
            "Der Query-Zweck passt nicht zum freigegebenen Recherchemodul.",
        )
    allowed = _brief_terms(brief) | _GENERIC_QUERY_TERMS
    query_terms = {m.group(0).casefold() for m in _WORD.finditer(query_text)}
    if query_terms - allowed:
        raise BriefError(
            "query_not_derived_from_brief",
            "Neue Fachbegriffe müssen zuerst im Recherchebrief geprüft werden.",
        )
    project = db.get(Project, brief.project_id)
    outcome = approval_service.run_preview(
        db, project=project, actor_user_id=actor_user_id, raw_query=query_text,
        intended_tool="firecrawl", purpose=f"research:{module}:{planner_purpose}",
        force_approval=True, apply_project_lexicon=True,
    )
    if outcome.approval is None:
        raise BriefError("query_blocked", "Die Suchanfrage wurde von der Firewall blockiert.")
    if supersedes_approval_id:
        old = db.get(SearchQueryApproval, supersedes_approval_id)
        if (
            old is None
            or old.workspace_id != brief.workspace_id
            or old.research_brief_id != brief.research_brief_id
            or old.research_module != module
        ):
            raise BriefError(
                "superseded_query_mismatch",
                "Die zu ersetzende Query gehört nicht zu diesem Brief und Modul.",
                status=409,
            )
        if old.status in ("pending", "approved"):
            old.status = "expired"
            old.decided_at = _now()
    approval = outcome.approval
    approval.research_brief_id = brief.research_brief_id
    approval.research_module = module
    approval.planner_purpose = planner_purpose
    return approval


def run(
    db: Session, brief: ResearchBrief, actor_user_id: str, approval_ids: list[str]
) -> ResearchRunResponse:
    if brief.status != "approved":
        raise BriefError("research_brief_not_approved", "Der Recherchebrief ist nicht freigegeben.")
    project = db.get(Project, brief.project_id)
    mode = provider_mode()
    data_class = derive_data_class(project.data_classification)
    settings = get_settings()
    if is_external_blocked(data_class):
        raise BriefError(
            "web_research_class_blocked",
            "Für diese Datenklasse ist Webrecherche gesperrt.",
            status=403,
        )
    if mode == "unavailable":
        raise BriefError("web_research_unavailable", "Öffentliche Recherche ist derzeit nicht verfügbar.", status=503)
    if data_class in (DataClass.D1_INTERNAL, DataClass.D2_CONFIDENTIAL_IDEA) and mode == "live" and not settings.d2_web_research_enabled:
        raise BriefError(
            "d2_live_web_research_disabled",
            "Live-Webrecherche für diese Datenklasse ist nicht aktiviert.",
        )
    if len(set(approval_ids)) != len(approval_ids):
        raise BriefError(
            "duplicate_approval_id", "Eine Query-Freigabe darf nur einmal ausgeführt werden."
        )
    approvals: list[SearchQueryApproval] = []
    for approval_id in approval_ids:
        approval = db.get(SearchQueryApproval, approval_id)
        if (
            approval is None or approval.research_brief_id != brief.research_brief_id
            or approval.project_id != project.project_id
            or approval.workspace_id != project.workspace_id
            or approval.research_module not in (brief.modules or [])
            or approval.status != "approved"
        ):
            raise BriefError("approval_not_approved", "Mindestens eine Query-Freigabe ist ungültig.")
        approvals.append(approval)

    # Validate the complete batch before creating a task or reaching a provider. This
    # avoids a partial external run when a later approval is invalid.
    task_ids: list[str] = []
    for approval in approvals:
        task_id, op_id = str(uuid.uuid4()), str(uuid.uuid4())
        kwargs = dict(
            db=db, project=project, query_preview=approval.sanitized_query,
            actor_user_id=actor_user_id, max_results=5, task_id=task_id,
            operation_id=op_id, approval=approval,
        )
        if approval.research_module == PARTNER_MODULE:
            service.create_partner_research_task(**kwargs)
        else:
            service.create_market_research_task(**kwargs)
        db.commit()
        research_executor(task_id, op_id)
        task_ids.append(task_id)
    db.expire_all()
    count = db.scalar(select(func.count(ResearchResult.result_id)).where(
        ResearchResult.research_task_id.in_(task_ids)
    )) or 0
    return ResearchRunResponse(task_ids=task_ids, result_count=count, execution_mode=mode)


def _locations(db: Session, result: ResearchResult) -> list[ResearchSourceLocation]:
    if not result.source_document_id:
        return []
    doc = db.get(SourceDocument, result.source_document_id)
    if doc is None or not doc.current_source_version_id:
        return []
    fragments = list(db.scalars(
        select(SourceFragment).where(
            SourceFragment.source_version_id == doc.current_source_version_id
        ).order_by(SourceFragment.ordinal).limit(3)
    ))
    return [ResearchSourceLocation(
        source_id=doc.source_id, source_version_id=doc.current_source_version_id,
        page=f.page, section=f.section, excerpt=(f.original_text or f.normalized_text)[:500],
    ) for f in fragments]


def _relevance(task: ResearchTask, brief: ResearchBrief | None) -> str:
    module = task.research_module
    if module == PARTNER_MODULE:
        return "Treffer zur freigegebenen Suche nach möglichen Schweizer Forschungskompetenzen; fachliche Passung und Förderberechtigung sind nicht bestätigt."
    labels = {
        "market_growth": "Markt und Wachstum",
        "competition_alternatives": "Wettbewerb und Alternativen",
        "customer_problem": "Kundenproblem und Bedarf",
        "state_of_the_art": "State of the Art",
    }
    return f"Treffer zum freigegebenen Recherchemodul „{labels.get(module, 'Öffentliche Recherche')}“; Snippet und Fundstelle sind fachlich zu prüfen."


def workspace(db: Session, project: Project) -> ResearchWorkspace:
    latest_brief = latest(db, project)
    approved = active_approved(db, project)
    briefs = list(db.scalars(
        select(ResearchBrief).where(
            ResearchBrief.project_id == project.project_id,
            ResearchBrief.workspace_id == project.workspace_id,
        )
    ))
    brief_by_id = {brief.research_brief_id: brief for brief in briefs}
    # Query approvals and completed tasks remain auditable after a new brief version.
    # Only planning/running uses the active approved version.
    brief_ids = list(brief_by_id)
    approvals = list(db.scalars(
        select(SearchQueryApproval).where(
            SearchQueryApproval.project_id == project.project_id,
            SearchQueryApproval.workspace_id == project.workspace_id,
            SearchQueryApproval.research_brief_id.in_(brief_ids) if brief_ids else False,
        ).order_by(SearchQueryApproval.created_at)
    )) if brief_ids else []
    tasks = list(db.scalars(select(ResearchTask).where(
        ResearchTask.project_id == project.project_id,
        ResearchTask.workspace_id == project.workspace_id,
        ResearchTask.research_brief_id.in_(brief_ids) if brief_ids else False,
    ))) if brief_ids else []
    by_approval = {t.firewall_approval_id: t for t in tasks if t.firewall_approval_id}
    query_views = [_query_view(a, by_approval.get(a.approval_id)) for a in approvals]
    by_task = {t.research_task_id: t for t in tasks}
    results = list(db.scalars(select(ResearchResult).where(
        ResearchResult.research_task_id.in_(by_task) if by_task else False
    ).order_by(ResearchResult.created_at))) if by_task else []
    partner_candidate_by_result: dict[str, object] = {}
    partner_results_by_brief: dict[str, list[ResearchResult]] = {}
    for result in results:
        task = by_task[result.research_task_id]
        if task.research_module == PARTNER_MODULE and task.research_brief_id:
            partner_results_by_brief.setdefault(task.research_brief_id, []).append(result)
    for brief_id, partner_results in partner_results_by_brief.items():
        source_brief = brief_by_id.get(brief_id)
        if source_brief is None:
            continue
        purpose_by_task_id = {
            result.research_task_id: by_task[result.research_task_id].planner_purpose or ""
            for result in partner_results
        }
        for candidate in to_partner_candidates(
            purpose_by_task_id, partner_results, topic=_partner_topic(source_brief)
        ):
            partner_candidate_by_result[candidate.result_id] = candidate
    result_views = []
    for result in results:
        task = by_task[result.research_task_id]
        url = result.final_url or result.source_url
        partner_candidate = partner_candidate_by_result.get(result.result_id)
        result_views.append(ResearchResultView(
            result_id=result.result_id, task_id=task.research_task_id,
            module=task.research_module, planner_purpose=task.planner_purpose,
            title=result.title, source_url=result.source_url, final_url=result.final_url,
            domain=urlparse(url).hostname or url, snippet=result.snippet,
            retrieved_at=result.retrieved_at, relevance_reason=_relevance(task, approved),
            status=result.status, execution_mode=task.execution_mode,
            source_document_id=result.source_document_id,
            source_locations=_locations(db, result),
            partner_candidate=(ResearchPartnerCandidateView(
                organization_or_group=partner_candidate.organization,
                location=partner_candidate.country_or_region,
                location_status=(
                    "verified" if partner_candidate.country_or_region else "unverified"
                ),
                expertise_keywords=partner_candidate.expertise_keywords,
                possible_project_role=partner_candidate.potential_project_role,
                why_potentially_relevant=_relevance(
                    task, brief_by_id.get(task.research_brief_id or "")
                ),
                evidence_url=partner_candidate.evidence_url,
            ) if partner_candidate else None),
        ))
    return ResearchWorkspace(
        brief=ResearchBriefState(latest=_view(latest_brief), active_approved=_view(approved)),
        queries=query_views, results=result_views, provider_mode=provider_mode(),
    )
