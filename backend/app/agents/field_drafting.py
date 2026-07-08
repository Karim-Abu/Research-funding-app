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

from app.agents import a2_fields, data_policy, gateway
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
from app.db.models import AgentInvocation, AnalysisRun, ProcessingConfirmation
from app.evaluation.data_mode import derive_data_mode
from app.drafts.charcount import char_count, within_limit
from app.repositories import audit, controls
from app.repositories import draft_suggestions as suggestions_repo

logger = logging.getLogger("app.agents.field_drafting")

INPUT_SCHEMA = "FieldDraftingInput@v1"
OUTPUT_SCHEMA = "PortalFieldDraftBundle@v1"
# Backward-compatible SOL entry point used by M9D tests.
SOLUTION_INNOVATION_FIELD_ID = "SOL.INNOVATION_SOLUTION.EDITOR"

_PROVIDER_RESOLVER = gateway.default_provider_resolver


def _default_resolver(config: A2FieldConfig):
    """Real adapters by default; a deterministic, field-aware fake when the dev/test
    flag is set. The fake text preserves the field's registry mandatory markers."""
    if get_settings().agent_fake_provider:
        import json

        from app.agents.providers import FakeProvider

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
    """R4.3: True, wenn dieser local_only-Lauf mit einer verbrauchten
    Local-AI-Opt-in-Bestätigung erstellt wurde (Owner-Entscheid 2026-07-08)."""
    try:
        db = Session.object_session(run)
    except Exception:  # kein ORM-Objekt (z. B. Test-Stub) → fail-closed
        return False
    if db is None:
        return False
    return db.scalar(
        select(ProcessingConfirmation.confirmation_id).where(
            ProcessingConfirmation.used_by_run_id == run.run_id,
            ProcessingConfirmation.processing_mode == "local_only",
            ProcessingConfirmation.status == "used",
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
    confirmed = False
    if mode == "local_only":
        # R4.3: lokaler KI-Pfad nur mit Opt-in-Bestätigung des Laufs; ohne sie
        # bleibt der Lauf regelbasiert (kein stiller Upgrade).
        confirmed = local_ai_confirmed(run)
        if not confirmed:
            return False, "processing_mode_local_only"
        if not settings.agent_fake_provider:
            # Der lokale Pfad darf NUR von einem lokalen Adapter bedient werden
            # — direkte Cloud-Adapter sind hier nie zulässig, egal welche Keys
            # gesetzt sind. (Heute existiert nur der Fake als lokaler Adapter.)
            route = registry.route(registry.profile(config.profile_id).primary_model)
            adapter = _PROVIDER_RESOLVER(route)
            if (
                provider_policy.kind_of_adapter(adapter)
                != provider_policy.ProviderKind.FAKE_LOCAL
                or not adapter.available()
            ):
                return False, "provider_unavailable"
    decision = data_policy.evaluate(
        profile=registry.profile(config.profile_id), classification=_classification(run),
        processing_mode=mode, settings=settings, run_confirmation=confirmed,
        local_provider=(mode == "local_only"),
    )
    if decision.blocked:
        return False, decision.reason
    # A provider must actually be available: a real configured route OR the dev/test
    # fake. Without either, A2 is unavailable (503) rather than a failing async job.
    # Uses the module-level resolver so the orchestrator and this pre-check agree.
    if mode == "cloud_assisted" and not settings.agent_fake_provider:
        route = registry.route(registry.profile(config.profile_id).primary_model)
        adapter = _PROVIDER_RESOLVER(route)
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


def _validate_candidate(bundle, ctx, config: A2FieldConfig) -> tuple[_Validated | None, str]:
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
    return _Validated(candidate=cand, warnings=warnings), ""


def run_a2_field_drafting(
    db: Session,
    run: AnalysisRun,
    *,
    field_id: str,
    draft_id: str,
    base_version_id: str,
    operation_id: str,
    guidance: str | None = None,
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
            resolver=provider_resolver or _default_resolver(config),
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
         guidance, resolver) -> A2Outcome:
    field_id = config.field_id
    # Replay/idempotency: reuse an existing proposed suggestion for this base.
    existing = suggestions_repo.get_proposed_for(db, run.run_id, draft_id, base_version_id)
    if existing is not None:
        return A2Outcome(status="reused", suggestion_id=existing.suggestion_id,
                         view=_suggestion_view(db, run, existing))

    mode = run.processing_mode
    if mode == "deterministic_only":
        _audit(db, run, "agent.field_drafting.skipped", field_id, {"reason": f"mode_{mode}"})
        return A2Outcome(status="skipped", reason=f"mode_{mode}")
    confirmed = False
    if mode == "local_only":
        # R4.3: nur mit Opt-in-Bestätigung des Laufs (kein stiller Upgrade).
        confirmed = local_ai_confirmed(run)
        if not confirmed:
            _audit(db, run, "agent.field_drafting.skipped", field_id,
                   {"reason": f"mode_{mode}"})
            return A2Outcome(status="skipped", reason=f"mode_{mode}")

    _audit(db, run, "agent.field_drafting.started", field_id, {"profile_id": config.profile_id})
    ctx = a2_context.assemble_a2_context(db, run, field_id=field_id, profile_id=config.profile_id)
    input_payload = a2_context.build_input_payload(ctx, run.run_id)
    try:
        validate_payload(INPUT_SCHEMA, input_payload)
    except (ValidationError, SchemaNotImplementedError) as exc:
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            control_id="CTRL.INPUT_SCHEMA", status="failed", detail=str(exc)[:200],
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

    validated, reason = _validate_candidate(result.output, ctx, config)
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
        prompt_version=prompt_version_for(config.profile_id), model_route=result.provider,
        model_id=result.model_id, suggested_text=cand.suggested_text,
        rationale=cand.rationale,
        evidence_anchor_ids=list(cand.evidence_anchor_ids),
        open_issue_ids=list(cand.open_issue_ids),
        placeholders=[p.model_dump() for p in result.output.placeholders],
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


def _suggestion_view(db, run, suggestion, *, evidence: list | None = None,
                     warnings: list | None = None) -> dict:
    """Operation-Result-View + typisiertes AIProposal (R5.2, additiv).

    Reused-Pfad: warnings fallen auf die Placeholder-Heuristik zurück (kein
    ctx verfügbar) — das AIProposal übernimmt dieselben safety_notes.
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
    return {
        "suggestion_id": suggestion.suggestion_id,
        "operation_id": suggestion.operation_id,
        "field_id": suggestion.field_id,
        "base_version_id": suggestion.base_version_id,
        "suggested_text": suggestion.suggested_text,
        "rationale": suggestion.rationale,
        "evidence": used,
        "open_issue_ids": list(suggestion.open_issue_ids or []),
        "placeholders": list(suggestion.placeholders or []),
        "character_count": suggestion.character_count,
        "character_limit": config.char_limit if config else None,
        "warnings": warn,
        # mode="json": datetime → ISO-String für die AsyncOperation-JSON-Spalte.
        "ai_proposal": proposal.model_dump(mode="json"),
    }
