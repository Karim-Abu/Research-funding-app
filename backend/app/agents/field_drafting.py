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
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import a2_fields, data_policy, gateway, generation
from app.agents import field_drafting_context as a2_context
from app.agents.a2_fields import A2FieldConfig
from app.agents.prompt_assets import prompt_version_for
from app.agents.proposal import build_proposal, proposal_anchor_violations
from app.agents.schemas import (
    SchemaNotImplementedError,
    ValidationError,
    validate_payload,
)
from app.config import provider_policy
from app.config.settings import get_settings
from app.db.models import AgentInvocation, AnalysisRun, ProcessingConfirmation, Project
from app.evaluation.data_mode import derive_data_mode
from app.drafts.charcount import char_count, within_limit
from app.repositories import audit, controls
from app.repositories import draft_suggestions as suggestions_repo
from app.drafts.sections import (
    SectionStructureError,
    extract_section,
    validate_section_candidate,
)
from app.runs.cloud_policy import REAL_AI_EVAL_CONFIRMATION_TEXT_VERSION

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
    if get_settings().agent_fake_provider:
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
    suggestion_id: str | None = None
    invocation_id: str | None = None
    view: dict | None = None  # operation.result payload for the frontend


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
    classification = _classification(run)
    if classification.get("origin") not in ("synthetic", "anonymized"):
        return False
    try:
        db = Session.object_session(run)
    except Exception:
        return False
    if db is None:
        return False
    project = db.get(Project, run.project_id) if run.project_id else None
    if project is None or (project.data_classification or {}).get("origin") not in (
        "synthetic", "anonymized"
    ):
        return False
    return db.scalar(
        select(ProcessingConfirmation.confirmation_id).where(
            ProcessingConfirmation.used_by_run_id == run.run_id,
            ProcessingConfirmation.processing_mode == "cloud_assisted",
            ProcessingConfirmation.status == "used",
            ProcessingConfirmation.confirmation_text_version
            == REAL_AI_EVAL_CONFIRMATION_TEXT_VERSION,
        )
    ) is not None


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
    route = registry.route(registry.profile(config.profile_id).primary_model)
    adapter = None if settings.agent_fake_provider else _PROVIDER_RESOLVER(route)
    is_demo = settings.agent_fake_provider or (
        adapter is not None
        and provider_policy.kind_of_adapter(adapter)
        == provider_policy.ProviderKind.FAKE_LOCAL
        and adapter.available()
    )
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
    # A provider must actually be available: a real configured route OR the dev/test
    # fake. Without either, A2 is unavailable (503) rather than a failing async job.
    # Uses the module-level resolver so the orchestrator and this pre-check agree.
    if mode == "cloud_assisted" and not is_demo:
        if adapter is None or not adapter.available():
            return False, "provider_unavailable"
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


_NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:[.,'’]\d+)*(?:\s?%)?")
_PATENT_RE = re.compile(r"\b(?:EP|WO|US|CH)\s?\d{4,}(?:[/.-]\d+)*\b", re.I)
_ORG_RE = re.compile(
    r"\b(?:[A-ZÄÖÜ][\wÄÖÜäöüß&-]+\s+){0,5}"
    r"(?:AG|GmbH|Ltd\.?|Inc\.?|University|Universität|Hochschule|Institute|Institut)\b"
)


def _unsupported_generated_tokens(text: str, allowed_corpus: str) -> str | None:
    allowed_numbers = {token.casefold() for token in _NUMBER_RE.findall(allowed_corpus or "")}
    allowed_patents = {token.casefold() for token in _PATENT_RE.findall(allowed_corpus or "")}
    allowed_organisations = {
        " ".join(token.split()).casefold()
        for token in _ORG_RE.findall(allowed_corpus or "")
    }
    for token in _PATENT_RE.findall(text or ""):
        if token.casefold() not in allowed_patents:
            return "invented_patent_identifier"
    for token in _NUMBER_RE.findall(text or ""):
        if token.casefold() not in allowed_numbers:
            return "invented_numeric_token"
    for token in _ORG_RE.findall(text or ""):
        if " ".join(token.split()).casefold() not in allowed_organisations:
            return "invented_partner_name"
    return None


def _validate_candidate(
    bundle, ctx, config: A2FieldConfig, target_section: str | None
) -> tuple[_Validated | None, str]:
    if target_section is not None:
        cand = bundle.section_candidate
        if cand.field_id != config.field_id or cand.target_section != target_section:
            return None, "section_target_mismatch"
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
        claim_text = "\n".join([
            cand.suggested_text,
            *cand.preserved_facts,
            *cand.removed_or_reframed_claims,
            *cand.new_claims,
        ])
        unsafe = _unsupported_generated_tokens(claim_text, ctx.context_text)
        if unsafe:
            return None, unsafe
        if a2_context.application_language_conflicts(cand.suggested_text, ctx.language):
            return None, "application_language_changed"
        if proposal_anchor_violations(cand.evidence_anchor_ids, ctx.allowed_anchor_ids):
            return None, "unknown_evidence_anchor"
        if next((i for i in cand.open_issue_ids if i not in ctx.allowed_issue_ids), None):
            return None, "unknown_open_issue"
        placeholders = [p.model_dump() for p in cand.missing_inputs]
        warnings = list(bundle.warnings or [])
        if placeholders:
            warnings.append("contains_placeholders")
        return _Validated(
            candidate=cand,
            warnings=warnings,
            placeholders=placeholders,
            section_result=cand.model_dump(mode="json"),
        ), ""

    candidates = [c for c in bundle.draft_candidates if c.field_id == config.field_id]
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
    unsafe = _unsupported_generated_tokens(cand.suggested_text, ctx.context_text)
    if unsafe:
        return None, unsafe
    return _Validated(
        candidate=cand, warnings=warnings,
        placeholders=[p.model_dump() for p in bundle.placeholders],
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
         guidance, target_section, resolver) -> A2Outcome:
    field_id = config.field_id
    is_composite = bool(config.mandatory_markers)
    if (
        is_composite and target_section is not None
        and target_section not in config.mandatory_markers
    ):
        return A2Outcome(status="failed", reason="target_section_unknown")
    if not is_composite and target_section is not None:
        return A2Outcome(status="failed", reason="target_section_not_supported")
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
                         invocation_id=result.invocation_id)

    validated, reason = _validate_candidate(result.output, ctx, config, target_section)
    if validated is None:
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            control_id="CTRL.OUTPUT_SCHEMA", status="failed", detail=reason,
            run_id=run.run_id, agent_invocation_id=result.invocation_id,
        )
        _audit(db, run, "agent.field_drafting.failed", field_id, {"reason": reason})
        return A2Outcome(status="failed", reason=reason,
                         invocation_id=result.invocation_id)

    cand = validated.candidate
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
        section_result_json=validated.section_result,
        suggested_text=cand.suggested_text,
        rationale=cand.rationale,
        evidence_anchor_ids=list(cand.evidence_anchor_ids),
        open_issue_ids=list(cand.open_issue_ids),
        placeholders=validated.placeholders,
        character_count=char_count(cand.suggested_text),
    )
    _audit(db, run, "agent.field_drafting.succeeded", field_id,
           {"suggestion_id": suggestion.suggestion_id,
            "character_count": suggestion.character_count})
    return A2Outcome(
        status="succeeded", suggestion_id=suggestion.suggestion_id,
        invocation_id=result.invocation_id,
        view=_suggestion_view(db, run, suggestion, evidence=ctx.verified_evidence,
                              warnings=validated.warnings),
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
    return {
        "suggestion_id": suggestion.suggestion_id,
        "operation_id": suggestion.operation_id,
        "field_id": suggestion.field_id,
        "target_section": suggestion.target_section,
        "generation_kind": suggestion.generation_kind,
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
        # mode="json": datetime → ISO-String für die AsyncOperation-JSON-Spalte.
        "proposal": proposal_json,
        "ai_proposal": (
            proposal_json
            if suggestion.generation_kind == generation.MODEL_GENERATED else None
        ),
    }
