"""ResearchExecutor (Milestone 9I-A): bounded background execution of a public web
search. Mirrors app.runs.executor — own DB session, atomic status, fail-closed.

Flow: data-policy gate -> research-task CostGuard -> provider search -> SSRF-validate
each candidate URL -> persist candidate ResearchResults. Snippets are candidates only;
they are NOT evidence and are NOT imported until the user imports a result.
"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.config.settings import get_settings
from app.db.models import AsyncOperation, Project, ResearchResult, ResearchTask
from app.db.session import SessionLocal
from app.research import cost_guard, recording
from app.research.policy import evaluate_web_research
from app.research.providers import (
    CreditExceeded,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    SearchRequest,
    get_web_provider,
)
from app.research.url_safety import validate_public_url
from app.security.data_class import DataClass, derive_data_class

logger = logging.getLogger("app.research.executor")
_semaphore = threading.BoundedSemaphore(get_settings().max_run_concurrency)

_SEARCH_TOOL = "search_public_professional_sources"
_SEARCH_MAX_CALLS_PER_TASK = 5

_POTENTIAL_SECTIONS = {
    "market_growth": ["Marktgrösse und Wachstum"],
    "competition_alternatives": ["Wettbewerb und Alternativlösungen"],
    "customer_problem": ["Kundenproblem (historisch)"],
    "state_of_the_art": ["State of the Art"],
    "swiss_research_partners": ["Forschungspartner und Kompetenzträger"],
}
_DEMO_DOMAINS = {"example.org", "example.com", "example.net"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_provider_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _is_demo_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").casefold().rstrip(".")
    return any(host == domain or host.endswith(f".{domain}") for domain in _DEMO_DOMAINS)


def _preliminary_quality(url: str, category: str | None) -> str:
    host = (urlparse(url).hostname or "").casefold()
    if category == "research" or host.endswith(".edu") or host.endswith(".ac.uk"):
        return "wissenschaftlich"
    if host.endswith(".admin.ch") or host.endswith(".gov") or host.endswith(".gov.ch"):
        return "offizielle_stelle"
    if host.endswith(".ch"):
        return "institutionell_ungeprüft"
    return "unbewertet"


def _problem(code: str, detail: str) -> dict:
    return {
        "type": f"/problems/{code}", "title": "Research Error", "status": 502,
        "detail": detail, "code": code, "correlation_id": str(uuid.uuid4()),
    }


def _finish_operation(db, operation_id: str, status: str, code: str | None = None,
                      detail: str | None = None) -> None:
    op = db.get(AsyncOperation, operation_id)
    if op is not None and op.status not in ("succeeded", "failed", "cancelled"):
        op.status = status
        op.finished_at = _now()
        if status == "failed":
            op.last_error_code = code
            op.error = _problem(code or "RESEARCH_FAILED", detail or "Research failed.")


def _fail_task(task: ResearchTask, *, code: str, detail: str) -> None:
    task.status = "failed"
    task.error_code = code
    task.safe_error_detail = detail
    task.finished_at = _now()


def _block_task(db, task: ResearchTask, operation_id: str, code: str, detail: str,
                reason: str) -> None:
    """Mark a task blocked, write a metadata-only audit event, finish the operation and
    commit. Used for data-policy / D2-live-gate blocks."""
    task.status = "blocked"
    task.error_code = code
    task.safe_error_detail = detail
    task.finished_at = _now()
    recording.record_audit(
        db, workspace_id=task.workspace_id, actor_user_id=None,
        action="research_task.blocked", research_task_id=task.research_task_id,
        detail={"reason": reason},
    )
    _finish_operation(db, operation_id, "failed", code, "Web research blocked.")
    db.commit()


def research_executor(task_id: str, operation_id: str) -> None:
    with _semaphore:
        db = SessionLocal()
        try:
            task = db.get(ResearchTask, task_id)
            op = db.get(AsyncOperation, operation_id)
            if task is None or op is None:
                return
            if task.status in ("succeeded", "failed", "blocked", "cancelled"):
                return
            project = db.get(Project, task.project_id)
            op.status = "running"
            op.started_at = _now()
            task.status = "running"
            task.started_at = _now()
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            db.close()
            _safe_mark_failed(task_id, operation_id, "RESEARCH_START_FAILED")
            return

        try:
            settings = get_settings()
            classification = project.data_classification if project else {}
            try:
                data_class = (
                    DataClass(task.firewall_data_class)
                    if task.firewall_data_class
                    else derive_data_class(classification)
                )
            except ValueError:
                data_class = derive_data_class(classification)

            if data_class == DataClass.D0_PUBLIC:
                # Public/synthetic: the existing web Data Policy applies unchanged.
                decision = evaluate_web_research(
                    classification=classification,
                    processing_mode=(classification or {}).get("processing_mode", ""),
                    settings=settings,
                    internal_public_confirmation_id=task.internal_public_confirmation_id,
                )
                recording.record_control(
                    db, workspace_id=task.workspace_id, project_id=task.project_id,
                    research_task_id=task.research_task_id, control_id="CTRL.DATA_POLICY",
                    status=decision.status, detail=decision.reason,
                )
                if decision.blocked:
                    _block_task(db, task, operation_id, "web_research_blocked",
                                "Öffentliche Recherche ist für diese Datenklasse nicht erlaubt.",
                                decision.reason)
                    return
            elif data_class in (DataClass.D1_INTERNAL, DataClass.D2_CONFIDENTIAL_IDEA):
                # Confidential: only a firewall-sanitized, human-approved query reaches
                # here (the service enforced it). The project's own sensitivity gate does
                # NOT apply to the public-safe sanitized query — record it as passed.
                recording.record_control(
                    db, workspace_id=task.workspace_id, project_id=task.project_id,
                    research_task_id=task.research_task_id, control_id="CTRL.DATA_POLICY",
                    status="passed", detail=f"{data_class}:sanitized_approved_query",
                )
                # D2/D1 live-provider gate (binding correction 1): a confidential class
                # may reach a LIVE web provider only when d2_web_research_enabled. Without
                # it the fake provider is fine (dev/test); a live provider is blocked.
                if not settings.d2_web_research_enabled and not settings.web_research_fake_provider:
                    _block_task(db, task, operation_id, "d2_live_web_research_disabled",
                                "Live-Websuche für vertrauliche Projekte ist nicht aktiviert.",
                                "d2_live_web_research_disabled")
                    return
            else:
                # D3 / UNKNOWN never reach the provider (defensive — service blocks first).
                _block_task(db, task, operation_id, "web_research_blocked",
                            "Öffentliche Recherche ist für diese Datenklasse gesperrt.",
                            f"{data_class}:class_blocked")
                return

            provider, dns_resolver = get_web_provider(settings)
            if not provider.available():
                _fail_task(task, code="provider_unavailable",
                           detail="Der Recherchedienst ist derzeit nicht verfügbar.")
                _finish_operation(db, operation_id, "failed", "provider_unavailable",
                                  "Web research provider unavailable.")
                db.commit()
                return

            guard = cost_guard.pre_check_tool(
                db, research_task_id=task.research_task_id, tool_id=_SEARCH_TOOL,
                max_calls=_SEARCH_MAX_CALLS_PER_TASK,
            )
            if not guard.allowed:
                recording.record_control(
                    db, workspace_id=task.workspace_id, project_id=task.project_id,
                    research_task_id=task.research_task_id, control_id="CTRL.COST_GUARD",
                    status="blocked", detail=guard.reason,
                )
                _fail_task(task, code="cost_guard_blocked",
                           detail="Das Budget für diese Recherche ist erreicht.")
                _finish_operation(db, operation_id, "failed", "cost_guard_blocked",
                                  "Research cost limit reached.")
                db.commit()
                return

            request = SearchRequest(
                query=task.query_text,
                max_results=min(task.max_results, settings.web_search_max_results),
                preferred_domains=tuple(task.preferred_domains or []),
                excluded_domains=tuple(task.disallowed_domains or []),
                categories=("research",) if task.research_module == "state_of_the_art" else (),
            )
            tool_invocation_id = recording.record_tool(
                db, workspace_id=task.workspace_id, research_task_id=task.research_task_id,
                tool_id=_SEARCH_TOOL, caller="orchestrator",
                input_hash=task.normalized_query_hash, output_hash=None, status="running",
            )
            try:
                outcome = provider.search(request)
            except (ProviderUnavailable, ProviderTimeout, ProviderError, CreditExceeded) as exc:
                _record_tool_failure(db, tool_invocation_id, type(exc).__name__)
                code = _safe_provider_code(exc)
                _fail_task(task, code=code, detail=_safe_provider_detail(exc))
                recording.record_control(
                    db, workspace_id=task.workspace_id, project_id=task.project_id,
                    research_task_id=task.research_task_id, control_id="CTRL.COST_GUARD",
                    status="failed", detail=code, tool_invocation_id=tool_invocation_id,
                )
                _finish_operation(db, operation_id, "failed", code, "Web search failed.")
                db.commit()
                return

            if outcome.provider != "fake" and any(
                _is_demo_url(candidate.url) for candidate in outcome.candidates
            ):
                _record_tool_failure(db, tool_invocation_id, "LiveDemoDomainRejected")
                _fail_task(
                    task, code="live_demo_domain_rejected",
                    detail="Der Live-Dienst lieferte eine reservierte Demo-Domain.",
                )
                recording.record_audit(
                    db, workspace_id=task.workspace_id, actor_user_id=None,
                    action="research_task.failed", research_task_id=task.research_task_id,
                    detail={"reason": "live_demo_domain_rejected"},
                )
                _finish_operation(
                    db, operation_id, "failed", "live_demo_domain_rejected",
                    "Live research returned a reserved demo domain.",
                )
                db.commit()
                return

            kept = 0
            for cand in outcome.candidates:
                check = validate_public_url(cand.url, resolver=dns_resolver)
                if not check.ok:
                    recording.record_control(
                        db, workspace_id=task.workspace_id, project_id=task.project_id,
                        research_task_id=task.research_task_id,
                        control_id="CTRL.SSRF_PREVENTION", status="blocked",
                        detail=check.reason, tool_invocation_id=tool_invocation_id,
                    )
                    continue
                db.add(ResearchResult(
                    result_id=str(uuid.uuid4()),
                    research_task_id=task.research_task_id,
                    workspace_id=task.workspace_id,
                    source_url=cand.url,
                    title=cand.title,
                    snippet=cand.snippet,
                    publisher=cand.publisher,
                    published_at=_parse_provider_date(cand.published_at),
                    source_category=cand.source_category,
                    source_quality=_preliminary_quality(cand.url, cand.source_category),
                    potential_sections=list(_POTENTIAL_SECTIONS.get(
                        task.research_module or "", []
                    )),
                    provider_rank=cand.rank,
                    retrieved_at=_now(),
                    status="candidate",
                    identity_match_status="not_applicable",
                    partner_candidate_status=(
                        "research_partner_candidate"
                        if task.purpose == "partner_research_org_topic" else None
                    ),
                    eligibility_status="not_checked",
                ))
                kept += 1

            task.result_count = kept
            task.provider = outcome.provider
            task.execution_mode = "fake_demo" if outcome.provider == "fake" else "live"
            task.provider_usage = {
                "result_count": kept, "credits_used": outcome.credits_used,
                "latency_ms": outcome.latency_ms,
            }
            task.status = "succeeded"
            task.finished_at = _now()
            recording.record_tool(
                db, workspace_id=task.workspace_id, research_task_id=task.research_task_id,
                tool_id=_SEARCH_TOOL, caller="orchestrator",
                input_hash=task.normalized_query_hash,
                output_hash=str(kept), status="succeeded", latency_ms=outcome.latency_ms,
            )
            for control_id in ("CTRL.PUBLIC_URL_VALIDATION", "CTRL.PROFESSIONAL_RESEARCH_PURPOSE",
                               "CTRL.NO_SENSITIVE_PERSONAL_ATTRIBUTES", "CTRL.AUDIT_WRITE"):
                recording.record_control(
                    db, workspace_id=task.workspace_id, project_id=task.project_id,
                    research_task_id=task.research_task_id, control_id=control_id,
                    status="passed", tool_invocation_id=tool_invocation_id,
                )
            recording.record_audit(
                db, workspace_id=task.workspace_id, actor_user_id=None,
                action="research_task.succeeded", research_task_id=task.research_task_id,
                detail={"result_count": kept},
            )
            _finish_operation(db, operation_id, "succeeded")
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            _safe_mark_failed(task_id, operation_id, "RESEARCH_EXECUTION_FAILED")
        finally:
            db.close()


def _record_tool_failure(db, tool_invocation_id: str, error_class: str) -> None:
    from app.db.models import ToolInvocation
    inv = db.get(ToolInvocation, tool_invocation_id)
    if inv is not None:
        inv.status = "failed"
        inv.error_class = error_class
        inv.finished_at = _now()


def _safe_provider_code(exc: Exception) -> str:
    return {
        ProviderUnavailable: "provider_unavailable",
        ProviderTimeout: "provider_timeout",
        ProviderError: "provider_error",
        CreditExceeded: "credit_exceeded",
    }.get(type(exc), "provider_error")


def _safe_provider_detail(exc: Exception) -> str:
    if isinstance(exc, CreditExceeded):
        return "Das Budget für die Recherche ist erreicht."
    if isinstance(exc, ProviderUnavailable):
        return "Der Recherchedienst ist derzeit nicht verfügbar."
    if isinstance(exc, ProviderTimeout):
        return "Die Recherche hat das Zeitlimit überschritten."
    return "Die Recherche konnte nicht abgeschlossen werden."


def _safe_mark_failed(task_id: str, operation_id: str, code: str) -> None:
    db = SessionLocal()
    try:
        task = db.get(ResearchTask, task_id)
        if task is not None and task.status not in ("succeeded", "failed", "blocked", "cancelled"):
            _fail_task(task, code=code, detail="Die Recherche konnte nicht abgeschlossen werden.")
        _finish_operation(db, operation_id, "failed", code, "Research failed.")
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    finally:
        db.close()
