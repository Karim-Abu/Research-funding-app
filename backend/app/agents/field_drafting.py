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

from sqlalchemy.orm import Session

from app.agents import data_policy, gateway
from app.agents import field_drafting_context as a2_context
from app.agents.prompt_assets import prompt_version_for
from app.agents.schemas import (
    SchemaNotImplementedError,
    ValidationError,
    validate_payload,
)
from app.config.settings import get_settings
from app.db.models import AnalysisRun
from app.drafts.charcount import char_count, within_limit
from app.repositories import audit, controls
from app.repositories import draft_suggestions as suggestions_repo

logger = logging.getLogger("app.agents.field_drafting")

PROFILE_ID = "A2.solution_innovation"
FIELD_ID = "SOL.INNOVATION_SOLUTION.EDITOR"
INPUT_SCHEMA = "FieldDraftingInput@v1"
OUTPUT_SCHEMA = "PortalFieldDraftBundle@v1"
CHAR_LIMIT = 25000
_MANDATORY_MARKERS = ("4.1", "4.2", "4.3", "4.4", "4.5")
_NO_CALL_MODES = ("deterministic_only", "local_only")

_PROVIDER_RESOLVER = gateway.default_provider_resolver

# Deterministic fake A2 output for dev/test (settings.agent_fake_provider). Valid
# bundle: preserves 4.1-4.5, cites no evidence (evidence is optional).
_FAKE_SUGGESTED_TEXT = (
    "4.1 Stand der Technik: bestehende Verfahren und deren Grenzen.\n"
    "4.2 Neuheit: klare Abgrenzung gegenüber dem Stand der Technik.\n"
    "4.3 Ziele: messbare Ziele mit Baseline und Zielwert, wo belegbar.\n"
    "4.4 Vorarbeiten: abgeschlossene Vorstudien getrennt von geplanter Arbeit.\n"
    "4.5 Partner: geeignete Kompetenzen und Infrastruktur der Partner."
)


def _default_resolver():
    """Real adapters by default; a deterministic fake when the dev/test flag is set."""
    if get_settings().agent_fake_provider:
        import json

        from app.agents.providers import FakeProvider

        bundle = {
            "draft_candidates": [{
                "field_id": FIELD_ID, "suggested_text": _FAKE_SUGGESTED_TEXT,
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


def _audit(db: Session, run: AnalysisRun, action: str, detail: dict | None = None) -> None:
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None, action=action,
        target_type="portal_field_draft", target_id=FIELD_ID, detail=detail,
    )


def _classification(run: AnalysisRun) -> dict:
    return dict(run.effective_data_classification or {})


def availability(run: AnalysisRun) -> tuple[bool, str]:
    """Per-run availability for createRedraft's 503 pre-check. Reads the run's
    existing processing mode + classification — NEVER upgrades the mode."""
    mode = run.processing_mode
    if mode in _NO_CALL_MODES:
        return False, f"processing_mode_{mode}"
    registry = gateway.get_agent_registry()
    decision = data_policy.evaluate(
        profile=registry.profile(PROFILE_ID), classification=_classification(run),
        processing_mode=mode, settings=get_settings(), run_confirmation=False,
    )
    if decision.blocked:
        return False, decision.reason
    return True, "available"


def _mandatory_structure_ok(text: str) -> bool:
    # Semantic check: all five mandatory questions represented by section number
    # (4.1-4.5), not brittle byte-identical labels.
    return all(marker in text for marker in _MANDATORY_MARKERS)


@dataclass
class _Validated:
    candidate: object
    warnings: list = field(default_factory=list)


def _validate_candidate(bundle, ctx) -> tuple[_Validated | None, str]:
    candidates = [c for c in bundle.draft_candidates if c.field_id == FIELD_ID]
    if not candidates:
        return None, "no_candidate_for_field"
    cand = candidates[0]
    if not cand.suggested_text.strip():
        return None, "empty_suggested_text"
    if not within_limit(cand.suggested_text, CHAR_LIMIT):  # strict, never trimmed
        return None, "character_limit_exceeded"
    if not _mandatory_structure_ok(cand.suggested_text):
        return None, "mandatory_structure_missing"
    bad_anchor = next(
        (a for a in cand.evidence_anchor_ids if a not in ctx.allowed_anchor_ids), None
    )
    if bad_anchor is not None:
        return None, "unknown_evidence_anchor"
    bad_issue = next(
        (i for i in cand.open_issue_ids if i not in ctx.allowed_issue_ids), None
    )
    if bad_issue is not None:
        return None, "unknown_open_issue"
    warnings = []
    if bundle.placeholders:
        warnings.append("contains_placeholders")
    if ctx.confirmed_facts:
        warnings.append("based_on_unconfirmed_facts")
    return _Validated(candidate=cand, warnings=warnings), ""


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
    """Generate + validate + persist an advisory A2 suggestion. Never raises."""
    try:
        return _run(
            db, run, draft_id=draft_id, base_version_id=base_version_id,
            operation_id=operation_id, guidance=guidance,
            resolver=provider_resolver or _default_resolver(),
        )
    except Exception:  # defensive: A2 must never break the request/run
        logger.exception("A2 field drafting crashed; run %s", run.run_id)
        _audit(db, run, "agent.field_drafting.failed", {"reason": "internal_error"})
        return A2Outcome(status="failed", reason="internal_error")


def _run(db, run, *, draft_id, base_version_id, operation_id, guidance, resolver) -> A2Outcome:
    # Replay/idempotency: reuse an existing proposed suggestion for this base.
    existing = suggestions_repo.get_proposed_for(db, run.run_id, draft_id, base_version_id)
    if existing is not None:
        return A2Outcome(status="reused", suggestion_id=existing.suggestion_id,
                         view=_suggestion_view(existing))

    mode = run.processing_mode
    if mode in _NO_CALL_MODES:
        _audit(db, run, "agent.field_drafting.skipped", {"reason": f"mode_{mode}"})
        return A2Outcome(status="skipped", reason=f"mode_{mode}")

    _audit(db, run, "agent.field_drafting.started", {"profile_id": PROFILE_ID})
    ctx = a2_context.assemble_a2_context(db, run)
    input_payload = a2_context.build_input_payload(ctx, run.run_id)
    try:
        validate_payload(INPUT_SCHEMA, input_payload)
    except (ValidationError, SchemaNotImplementedError) as exc:
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            control_id="CTRL.INPUT_SCHEMA", status="failed", detail=str(exc)[:200],
            run_id=run.run_id,
        )
        _audit(db, run, "agent.field_drafting.skipped", {"reason": "input_schema"})
        return A2Outcome(status="skipped", reason="input_schema")

    request = gateway.ModelRequest(
        profile_id=PROFILE_ID, workspace_id=run.workspace_id, input_payload=input_payload,
        classification=_classification(run), processing_mode=mode, run_id=run.run_id,
        project_id=run.project_id, run_confirmation=False,
        prompt_version=prompt_version_for(PROFILE_ID), context_text=ctx.context_text,
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
        _audit(db, run, "agent.field_drafting.failed", {"reason": result.error_code})
        return A2Outcome(status=result.status, reason=result.error_code,
                         invocation_id=result.invocation_id)

    validated, reason = _validate_candidate(result.output, ctx)
    if validated is None:
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            control_id="CTRL.OUTPUT_SCHEMA", status="failed", detail=reason,
            run_id=run.run_id, agent_invocation_id=result.invocation_id,
        )
        _audit(db, run, "agent.field_drafting.failed", {"reason": reason})
        return A2Outcome(status="failed", reason=reason,
                         invocation_id=result.invocation_id)

    cand = validated.candidate
    suggestion = suggestions_repo.create(
        db, run, draft_id=draft_id, base_version_id=base_version_id, field_id=FIELD_ID,
        profile_id=PROFILE_ID, operation_id=operation_id,
        agent_invocation_id=result.invocation_id,
        prompt_version=prompt_version_for(PROFILE_ID), model_route=result.provider,
        model_id=result.model_id, suggested_text=cand.suggested_text,
        rationale=cand.rationale,
        evidence_anchor_ids=list(cand.evidence_anchor_ids),
        open_issue_ids=list(cand.open_issue_ids),
        placeholders=[p.model_dump() for p in result.output.placeholders],
        character_count=char_count(cand.suggested_text),
    )
    _audit(db, run, "agent.field_drafting.succeeded",
           {"suggestion_id": suggestion.suggestion_id,
            "character_count": suggestion.character_count})
    return A2Outcome(
        status="succeeded", suggestion_id=suggestion.suggestion_id,
        invocation_id=result.invocation_id,
        view=_suggestion_view(suggestion, evidence=ctx.verified_evidence,
                              warnings=validated.warnings),
    )


def _suggestion_view(suggestion, *, evidence: list | None = None, warnings: list | None = None) -> dict:
    anchor_ids = set(suggestion.evidence_anchor_ids or [])
    used = [e for e in (evidence or []) if e["anchor_id"] in anchor_ids]
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
        "character_limit": CHAR_LIMIT,
        "warnings": warnings if warnings is not None else (
            ["contains_placeholders"] if suggestion.placeholders else []
        ),
    }
