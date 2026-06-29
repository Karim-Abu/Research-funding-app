"""Import a public web ResearchResult as a normal SourceDocument (Milestone 9I-A).

Re-runs the data-policy + SSRF gates, fetches the page via the provider, then creates a
SourceDocument(type=url) + a NEW SourceVersion and runs the EXISTING ingestion pipeline
(parse -> fragment -> normalize). Snippets/page text never become EvidenceAnchors here —
those only come from the deterministic evidence pipeline later (binding correction 10).
Import success does NOT depend on the advisory A1 synthesis (binding correction 6).
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models import Project, ResearchResult, ResearchTask, SourceDocument
from app.ingestion.pipeline import process_source_version
from app.repositories import sources as sources_repo
from app.research import cost_guard, recording
from app.research.policy import evaluate_web_research
from app.research.providers import (
    CreditExceeded,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    get_web_provider,
)
from app.research.url_safety import validate_public_url

logger = logging.getLogger("app.research.import")

_FETCH_TOOL = "fetch_validated_public_url"
_FETCH_MAX_CALLS_PER_TASK = 10


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
    classification = project.data_classification or {}

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

    check = validate_public_url(result.source_url, resolver=get_web_provider(settings)[1])
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

    provider, dns_resolver = get_web_provider(settings)
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
    except (ProviderUnavailable, ProviderTimeout, ProviderError, CreditExceeded) as exc:
        result.safe_error_detail = "Die Quelle konnte nicht abgerufen werden."
        raise ImportBlocked("fetch_failed", "Die Quelle konnte nicht abgerufen werden.",
                            status=502) from exc

    # Re-validate the final URL after any provider-side redirects.
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

    data = fetched.text.encode("utf-8")
    if len(data) > settings.web_fetch_max_bytes:
        data = data[: settings.web_fetch_max_bytes]
    from app.storage import get_storage

    ref = get_storage().put(data)
    classification_out = _public_source_classification(classification.get("processing_mode", ""))
    name = result.title[:200] or fetched.final_url
    doc = sources_repo.create_document(
        db, project_id=project.project_id, workspace_id=project.workspace_id,
        created_by=actor_user_id, name=name, source_type="url",
        classification=classification_out, status="uploaded",
    )
    version = sources_repo.create_version(
        db, document=doc, original_content_hash=fetched.content_hash,
        classification=classification_out, storage_ref=ref,
        original_filename=name, byte_size=len(data), mime_type="text/plain",
        status="uploaded",
    )
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
    result.source_document_id = doc.source_id
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
