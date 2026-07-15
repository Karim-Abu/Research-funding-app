"""A1 Public Competence Research orchestrator (Milestone 9I-A).

Advisory synthesis of public professional evidence from IMPORTED public source versions.
Runs at most once per research task, AFTER import, and is fully NON-BLOCKING: any failure
leaves the imported sources intact and records a safe failure (binding correction 6).

It only ever reads locally imported, normalized fragments (never direct network), never
confirms facts, never edits drafts, never selects partners or creates EvidenceAnchors.
Every professional-evidence/partner-role output is advisory and requires human review.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import data_policy, gateway
from app.agents.prompt_assets import prompt_version_for
from app.agents.schemas import SchemaNotImplementedError, ValidationError, validate_payload
from app.config.settings import get_settings
from app.db.models import (
    Project,
    ResearchResult,
    ResearchTask,
    SourceDocument,
    SourceFragment,
    SourceVersion,
)
from app.repositories import audit

logger = logging.getLogger("app.agents.public_competence_research")

PROFILE_ID = "A1.public_competence_research"
INPUT_SCHEMA = "PublicCompetenceResearchInput@v1"
OUTPUT_SCHEMA = "PublicCompetenceResearchResult@v1"
_CONTEXT_CHAR_BUDGET = 16000

# Module-level resolver (tests / real adapters). The web fake provider drives this when
# web_research_fake_provider is set — A1 synthesis is part of the web-research feature.
_PROVIDER_RESOLVER = gateway.default_provider_resolver


def _audit(db: Session, task: ResearchTask, action: str, detail: dict | None = None) -> None:
    audit.record(
        db, workspace_id=task.workspace_id, actor_user_id=None, action=action,
        target_type="research_task", target_id=task.research_task_id, detail=detail,
    )


def _imported_versions(db: Session, task: ResearchTask) -> list[tuple[ResearchResult, str]]:
    """(result, source_version_id) for each imported result with a processed source."""
    rows = db.scalars(
        select(ResearchResult).where(
            ResearchResult.research_task_id == task.research_task_id,
            ResearchResult.status == "imported",
        )
    )
    out: list[tuple[ResearchResult, str]] = []
    for r in rows:
        if not r.source_document_id:
            continue
        doc = db.get(SourceDocument, r.source_document_id)
        if doc and doc.current_source_version_id:
            out.append((r, doc.current_source_version_id))
    return out


def _context_text(db: Session, version_ids: list[str]) -> tuple[str, list[str]]:
    parts: list[str] = []
    used = 0
    selected: list[str] = []
    for vid in version_ids:
        frags = db.scalars(
            select(SourceFragment)
            .where(SourceFragment.source_version_id == vid)
            .order_by(SourceFragment.ordinal)
        )
        for frag in frags:
            block = f"[source_version_id={vid} ordinal={frag.ordinal}]\n{frag.normalized_text}"
            if used + len(block) > _CONTEXT_CHAR_BUDGET:
                break
            parts.append(block)
            used += len(block)
        selected.append(vid)
    return "\n\n".join(parts), selected


def _resolver():
    if get_settings().web_research_fake_provider:
        return _fake_resolver
    return _PROVIDER_RESOLVER


def _fake_resolver(route):
    """Deterministic dev/test fake: one advisory evidence record + one suggestion."""
    import json

    from app.agents.providers.fake import FakeProvider

    bundle = {
        "professional_evidence": [{
            "evidence_type": "institutional_profile",
            "subject_name": "Öffentliches Profil",
            "organisation": "Öffentliche Institution",
            "claim": "Öffentlich dokumentierte fachliche Kompetenz (zu prüfen).",
            "source_url": "https://research.example.org/result/0",
            "source_title": "Öffentliche Quelle",
            "accessed_at": None,
            "source_version_id": None,
        }],
        "partner_role_suggestions": [{
            "role_name": "Forschungspartner",
            "competence_gap": "Fachliche Ergänzung (Vorschlag, fachlich zu prüfen).",
            "suggested_subject_name": "Öffentliches Profil",
            "suggested_organisation": "Öffentliche Institution",
            "professional_evidence_indexes": [0],
        }],
        "unresolved_identity_matches": [],
        "warnings": ["Vorschläge sind advisory und erfordern menschliche Prüfung."],
    }
    return FakeProvider(raw_output=json.dumps(bundle))


def synthesize_after_import(
    db: Session, *, task: ResearchTask | None, project: Project, provider_resolver=None
) -> str:
    """Run A1 synthesis at most once per task. Returns the resulting
    a1_synthesis_status. Never raises (callers rely on import staying intact)."""
    if task is None:
        return "skipped"
    if task.a1_synthesis_status == "succeeded":
        return "succeeded"  # at-most-one successful synthesis per task
    try:
        return _run(db, task, project, provider_resolver or _resolver())
    except Exception:  # noqa: BLE001 — advisory; never break the import
        logger.exception("A1 public-competence synthesis crashed for task %s",
                         task.research_task_id)
        task.a1_synthesis_status = "failed"
        _audit(db, task, "agent.public_competence_research.failed", {"reason": "internal_error"})
        db.commit()
        return "failed"


def _run(db: Session, task: ResearchTask, project: Project, resolver) -> str:
    pairs = _imported_versions(db, task)
    if not pairs:
        task.a1_synthesis_status = "skipped"
        _audit(db, task, "agent.public_competence_research.skipped", {"reason": "no_imported_sources"})
        db.commit()
        return "skipped"

    settings = get_settings()
    registry = gateway.get_agent_registry()
    profile = registry.profile(PROFILE_ID)
    classification = dict(project.data_classification or {})
    mode = classification.get("processing_mode", "")

    decision = data_policy.evaluate(
        profile=profile, classification=classification, processing_mode=mode,
        settings=settings, run_confirmation=False,
    )
    if decision.blocked:
        task.a1_synthesis_status = "skipped"
        _audit(db, task, "agent.public_competence_research.skipped", {"reason": decision.reason})
        db.commit()
        return "skipped"

    version_ids = [vid for _, vid in pairs]
    input_payload = {
        "research_task_id": task.research_task_id,
        "project_id": task.project_id,
        "research_result_source_version_ids": version_ids,
        "requested_partner_roles": list(task.requested_partner_roles or []),
        "competence_needs": list(task.competence_needs or []),
    }
    try:
        validate_payload(INPUT_SCHEMA, input_payload)
    except (ValidationError, SchemaNotImplementedError):
        task.a1_synthesis_status = "skipped"
        _audit(db, task, "agent.public_competence_research.skipped", {"reason": "input_schema"})
        db.commit()
        return "skipped"

    context_text, _selected = _context_text(db, version_ids)
    request = gateway.ModelRequest(
        profile_id=PROFILE_ID,
        workspace_id=task.workspace_id,
        input_payload=input_payload,
        classification=classification,
        processing_mode=mode,
        run_id=None,
        project_id=task.project_id,
        prompt_version=prompt_version_for(PROFILE_ID),
        context_text=context_text,
        context_meta={"research_task_id": task.research_task_id,
                      "imported_version_count": len(version_ids)},
        skill_id="a1.public_competence_research",
        input_artifact_refs=(
            {
                "kind": "imported_public_research",
                "research_task_id": task.research_task_id,
                "source_version_ids": version_ids,
            },
        ),
    )
    result = gateway.invoke(db, request, provider_resolver=resolver, registry=registry)

    if isinstance(result, gateway.SafeFailure):
        # Non-blocking: leave evidence arrays empty, record a safe failure.
        status = "skipped" if result.safe_detail == "provider_unavailable" else "failed"
        task.a1_synthesis_status = status
        _audit(db, task, f"agent.public_competence_research.{status}",
               {"reason": result.error_code})
        db.commit()
        return status

    return _persist(db, task, pairs, result)


def _persist(db: Session, task: ResearchTask, pairs, response) -> str:
    out = response.output
    primary_result, primary_version = pairs[0]
    version_to_result = {vid: r for r, vid in pairs}

    evidence_dicts: list[dict] = []
    for rec in out.professional_evidence:
        vid = rec.source_version_id if rec.source_version_id in version_to_result else primary_version
        target = version_to_result.get(vid, primary_result)
        evidence_dicts.append({
            "professional_evidence_id": str(uuid.uuid4()),
            "evidence_type": rec.evidence_type,
            "subject_name": rec.subject_name,
            "organisation": rec.organisation,
            "claim": rec.claim,
            "source_url": rec.source_url,
            "source_title": rec.source_title,
            "accessed_at": (rec.accessed_at or target.retrieved_at.isoformat()),
            "source_id": target.source_document_id,
        })

    suggestion_dicts: list[dict] = []
    for rec in out.partner_role_suggestions:
        ev_ids = [
            evidence_dicts[i]["professional_evidence_id"]
            for i in rec.professional_evidence_indexes
            if 0 <= i < len(evidence_dicts)
        ]
        suggestion_dicts.append({
            "suggestion_id": str(uuid.uuid4()),
            "role_name": rec.role_name,
            "competence_gap": rec.competence_gap,
            "suggested_subject_name": rec.suggested_subject_name,
            "suggested_organisation": rec.suggested_organisation,
            "professional_evidence_ids": ev_ids,
            "status": "suggested",
            "human_review_required": True,
        })

    # Attach all advisory evidence/suggestions to the primary imported result.
    primary_result.professional_evidence = evidence_dicts
    primary_result.partner_role_suggestions = suggestion_dicts
    task.a1_synthesis_status = "succeeded"
    _audit(db, task, "agent.public_competence_research.succeeded",
           {"evidence": len(evidence_dicts), "suggestions": len(suggestion_dicts),
            "invocation_id": response.invocation_id})
    db.commit()
    return "succeeded"
