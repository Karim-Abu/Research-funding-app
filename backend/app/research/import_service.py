"""Import a public web ResearchResult as a normal SourceDocument (Milestone 9I-A).

Re-runs the data-policy + SSRF gates, fetches the page via the provider, then creates a
SourceDocument(type=url) + a NEW SourceVersion and runs the EXISTING ingestion pipeline
(parse -> fragment -> normalize). Snippets/page text never become EvidenceAnchors here —
those only come from the deterministic evidence pipeline later (binding correction 10).
Import success does NOT depend on the advisory A1 synthesis (binding correction 6).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models import (
    Project, ResearchResult, ResearchTask, SourceDocument, SourceVersion,
)
from app.ingestion.pipeline import process_source_version
from app.repositories import sources as sources_repo
from app.research import content_safety, cost_guard, recording
from app.research.policy import evaluate_web_research
from app.research.providers import (
    CreditExceeded,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    get_web_provider,
)
from app.research.url_safety import (
    canonical_public_url, content_type_allowed, validate_public_url,
)
from app.security.data_class import DataClass, derive_data_class

logger = logging.getLogger("app.research.import")

_FETCH_TOOL = "fetch_validated_public_url"
_FETCH_MAX_CALLS_PER_TASK = 10


def _parse_provider_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


class ImportBlocked(Exception):
    """Import refused by policy/SSRF/provider — carries a safe code + detail."""

    def __init__(self, code: str, detail: str, status: int = 422) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


def _public_source_classification(processing_mode: str) -> dict:
    # Imported web sources are definitionally public; web research only runs on
    # public/synthetic projects, so this never downgrades a stricter project class.
    mode = processing_mode if processing_mode in ("deterministic_only", "cloud_assisted") else "deterministic_only"
    return {
        "sensitivity": "public",
        "origin": "public_source",
        "processing_mode": mode,
        "web_research_mode": "validated_public",
        "nda_applies": False,
    }


def import_result(
    db: Session,
    *,
    result: ResearchResult,
    task: ResearchTask,
    project: Project,
    actor_user_id: str,
) -> SourceDocument:
    settings = get_settings()
    # CI-/Demo-Suchergebnisse sind keine Webquellen und dürfen den produktiven
    # SourceDocument-/A2-/Marktvergleichspfad niemals betreten.
    if task.execution_mode == "fake_demo" or task.provider == "fake":
        raise ImportBlocked(
            "demo_result_not_importable",
            "Demo-Recherche enthält keine echten Webquellen und kann nicht übernommen werden.",
            status=422,
        )
    classification = project.data_classification or {}
    try:
        data_class = (
            DataClass(task.firewall_data_class)
            if task.firewall_data_class
            else derive_data_class(classification)
        )
    except ValueError:
        data_class = derive_data_class(classification)

    if data_class == DataClass.D0_PUBLIC:
        decision = evaluate_web_research(
            classification=classification,
            processing_mode=classification.get("processing_mode", ""),
            settings=settings,
            internal_public_confirmation_id=task.internal_public_confirmation_id,
        )
        recording.record_control(
            db, workspace_id=task.workspace_id, project_id=task.project_id,
            research_task_id=task.research_task_id, control_id="CTRL.DATA_POLICY",
            status=decision.status, detail=decision.reason,
        )
        if decision.blocked:
            raise ImportBlocked("web_research_blocked",
                                "Import ist für diese Datenklasse nicht erlaubt.", status=422)
    elif data_class in (DataClass.D1_INTERNAL, DataClass.D2_CONFIDENTIAL_IDEA):
        # The task passed the Search Query Firewall; fetching the (public) result URL is
        # a public pull-in, not a confidential push-out. The D2/D1 live-provider gate
        # still applies to the fetch.
        recording.record_control(
            db, workspace_id=task.workspace_id, project_id=task.project_id,
            research_task_id=task.research_task_id, control_id="CTRL.DATA_POLICY",
            status="passed", detail=f"{data_class}:sanitized_approved_query",
        )
        if not settings.d2_web_research_enabled and not settings.web_research_fake_provider:
            raise ImportBlocked("d2_live_web_research_disabled",
                                "Live-Websuche für vertrauliche Projekte ist nicht aktiviert.",
                                status=422)
    else:
        raise ImportBlocked("web_research_blocked",
                            "Import ist für diese Datenklasse gesperrt.", status=422)

    provider, dns_resolver = get_web_provider(settings)
    canonical_candidate = canonical_public_url(result.source_url)
    existing_url_result = db.scalar(
        select(ResearchResult)
        .join(ResearchTask, ResearchTask.research_task_id == ResearchResult.research_task_id)
        .where(
            ResearchTask.project_id == project.project_id,
            ResearchTask.workspace_id == project.workspace_id,
            ResearchResult.canonical_url == canonical_candidate,
            ResearchResult.source_document_id.is_not(None),
            ResearchResult.status == "imported",
        )
        .order_by(ResearchResult.created_at)
    )
    if existing_url_result is not None:
        existing_doc = db.get(SourceDocument, existing_url_result.source_document_id)
        if existing_doc is not None:
            result.status = "imported"
            result.canonical_url = canonical_candidate
            result.final_url = existing_url_result.final_url
            result.source_document_id = existing_doc.source_id
            recording.record_audit(
                db, workspace_id=task.workspace_id, actor_user_id=actor_user_id,
                action="research_result.import_replayed", research_task_id=task.research_task_id,
                detail={"result_id": result.result_id, "source_id": existing_doc.source_id,
                        "reason": "canonical_url_match"},
            )
            return existing_doc

    check = validate_public_url(result.source_url, resolver=dns_resolver)
    recording.record_control(
        db, workspace_id=task.workspace_id, project_id=task.project_id,
        research_task_id=task.research_task_id, control_id="CTRL.SSRF_PREVENTION",
        status="passed" if check.ok else "blocked", detail=check.reason,
    )
    if not check.ok:
        result.status = "rejected"
        result.safe_error_detail = "Die URL hat die Sicherheitsprüfung nicht bestanden."
        raise ImportBlocked("unsafe_url", "Die Quelle hat die URL-Prüfung nicht bestanden.",
                            status=422)

    guard = cost_guard.pre_check_tool(
        db, research_task_id=task.research_task_id, tool_id=_FETCH_TOOL,
        max_calls=_FETCH_MAX_CALLS_PER_TASK,
    )
    if not guard.allowed:
        raise ImportBlocked("cost_guard_blocked", "Das Budget für Importe ist erreicht.",
                            status=429)

    if not provider.available():
        raise ImportBlocked("provider_unavailable",
                            "Der Recherchedienst ist derzeit nicht verfügbar.", status=503)

    tool_invocation_id = recording.record_tool(
        db, workspace_id=task.workspace_id, research_task_id=task.research_task_id,
        tool_id=_FETCH_TOOL, caller="orchestrator",
        input_hash=recording.hash_text(result.source_url), output_hash=None, status="running",
    )
    try:
        fetched = provider.fetch(result.source_url, max_bytes=settings.web_fetch_max_bytes)
    except ProviderUnavailable as exc:
        result.safe_error_detail = "Der Recherchedienst ist nicht verf\u00fcgbar."
        raise ImportBlocked(
            exc.code, result.safe_error_detail, status=503
        ) from exc
    except ProviderTimeout as exc:
        result.safe_error_detail = "Der Abruf der Quelle hat zu lange gedauert."
        raise ImportBlocked(
            exc.code, result.safe_error_detail, status=504
        ) from exc
    except CreditExceeded as exc:
        result.safe_error_detail = "Das Provider-Budget f\u00fcr den Abruf ist erreicht."
        raise ImportBlocked(
            exc.code, result.safe_error_detail, status=429
        ) from exc
    except ProviderError as exc:
        result.safe_error_detail = "Die Quelle konnte nicht abgerufen werden."
        raise ImportBlocked(exc.code, "Die Quelle konnte nicht abgerufen werden.",
                            status=502) from exc

    # Re-validate every provider-reported redirect and the final URL. A changed
    # final URL without a complete provider chain is unverifiable and fails closed;
    # this service intentionally does not grow a second HTTP crawler.
    canonical_final = canonical_public_url(fetched.final_url)
    if canonical_final != canonical_candidate and not fetched.redirect_chain_verified:
        raise ImportBlocked(
            "redirect_chain_unverified",
            "Die Weiterleitungskette der Quelle konnte nicht gepr\u00fcft werden.",
            status=422,
        )
    if len(fetched.redirect_chain) > 10:
        raise ImportBlocked(
            "redirect_limit_exceeded",
            "Die Quelle hat zu viele Weiterleitungen.",
            status=422,
        )
    for target in fetched.redirect_chain:
        redirect_check = validate_public_url(target, resolver=dns_resolver)
        if not redirect_check.ok:
            raise ImportBlocked(
                "unsafe_redirect_url",
                "Eine Weiterleitungsadresse hat die Sicherheitspr\u00fcfung nicht bestanden.",
                status=422,
            )
    final_check = validate_public_url(fetched.final_url, resolver=dns_resolver)
    recording.record_control(
        db, workspace_id=task.workspace_id, project_id=task.project_id,
        research_task_id=task.research_task_id, control_id="CTRL.REDIRECT_REVALIDATION",
        status="passed" if final_check.ok else "blocked", detail=final_check.reason,
        tool_invocation_id=tool_invocation_id,
    )
    if not final_check.ok:
        raise ImportBlocked("unsafe_final_url",
                            "Die Zieladresse hat die Sicherheitsprüfung nicht bestanden.",
                            status=422)

    if not content_type_allowed(fetched.content_type):
        raise ImportBlocked(
            "unsupported_content_type",
            "Der Inhaltstyp der Quelle ist nicht f\u00fcr den Import zugelassen.",
            status=422,
        )
    data = fetched.text.encode("utf-8")
    if fetched.byte_size > settings.web_fetch_max_bytes or len(data) > settings.web_fetch_max_bytes:
        raise ImportBlocked(
            "source_too_large", "Die Quelle \u00fcberschreitet das Importlimit.", status=413
        )

    # Exact hashes are safe idempotent identity. Near hashes are advisory only.
    existing_hash_version = db.scalar(
        select(SourceVersion)
        .join(SourceDocument, SourceDocument.source_id == SourceVersion.source_document_id)
        .where(
            SourceDocument.project_id == project.project_id,
            SourceDocument.workspace_id == project.workspace_id,
            SourceDocument.type == "url",
            SourceVersion.original_content_hash == fetched.content_hash,
        )
        .order_by(SourceVersion.created_at)
    )
    if existing_hash_version is not None:
        existing_doc = db.get(SourceDocument, existing_hash_version.source_document_id)
        if existing_doc is not None:
            result.status = "imported"
            result.final_url = fetched.final_url
            result.canonical_url = canonical_final
            result.fetched_content_type = fetched.content_type
            result.fetched_content_hash = fetched.content_hash
            result.source_document_id = existing_doc.source_id
            recording.record_audit(
                db, workspace_id=task.workspace_id, actor_user_id=actor_user_id,
                action="research_result.import_replayed", research_task_id=task.research_task_id,
                detail={"result_id": result.result_id, "source_id": existing_doc.source_id,
                        "reason": "content_hash_match"},
            )
            return existing_doc

    safety_status, quarantine_reason = content_safety.scan_untrusted_text(fetched.text)
    simhash = content_safety.similarity_hash(fetched.text)
    possible_duplicate_version = None
    for candidate_version in db.scalars(
        select(SourceVersion)
        .join(SourceDocument, SourceDocument.source_id == SourceVersion.source_document_id)
        .where(
            SourceDocument.project_id == project.project_id,
            SourceDocument.workspace_id == project.workspace_id,
            SourceDocument.type == "url",
            SourceVersion.similarity_hash.is_not(None),
        )
    ):
        if content_safety.possible_duplicate(simhash, candidate_version.similarity_hash):
            possible_duplicate_version = candidate_version
            break
    from app.storage import get_storage

    ref = get_storage().put(data)
    classification_out = _public_source_classification(classification.get("processing_mode", ""))
    name = result.title[:200] or fetched.final_url
    doc = sources_repo.create_document(
        db, project_id=project.project_id, workspace_id=project.workspace_id,
        created_by=actor_user_id, name=name, source_type="url",
        classification=classification_out, status="uploaded",
    )
    doc.source_url = fetched.final_url
    version = sources_repo.create_version(
        db, document=doc, original_content_hash=fetched.content_hash,
        classification=classification_out, storage_ref=ref,
        original_filename=name, byte_size=len(data), mime_type="text/plain",
        status="uploaded",
    )
    version.retrieval_provenance = {
        "canonical_url": canonical_final,
        "original_url": result.source_url,
        "title": fetched.title or result.title,
        "publisher": fetched.publisher or result.publisher,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "provider": fetched.provider,
        "execution_mode": task.execution_mode,
        "research_task_id": task.research_task_id,
        "query_approval_id": task.firewall_approval_id,
        "content_type": fetched.content_type,
        "content_hash": fetched.content_hash,
    }
    version.content_review_status = "unreviewed"
    version.content_safety_status = safety_status
    version.quarantine_reason_code = quarantine_reason
    version.similarity_hash = simhash
    if possible_duplicate_version is not None:
        version.possible_duplicate_source_id = possible_duplicate_version.source_document_id
    recording.record_tool(
        db, workspace_id=task.workspace_id, research_task_id=task.research_task_id,
        tool_id=_FETCH_TOOL, caller="orchestrator",
        input_hash=recording.hash_text(result.source_url),
        output_hash=fetched.content_hash, status="succeeded", latency_ms=fetched.latency_ms,
    )
    for control_id in ("CTRL.PUBLIC_URL_VALIDATION", "CTRL.SOURCE_TRUST", "CTRL.AUDIT_WRITE"):
        recording.record_control(
            db, workspace_id=task.workspace_id, project_id=task.project_id,
            research_task_id=task.research_task_id, control_id=control_id, status="passed",
            tool_invocation_id=tool_invocation_id,
        )

    result.status = "imported"
    result.final_url = fetched.final_url
    result.canonical_url = canonical_final
    result.fetched_content_type = fetched.content_type
    result.fetched_content_hash = fetched.content_hash
    result.content_safety_status = safety_status
    result.quarantine_reason_code = quarantine_reason
    result.possible_duplicate_source_id = version.possible_duplicate_source_id
    if task.purpose == "partner_research_org_topic":
        result.partner_candidate_status = "research_partner_candidate"
        result.eligibility_status = "not_checked"
    result.title = fetched.title or result.title
    result.publisher = fetched.publisher or result.publisher
    result.published_at = _parse_provider_date(fetched.published_at) or result.published_at
    result.source_document_id = doc.source_id
    task.provider_usage = {
        **(task.provider_usage or {}),
        "last_fetch_credits_used": fetched.credits_used,
        "last_fetch_latency_ms": fetched.latency_ms,
    }
    recording.record_audit(
        db, workspace_id=task.workspace_id, actor_user_id=actor_user_id,
        action="research_result.imported", research_task_id=task.research_task_id,
        detail={"result_id": result.result_id, "source_id": doc.source_id},
    )
    db.commit()

    # Run the EXISTING ingestion pipeline synchronously (textual content, no heavy I/O).
    process_source_version(version.source_version_id)
    db.expire_all()

    # Advisory A1 synthesis — NON-BLOCKING (binding correction 6). Any failure leaves the
    # imported source intact and records a safe failure; it never fails the import.
    try:
        from app.agents import public_competence_research

        public_competence_research.synthesize_after_import(
            db, task=db.get(ResearchTask, task.research_task_id), project=project
        )
    except Exception:  # noqa: BLE001 — A1 is advisory and must never break import
        logger.warning("A1 public-competence synthesis failed; import preserved")
        fresh = db.get(ResearchTask, task.research_task_id)
        if fresh is not None and fresh.a1_synthesis_status is None:
            fresh.a1_synthesis_status = "failed"
            db.commit()

    return db.get(SourceDocument, doc.source_id)
