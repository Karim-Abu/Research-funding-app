"""A2 Solution & Innovation drafting orchestrator (Milestone 9D).

Runs A2.solution_innovation through the ModelGateway to produce an **advisory** draft
suggestion for SOL.INNOVATION_SOLUTION.EDITOR. Validates structure (mandatory 4.1-4.5),
the 25000-char limit (strict, never trimmed) and evidence/open-issue references, then
persists a DraftSuggestion(proposed). Never raises; never mutates the draft. Accepting is
an explicit, separate user action (updateField). Invoked from the createRedraft async
executor.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import a2_fields, allowed_facts, data_policy, gateway, generation
from app.agents import field_drafting_context as a2_context
from app.agents.a2_fields import A2FieldConfig
from app.agents.prompt_assets import prompt_version_for
from app.agents.proposal import build_proposal, proposal_anchor_violations
from app.agents.schemas import (
    SchemaNotImplementedError,
    ValidationError,
    validate_payload,
)
from app.config.settings import get_settings
from app.db.models import (
    AgentInvocation,
    AnalysisRun,
    ResearchResult,
    ResearchTask,
    SourceDocument,
    SourceVersion,
)
from app.evaluation.data_mode import derive_data_mode
from app.drafts.charcount import char_count, within_limit
from app.repositories import audit, controls
from app.repositories import draft_suggestions as suggestions_repo
from app.drafts.sections import (
    SectionStructureError,
    extract_section,
    validate_section_candidate,
)
from app.runs.cloud_policy import real_eval_confirmed as _run_real_eval_confirmed

logger = logging.getLogger("app.agents.field_drafting")

FIELD_INPUT_SCHEMA = "FieldDraftingInput@v1"
FIELD_OUTPUT_SCHEMA = "PortalFieldDraftBundle@v1"
SECTION_INPUT_SCHEMA = "SectionDraftingInput@v1"
SECTION_OUTPUT_SCHEMA = "PortalSectionDraftBundle@v1"
# Backward-compatible SOL entry point used by M9D tests.
SOLUTION_INNOVATION_FIELD_ID = "SOL.INNOVATION_SOLUTION.EDITOR"

_PROVIDER_RESOLVER = gateway.default_provider_resolver


def _default_resolver(config: A2FieldConfig, target_section: str | None = None):
    """Real adapters by default; a deterministic, field-aware fake when the dev/test
    flag is set. The fake text preserves the field's registry mandatory markers."""
    settings = get_settings()
    if settings.agent_fake_provider and settings.ai_eval_mode != "real":
        import json

        from app.agents.providers import FakeProvider

        if target_section is not None:
            section_bundle = {
                "section_candidate": {
                    "field_id": config.field_id,
                    "target_section": target_section,
                    "suggested_text": extract_section(
                        config.fake_text, config.mandatory_markers, target_section
                    ),
                    "rationale": "Deterministische Demo-Ausgabe fuer UI-/CI-Tests.",
                    "preserved_facts": [],
                    "removed_or_reframed_claims": [],
                    "new_claims": [],
                    "missing_inputs": [],
                    "evidence_anchor_ids": [],
                    "research_source_ids": [],
                    "open_issue_ids": [],
                },
                "warnings": ["fake_demo_no_model"],
            }
            return lambda _route: FakeProvider(raw_output=json.dumps(section_bundle))

        bundle = {
            "draft_candidates": [{
                "field_id": config.field_id, "suggested_text": config.fake_text,
                "rationale": "An verfügbare Belege und Anforderungen angepasst.",
                "evidence_anchor_ids": [], "open_issue_ids": [],
            }],
            "placeholders": [], "field_level_warnings": [],
        }
        return lambda _route: FakeProvider(raw_output=json.dumps(bundle))
    return _PROVIDER_RESOLVER


@dataclass
class A2Outcome:
    status: str  # succeeded | reused | skipped | blocked | failed
    reason: str = ""
    # Sicherer Detailgrund der letzten Route (z. B. timeout/provider_outage) —
    # unterscheidet transiente Providerfehler von Policy-/Schema-Fehlern.
    safe_detail: str = ""
    suggestion_id: str | None = None
    invocation_id: str | None = None
    view: dict | None = None  # operation.result payload for the frontend
    # Beobachtungen des Erlaubt-Gates und der Routing-Bindung (nur Codes/
    # Zählwerte/Tokens — nie Fliesstext). Für Evaluation und Review.
    claim_check: dict = field(default_factory=dict)


def _audit(
    db: Session, run: AnalysisRun, action: str, field_id: str, detail: dict | None = None
) -> None:
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None, action=action,
        target_type="portal_field_draft", target_id=field_id, detail=detail,
    )


def _classification(run: AnalysisRun) -> dict:
    return dict(run.effective_data_classification or {})


def local_ai_confirmed(run: AnalysisRun) -> bool:
    """The product has no approved local/institutional model adapter yet."""

    # FakeProvider is a demo generator and must never unlock a local-AI path.
    return False


def real_eval_confirmed(run: AnalysisRun) -> bool:
    return _run_real_eval_confirmed(run)


def availability(run: AnalysisRun, field_id: str) -> tuple[bool, str]:
    """Per-run availability for createRedraft's 503 pre-check, for a specific A2
    field. Reads the run's existing processing mode + classification — NEVER upgrades
    the mode."""
    config = a2_fields.resolve_field_config(field_id)
    if config is None:
        return False, "field_not_supported"
    mode = run.processing_mode
    settings = get_settings()
    registry = gateway.get_agent_registry()
    if mode == "deterministic_only":
        return False, "processing_mode_deterministic_only"
    if mode == "local_only":
        return False, "local_ai_provider_unavailable"
    from app.evaluation.preflight import (
        live_fake_conflict,
        ready_route_for_role,
    )
    if live_fake_conflict(settings):
        return False, "live_fake_conflict"
    is_demo = settings.agent_fake_provider and settings.ai_eval_mode != "real"
    confirmed = real_eval_confirmed(run)
    if not is_demo and not confirmed:
        return False, "real_eval_confirmation_required"
    decision = data_policy.evaluate(
        profile=registry.profile(config.profile_id), classification=_classification(run),
        processing_mode=mode, settings=settings, run_confirmation=confirmed,
        local_provider=False,
    )
    if decision.blocked:
        return False, decision.reason
    if mode in ("cloud_assisted", "live") and not is_demo:
        try:
            db = Session.object_session(run)
        except Exception:
            db = None
        _route_key, reason = ready_route_for_role(
            db, "A2_INNOSUISSE_PROPOSAL_WRITER",
            settings=settings, registry=registry,
        )
        if reason:
            return False, reason
    return True, "available"


def _mandatory_structure_ok(text: str, markers: tuple[str, ...]) -> bool:
    # Semantic check: every registry mandatory question represented by its section
    # number (SOL 4.1–4.5, VC 3.1/3.2), not brittle byte-identical labels.
    return all(marker in text for marker in markers)


@dataclass
class _Validated:
    candidate: object
    warnings: list = field(default_factory=list)
    placeholders: list = field(default_factory=list)
    section_result: dict | None = None
    # Zahlen, die aus bekannten Werten deterministisch ableitbar sind: kein
    # Beleg, aber auch keine Erfindung — sie gehen ins menschliche Review.
    derived_numbers: list = field(default_factory=list)
    # Das Modell hat abweichende Routing-IDs geliefert. Der Caller bindet die
    # kanonischen Werte; der Widerspruch bleibt sichtbar (nie still korrigiert).
    routing_mismatch: bool = False


def _proposal_contract_v2(
    validated: _Validated,
    config: A2FieldConfig,
    target_section: str | None,
) -> dict:
    """Project the existing advisory A2 result to the additive v2 contract.

    The provider-facing v1 bundles stay in place for route compatibility.  This
    normalized representation is stored alongside the existing section result,
    so suggestion and review views do not need a second pipeline or a breaking
    API change.
    """
    candidate = validated.candidate
    missing = [
        {"label": str(item.get("label") or "Eingabe fehlt"),
         "reason": str(item.get("reason") or "Menschliche Klärung erforderlich")}
        for item in validated.placeholders
        if isinstance(item, dict)
    ]
    payload = {
        "field_id": config.field_id,
        "section_id": target_section,
        "proposed_text": candidate.suggested_text,
        "character_count": char_count(candidate.suggested_text),
        "character_limit": config.char_limit,
        "change_summary": [candidate.rationale] if candidate.rationale else [],
        "preserved_facts": list(getattr(candidate, "preserved_facts", []) or []),
        "evidence_refs": list(getattr(candidate, "evidence_anchor_ids", []) or []),
        # Only explicit candidate labels are represented here; no inferred
        # semantic support is manufactured from an exact source location.
        "applicant_claims_used": list(getattr(candidate, "preserved_facts", []) or []),
        "unsupported_claims": list(getattr(candidate, "new_claims", []) or []),
        "missing_inputs": missing,
        "removed_non_final_content": list(
            getattr(candidate, "removed_or_reframed_claims", []) or []
        ),
        "confidence": "low" if missing else "medium",
        "requires_human_review": True,
    }
    return validate_payload("ProposalSectionSuggestion@v2", payload).model_dump(mode="json")


def _bind_routing_metadata(candidate, *, field_id: str, target_section: str | None):
    """Routing-IDs deterministisch aus dem Request setzen (Caller-Bindung).

    Der Aufrufer kennt Feld und Zielabschnitt; das Modell muss sie nicht
    erraten. Es liefert weiterhin Inhalt, Begründung und Vorschlag — die
    kanonische Quelle der IDs ist der Request. Ein abweichender Modellwert wird
    NICHT still übernommen, sondern als Widerspruch zurückgemeldet; die
    fachliche Abschnittstreue prüfen unverändert die Struktur-Gates.
    """
    fields = {"field_id": field_id}
    mismatch = candidate.field_id != field_id
    if target_section is not None:
        fields["target_section"] = target_section
        mismatch = mismatch or candidate.target_section != target_section
    return candidate.model_copy(update=fields), mismatch


def _validate_candidate(
    bundle, ctx, config: A2FieldConfig, target_section: str | None,
    manifest: allowed_facts.AllowedFactsManifest,
) -> tuple[_Validated | None, str]:
    if target_section is not None:
        cand, routing_mismatch = _bind_routing_metadata(
            bundle.section_candidate,
            field_id=config.field_id, target_section=target_section,
        )
        if not cand.suggested_text.strip():
            return None, "empty_suggested_text"
        try:
            validate_section_candidate(
                cand.suggested_text, config.mandatory_markers, target_section
            )
        except SectionStructureError as exc:
            return None, exc.code
        if not within_limit(cand.suggested_text, config.char_limit):
            return None, "character_limit_exceeded"
        placeholder_text = [
            " ".join(
                part for part in (item.label, item.reason or "") if part
            )
            for item in cand.missing_inputs
        ]
        claim_text = "\n".join([
            cand.suggested_text,
            *cand.preserved_facts,
            *cand.removed_or_reframed_claims,
            *cand.new_claims,
            *placeholder_text,
        ])
        check = allowed_facts.check_claims(claim_text, manifest)
        if check.reason:
            return None, check.reason
        if a2_context.application_language_conflicts(cand.suggested_text, ctx.language):
            return None, "application_language_changed"
        if proposal_anchor_violations(cand.evidence_anchor_ids, ctx.allowed_anchor_ids):
            return None, "unknown_evidence_anchor"
        if next(
            (source_id for source_id in cand.research_source_ids
             if source_id not in ctx.allowed_research_source_ids),
            None,
        ):
            return None, "unknown_research_source"
        if next((i for i in cand.open_issue_ids if i not in ctx.allowed_issue_ids), None):
            return None, "unknown_open_issue"
        if cand.new_claims and not (
            cand.evidence_anchor_ids or cand.research_source_ids
        ):
            return None, "new_claim_without_source"
        placeholders = [p.model_dump() for p in cand.missing_inputs]
        warnings = list(bundle.warnings or [])
        if placeholders:
            warnings.append("contains_placeholders")
        if ctx.meta.get("language_needs_review"):
            warnings.append("application_language_needs_review")
        if check.derived_numbers:
            warnings.append("contains_derived_numeric_claims")
        if routing_mismatch:
            warnings.append("model_routing_metadata_mismatch")
        return _Validated(
            candidate=cand,
            warnings=warnings,
            placeholders=placeholders,
            section_result=cand.model_dump(mode="json"),
            derived_numbers=list(check.derived_numbers),
            routing_mismatch=routing_mismatch,
        ), ""

    candidates = [c for c in bundle.draft_candidates if c.field_id == config.field_id]
    routing_mismatch = False
    if not candidates and len(bundle.draft_candidates) == 1:
        # Einzelfeld-Lauf: der Caller kennt das Feld. Eine abweichende Modell-ID
        # ist ein Routing-Widerspruch, kein fehlender Kandidat.
        cand, routing_mismatch = _bind_routing_metadata(
            bundle.draft_candidates[0], field_id=config.field_id,
            target_section=None,
        )
        candidates = [cand]
    if not candidates:
        return None, "no_candidate_for_field"
    cand = candidates[0]
    if not cand.suggested_text.strip():
        return None, "empty_suggested_text"
    if not within_limit(cand.suggested_text, config.char_limit):  # strict, never trimmed
        return None, "character_limit_exceeded"
    if not _mandatory_structure_ok(cand.suggested_text, config.mandatory_markers):
        return None, "mandatory_structure_missing"
    # R5.2: used_anchor_ids ⊆ allowed_anchor_ids (wiederverwendbarer Helper).
    if proposal_anchor_violations(cand.evidence_anchor_ids, ctx.allowed_anchor_ids):
        return None, "unknown_evidence_anchor"
    bad_issue = next(
        (i for i in cand.open_issue_ids if i not in ctx.allowed_issue_ids), None
    )
    if bad_issue is not None:
        return None, "unknown_open_issue"
    warnings = []
    if bundle.placeholders:
        warnings.append("contains_placeholders")
    if ctx.advisory_facts:
        warnings.append("based_on_unconfirmed_facts")
    if ctx.meta.get("language_needs_review"):
        warnings.append("application_language_needs_review")
    check = allowed_facts.check_claims(cand.suggested_text, manifest)
    if check.reason:
        return None, check.reason
    if check.derived_numbers:
        warnings.append("contains_derived_numeric_claims")
    if routing_mismatch:
        warnings.append("model_routing_metadata_mismatch")
    return _Validated(
        candidate=cand, warnings=warnings,
        placeholders=[p.model_dump() for p in bundle.placeholders],
        derived_numbers=list(check.derived_numbers),
        routing_mismatch=routing_mismatch,
    ), ""


def run_a2_field_drafting(
    db: Session,
    run: AnalysisRun,
    *,
    field_id: str,
    draft_id: str,
    base_version_id: str,
    operation_id: str,
    guidance: str | None = None,
    target_section: str | None = None,
    provider_resolver=None,
    model_preference: str = "primary",
) -> A2Outcome:
    """Generate + validate + persist an advisory A2 suggestion for an A2-enabled field.
    Never raises. The field→profile/limit/markers binding comes from the registry."""
    config = a2_fields.resolve_field_config(field_id)
    if config is None:
        return A2Outcome(status="failed", reason="field_not_supported")
    try:
        return _run(
            db, run, config, draft_id=draft_id, base_version_id=base_version_id,
            operation_id=operation_id, guidance=guidance,
            target_section=target_section,
            resolver=provider_resolver or _default_resolver(config, target_section),
            model_preference=model_preference,
        )
    except Exception:  # defensive: A2 must never break the request/run
        logger.exception("A2 field drafting crashed; run %s field %s", run.run_id, field_id)
        _audit(db, run, "agent.field_drafting.failed", field_id, {"reason": "internal_error"})
        return A2Outcome(status="failed", reason="internal_error")


def run_a2_solution_innovation(
    db: Session,
    run: AnalysisRun,
    *,
    draft_id: str,
    base_version_id: str,
    operation_id: str,
    guidance: str | None = None,
    provider_resolver=None,
) -> A2Outcome:
    """Backward-compatible SOL entry point (M9D)."""
    return run_a2_field_drafting(
        db, run, field_id=SOLUTION_INNOVATION_FIELD_ID, draft_id=draft_id,
        base_version_id=base_version_id, operation_id=operation_id, guidance=guidance,
        provider_resolver=provider_resolver,
    )


def _run(db, run, config: A2FieldConfig, *, draft_id, base_version_id, operation_id,
         guidance, target_section, resolver,
         model_preference: str = "primary") -> A2Outcome:
    field_id = config.field_id
    is_composite = bool(config.mandatory_markers)
    if (
        is_composite and target_section is not None
        and target_section not in config.mandatory_markers
    ):
        return A2Outcome(status="failed", reason="target_section_unknown")
    if not is_composite and target_section is not None:
        return A2Outcome(status="failed", reason="target_section_not_supported")
    skill_id = a2_fields.skill_id_for(field_id, target_section)
    if skill_id is None:
        return A2Outcome(status="failed", reason="skill_not_configured")
    # Replay/idempotency: reuse an existing proposed suggestion for this base.
    existing = suggestions_repo.get_proposed_for(
        db, run.run_id, draft_id, base_version_id, target_section
    )
    if existing is not None:
        return A2Outcome(status="reused", suggestion_id=existing.suggestion_id,
                         view=_suggestion_view(db, run, existing))

    mode = run.processing_mode
    if mode == "deterministic_only":
        _audit(db, run, "agent.field_drafting.skipped", field_id, {"reason": f"mode_{mode}"})
        return A2Outcome(status="skipped", reason=f"mode_{mode}")
    confirmed = real_eval_confirmed(run)
    if mode == "local_only":
        reason = "local_ai_provider_unavailable"
        _audit(db, run, "agent.field_drafting.skipped", field_id, {"reason": reason})
        return A2Outcome(status="skipped", reason=reason)

    _audit(db, run, "agent.field_drafting.started", field_id, {"profile_id": config.profile_id})
    try:
        ctx = a2_context.assemble_a2_context(
            db, run, field_id=field_id, profile_id=config.profile_id,
            target_section=target_section, section_markers=config.mandatory_markers,
        )
    except (a2_context.ContextBudgetError, SectionStructureError) as exc:
        reason = getattr(exc, "code", str(exc))
        _audit(db, run, "agent.field_drafting.skipped", field_id, {"reason": reason})
        return A2Outcome(status="skipped", reason=reason)
    input_payload = a2_context.build_input_payload(ctx, run.run_id)
    # Erlaubt-Basis VOR dem Modellaufruf und aus derselben finalen Auswahl, die
    # in den Request geht (Payload + budgetierter Kontext).
    manifest = a2_context.build_allowed_facts(ctx, input_payload)
    input_schema = SECTION_INPUT_SCHEMA if target_section is not None else FIELD_INPUT_SCHEMA
    try:
        validate_payload(input_schema, input_payload)
    except (ValidationError, SchemaNotImplementedError):
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            control_id="CTRL.INPUT_SCHEMA", status="failed",
            detail="a2_input_schema_invalid",
            run_id=run.run_id,
        )
        _audit(db, run, "agent.field_drafting.skipped", field_id, {"reason": "input_schema"})
        return A2Outcome(status="skipped", reason="input_schema")

    request = gateway.ModelRequest(
        profile_id=config.profile_id, workspace_id=run.workspace_id, input_payload=input_payload,
        classification=_classification(run), processing_mode=mode, run_id=run.run_id,
        project_id=run.project_id, run_confirmation=confirmed,
        prompt_version=prompt_version_for(config.profile_id), context_text=ctx.context_text,
        context_hash=ctx.context_hash, context_meta=ctx.meta,
        input_schema_id=input_schema,
        output_schema_id=(
            SECTION_OUTPUT_SCHEMA if target_section is not None else FIELD_OUTPUT_SCHEMA
        ),
        skill_id=skill_id,
        # Kein stiller Fallback (provisorische Demo-Route): die Alternative
        # läuft nur auf expliziten Nutzerwunsch («Mit alternativem Modell
        # versuchen»).
        route_preference=(
            "fallback_only" if model_preference == "alternative" else "primary_only"
        ),
        input_artifact_refs=(
            {
                "kind": "a2_field_context",
                "run_id": run.run_id,
                "field_id": field_id,
                "target_section": target_section or "",
                "context_hash": ctx.context_hash,
                "evidence_anchor_ids": sorted(ctx.allowed_anchor_ids),
                "open_issue_ids": sorted(ctx.allowed_issue_ids),
            },
        ),
    )
    result = gateway.invoke(db, request, provider_resolver=resolver)

    for control_id, detail in (
        ("CTRL.TOOL_AUTHORIZATION", "a2_tools_authorized"),
        ("CTRL.INPUT_SCHEMA", "input_validated"),
        ("CTRL.EVIDENCE_REQUIREMENT", "draft_requires_human_review"),
    ):
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            control_id=control_id, status="passed", detail=detail, run_id=run.run_id,
            agent_invocation_id=result.invocation_id,
        )

    if isinstance(result, gateway.SafeFailure):
        _audit(db, run, "agent.field_drafting.failed", field_id, {"reason": result.error_code})
        return A2Outcome(status=result.status, reason=result.error_code,
                         safe_detail=result.safe_detail,
                         invocation_id=result.invocation_id)

    claim_check = {
        "routing_metadata_source": "caller_bound",
        "allowed_facts": manifest.meta(),
    }
    validated, reason = _validate_candidate(
        result.output, ctx, config, target_section, manifest
    )
    if validated is None:
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            control_id="CTRL.OUTPUT_SCHEMA", status="failed", detail=reason,
            run_id=run.run_id, agent_invocation_id=result.invocation_id,
        )
        _audit(db, run, "agent.field_drafting.failed", field_id, {"reason": reason})
        return A2Outcome(status="failed", reason=reason,
                         invocation_id=result.invocation_id,
                         claim_check=claim_check)
    claim_check.update(
        derived_numeric_claims=list(validated.derived_numbers),
        routing_metadata_mismatch=validated.routing_mismatch,
    )

    cand = validated.candidate
    # Keep the established v1 result shape readable for existing views while
    # persisting the normalized v2 professional contract under a namespaced
    # key.  Nothing consumes this data as an automatic draft update.
    section_result = dict(validated.section_result or {})
    section_result["role_skill_contract_v2"] = _proposal_contract_v2(
        validated, config, target_section
    )
    suggestion = suggestions_repo.create(
        db, run, draft_id=draft_id, base_version_id=base_version_id, field_id=field_id,
        profile_id=config.profile_id, operation_id=operation_id,
        agent_invocation_id=result.invocation_id,
        prompt_version=(
            prompt_version_for(config.profile_id)
            if result.generation_kind == generation.MODEL_GENERATED else None
        ),
        model_route=(
            result.provider
            if result.generation_kind == generation.MODEL_GENERATED else None
        ),
        model_id=(
            result.model_id
            if result.generation_kind == generation.MODEL_GENERATED else None
        ),
        generation_kind=result.generation_kind,
        target_section=target_section,
        section_result_json=section_result,
        suggested_text=cand.suggested_text,
        rationale=cand.rationale,
        evidence_anchor_ids=list(cand.evidence_anchor_ids),
        open_issue_ids=list(cand.open_issue_ids),
        placeholders=validated.placeholders,
        character_count=char_count(cand.suggested_text),
    )
    _audit(db, run, "agent.field_drafting.succeeded", field_id,
           {"suggestion_id": suggestion.suggestion_id,
            "character_count": suggestion.character_count,
            "derived_numeric_claim_count": len(validated.derived_numbers),
            "routing_metadata_mismatch": validated.routing_mismatch})
    return A2Outcome(
        status="succeeded", suggestion_id=suggestion.suggestion_id,
        invocation_id=result.invocation_id,
        view=_suggestion_view(db, run, suggestion, evidence=ctx.verified_evidence,
                              warnings=validated.warnings),
        claim_check=claim_check,
    )


def proposed_suggestion_view(db, run, suggestion) -> dict:
    """Read-only View einer bestehenden proposed Suggestion für den
    Suggestion-Read-Endpoint — identisch zum Redraft-Operation-Result
    (Reused-Pfad: Placeholder-Heuristik für die warnings)."""
    return _suggestion_view(db, run, suggestion)


def _suggestion_view(db, run, suggestion, *, evidence: list | None = None,
                     warnings: list | None = None) -> dict:
    """Operation-Result-View plus neutralen DraftProposal-View erstellen.

    Reused-Pfad: warnings fallen auf die Placeholder-Heuristik zurück (kein
    ctx verfügbar) — der DraftProposal übernimmt dieselben safety_notes.
    """
    anchor_ids = set(suggestion.evidence_anchor_ids or [])
    used = [e for e in (evidence or []) if e["anchor_id"] in anchor_ids]
    config = a2_fields.resolve_field_config(suggestion.field_id)
    warn = warnings if warnings is not None else (
        ["contains_placeholders"] if suggestion.placeholders else []
    )
    invocation = (
        db.get(AgentInvocation, suggestion.agent_invocation_id)
        if suggestion.agent_invocation_id else None
    )
    data_mode = derive_data_mode(
        ai_eval_mode=get_settings().ai_eval_mode,
        origin=(run.effective_data_classification or {}).get("origin"),
    )
    proposal = build_proposal(
        suggestion, invocation, data_mode=data_mode, safety_notes=warn
    )
    proposal_json = proposal.model_dump(mode="json")
    research_source_ids = list(
        (suggestion.section_result_json or {}).get("research_source_ids", [])
    )
    research_sources = []
    if research_source_ids:
        rows = db.execute(
            select(SourceDocument, ResearchResult, ResearchTask)
            .join(ResearchResult, ResearchResult.source_document_id == SourceDocument.source_id)
            .join(ResearchTask, ResearchTask.research_task_id == ResearchResult.research_task_id)
            .join(
                SourceVersion,
                SourceVersion.source_version_id == SourceDocument.current_source_version_id,
            )
            .where(
                SourceDocument.source_id.in_(research_source_ids),
                SourceDocument.project_id == run.project_id,
                SourceDocument.status == "processed",
                SourceVersion.processing_status == "processed",
                ResearchResult.status == "imported",
                ResearchResult.content_review_status == "reviewed",
                ResearchResult.support_status.in_(("supports", "partially_supports")),
                ResearchTask.execution_mode == "live",
            )
        )
        by_id = {doc.source_id: (doc, result, task) for doc, result, task in rows}
        for source_id in research_source_ids:
            row = by_id.get(source_id)
            if row is None:
                continue
            doc, result_row, task = row
            research_sources.append({
                "source_id": source_id,
                "title": result_row.title,
                "url": result_row.final_url or result_row.source_url,
                "research_module": task.research_module,
                "support_status": result_row.support_status,
                "content_review_status": result_row.content_review_status,
            })
    return {
        "suggestion_id": suggestion.suggestion_id,
        "operation_id": suggestion.operation_id,
        "field_id": suggestion.field_id,
        "target_section": suggestion.target_section,
        "generation_kind": suggestion.generation_kind,
        "execution_mode": (
            "live"
            if suggestion.generation_kind == generation.MODEL_GENERATED
            else "fake_demo"
        ),
        "base_version_id": suggestion.base_version_id,
        "suggested_text": suggestion.suggested_text,
        "rationale": suggestion.rationale,
        "evidence": used,
        "open_issue_ids": list(suggestion.open_issue_ids or []),
        "placeholders": list(suggestion.placeholders or []),
        "character_count": suggestion.character_count,
        "character_limit": config.char_limit if config else None,
        "warnings": warn,
        "section_result": suggestion.section_result_json,
        "research_sources": research_sources,
        # mode="json": datetime → ISO-String für die AsyncOperation-JSON-Spalte.
        "proposal": proposal_json,
        "ai_proposal": (
            proposal_json
            if suggestion.generation_kind == generation.MODEL_GENERATED else None
        ),
    }
