"""MarketComparison executor (Milestone 9I-B): bounded background generation.

Pre-filter imported public fragments -> structure them via the beta-internal model
(fake in tests) -> deterministically verify each item's exact quote against the imported
SourceVersion -> persist source_backed / needs_review / insufficient_evidence items.
Never raises; never mutates drafts/assessments/approvals; never invents content.
"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone

from app.agents import gateway
from app.agents.prompt_assets import prompt_version_for
from app.agents.schemas import SchemaNotImplementedError, ValidationError, validate_payload
from app.config.settings import get_settings
from app.db.models import (
    AsyncOperation,
    MarketComparison,
    MarketComparisonItem,
    Project,
    SourceFragment,
)
from app.db.session import SessionLocal
from app.evidence.tokenize import normalize_for_match
from app.market import cost_guard, recording, source_scope, verify
from app.market.agent_profile import PROFILE_ID, ensure_registered

logger = logging.getLogger("app.market.executor")
_semaphore = threading.BoundedSemaphore(get_settings().max_run_concurrency)

# Public classification for the model call: only public source fragments are sent.
_MODEL_CLASSIFICATION = {
    "sensitivity": "public", "origin": "public_source",
    "processing_mode": "cloud_assisted", "web_research_mode": "validated_public",
    "nda_applies": False,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _problem(code: str, detail: str) -> dict:
    return {"type": f"/problems/{code}", "title": "Market Comparison Error",
            "status": 502, "detail": detail, "code": code,
            "correlation_id": str(uuid.uuid4())}


def _finish_operation(db, operation_id, status, code=None, detail=None) -> None:
    op = db.get(AsyncOperation, operation_id)
    if op is not None and op.status not in ("succeeded", "failed", "cancelled"):
        op.status = status
        op.finished_at = _now()
        if status == "failed":
            op.last_error_code = code
            op.error = _problem(code or "MARKET_FAILED", detail or "Comparison failed.")


def _fake_bundle(candidates) -> str:
    """Deterministic dev/test fake: one source-backed item quoting the first candidate."""
    import json

    if not candidates:
        return json.dumps({"items": [], "research_gaps":
                           ["Keine marktbezogenen Passagen in den importierten Quellen."],
                           "warnings": []})
    c = candidates[0]
    text = c.text
    cut = min(160, len(text))
    space = text.rfind(" ", 0, cut)
    quote = text[: space if space > 40 else cut].strip()
    bundle = {
        "items": [{
            "name": "Öffentlich genannte Lösung",
            "category": "alternative_solution",
            "description": "In einer öffentlichen Quelle erwähnte Lösung (zu prüfen).",
            "target_customer_segment": None,
            "offering_summary": None,
            "strengths": None,
            "weaknesses": None,
            "differentiation_relevance": "Hinweis aus öffentlicher Quelle — fachlich zu prüfen.",
            "relation_to_project": "unclear",
            "source_fragment_id": c.fragment_id,
            "source_document_id": c.source_document_id,
            "quote": quote,
        }],
        "research_gaps": ["Marktgröße und Wettbewerbsumfeld sind nicht vollständig belegt."],
        "warnings": ["Vorschläge sind Hinweise aus öffentlichen Quellen, keine bestätigten Fakten."],
    }
    return json.dumps(bundle)


def _resolver(candidates):
    settings = get_settings()
    if settings.web_research_fake_provider:
        from app.agents.providers.fake import FakeProvider
        raw = _fake_bundle(candidates)
        return lambda _route: FakeProvider(raw_output=raw)
    return gateway.default_provider_resolver


def comparison_executor(comparison_id: str, operation_id: str) -> None:
    with _semaphore:
        db = SessionLocal()
        try:
            comparison = db.get(MarketComparison, comparison_id)
            op = db.get(AsyncOperation, operation_id)
            if comparison is None or op is None:
                return
            if comparison.status in ("ready_for_review", "failed"):
                return
            project = db.get(Project, comparison.project_id)
            op.status = "running"
            op.started_at = _now()
            comparison.status = "draft"
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            db.close()
            _safe_fail(comparison_id, operation_id, "MARKET_START_FAILED")
            return

        try:
            guard = cost_guard.pre_check_generation(comparison)
            if not guard.allowed:
                _finish_operation(db, operation_id, "succeeded")
                db.commit()
                return

            sources = source_scope.imported_public_sources(
                db, comparison.project_id, comparison.workspace_id
            )
            candidates = source_scope.prefilter_fragments(db, sources)
            if not candidates:
                _complete_empty(db, comparison, operation_id,
                                "Keine importierten öffentlichen Quellen mit marktbezogenen "
                                "Passagen vorhanden.")
                db.commit()
                return

            payload = {
                "project_id": comparison.project_id,
                "comparison_id": comparison.comparison_id,
                "project_title": project.title if project else "",
                "candidate_fragments": [
                    {"fragment_id": c.fragment_id, "source_version_id": c.source_version_id,
                     "source_document_id": c.source_document_id, "text": c.text}
                    for c in candidates
                ],
            }
            try:
                validate_payload("MarketComparisonInput@v1", payload)
            except (ValidationError, SchemaNotImplementedError):
                _fail(db, comparison, operation_id, "input_schema",
                      "Die Vergleichsanfrage konnte nicht aufgebaut werden.")
                db.commit()
                return

            ensure_registered()
            recording.record_control(
                db, workspace_id=comparison.workspace_id, project_id=comparison.project_id,
                comparison_id=comparison.comparison_id, control_id="CTRL.DATA_POLICY",
                status="passed", detail="public_source_only",
            )
            request = gateway.ModelRequest(
                profile_id=PROFILE_ID, workspace_id=comparison.workspace_id,
                input_payload=payload, classification=dict(_MODEL_CLASSIFICATION),
                processing_mode="cloud_assisted", run_id=None,
                project_id=comparison.project_id,
                prompt_version=prompt_version_for(PROFILE_ID),
            )
            result = gateway.invoke(db, request, provider_resolver=_resolver(candidates))

            if isinstance(result, gateway.SafeFailure):
                _fail(db, comparison, operation_id, result.error_code,
                      "Der Vergleich konnte nicht erstellt werden.")
                db.commit()
                return

            persisted = _persist(db, comparison, candidates, result)
            comparison.status = "ready_for_review"
            comparison.generation_status = "succeeded"
            recording.record_audit(
                db, workspace_id=comparison.workspace_id, actor_user_id=None,
                action="market_comparison.succeeded", comparison_id=comparison.comparison_id,
                detail={"item_count": persisted},
            )
            _finish_operation(db, operation_id, "succeeded")
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            _safe_fail(comparison_id, operation_id, "MARKET_EXECUTION_FAILED")
        finally:
            db.close()


def _persist(db, comparison, candidates, response) -> None:
    out = response.output
    by_fragment = {c.fragment_id: c for c in candidates}
    seen_names: set[str] = set()
    count = 0
    for rec in out.items:
        if count >= cost_guard.MAX_ITEMS_PER_COMPARISON:
            break
        name = (rec.name or "").strip()
        if not name:
            continue
        norm = normalize_for_match(name)
        if norm in seen_names:
            continue  # dedup by normalized name
        seen_names.add(norm)

        verified_refs: list[dict] = []
        source_doc_ids: list[str] = []
        cand = by_fragment.get(rec.source_fragment_id) if rec.source_fragment_id else None
        if cand is not None and rec.quote:
            fragment = db.get(SourceFragment, cand.fragment_id)
            if fragment is not None:
                ref = verify.verify_quote(
                    db, fragment=fragment,
                    source_document_id=cand.source_document_id, quote=rec.quote,
                )
                if ref is not None:
                    verified_refs.append(ref)
                    source_doc_ids.append(cand.source_document_id)

        if verified_refs:
            confidence, status = "source_backed", "proposed"
        else:
            # No exact verified quote → never presented as confirmed (rules 5/8).
            confidence, status = "insufficient_evidence", "needs_human_review"

        db.add(MarketComparisonItem(
            item_id=str(uuid.uuid4()),
            comparison_id=comparison.comparison_id,
            workspace_id=comparison.workspace_id,
            name=name,
            name_normalized=norm,
            category=rec.category,
            description=rec.description,
            target_customer_segment=rec.target_customer_segment,
            offering_summary=rec.offering_summary,
            strengths=rec.strengths,
            weaknesses=rec.weaknesses,
            differentiation_relevance=rec.differentiation_relevance,
            relation_to_project=rec.relation_to_project,
            confidence_label=confidence,
            status=status,
            source_document_ids=source_doc_ids,
            verified_quote_refs=verified_refs,
        ))
        count += 1

    comparison.research_gaps = list(out.research_gaps or [])
    comparison.warnings = list(out.warnings or [])
    return count


def _complete_empty(db, comparison, operation_id, gap: str) -> None:
    comparison.status = "ready_for_review"
    comparison.generation_status = "skipped"
    comparison.research_gaps = [gap]
    comparison.warnings = []
    recording.record_audit(
        db, workspace_id=comparison.workspace_id, actor_user_id=None,
        action="market_comparison.empty", comparison_id=comparison.comparison_id,
        detail={"reason": "no_source_backed_items"},
    )
    _finish_operation(db, operation_id, "succeeded")


def _fail(db, comparison, operation_id, code: str, detail: str) -> None:
    comparison.status = "failed"
    comparison.generation_status = "failed"
    comparison.error_code = code
    comparison.safe_error_detail = detail
    recording.record_audit(
        db, workspace_id=comparison.workspace_id, actor_user_id=None,
        action="market_comparison.failed", comparison_id=comparison.comparison_id,
        detail={"reason": code},
    )
    _finish_operation(db, operation_id, "failed", code, detail)


def _safe_fail(comparison_id: str, operation_id: str, code: str) -> None:
    db = SessionLocal()
    try:
        comparison = db.get(MarketComparison, comparison_id)
        if comparison is not None and comparison.status not in ("ready_for_review", "failed"):
            comparison.status = "failed"
            comparison.generation_status = "failed"
            comparison.error_code = code
            comparison.safe_error_detail = "Der Vergleich konnte nicht erstellt werden."
        _finish_operation(db, operation_id, "failed", code, "Comparison failed.")
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    finally:
        db.close()
