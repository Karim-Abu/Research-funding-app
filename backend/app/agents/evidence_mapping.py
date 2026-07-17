"""A1 Evidence Candidate Mapping orchestrator (Milestone 9C).

Activates ``A1.evidence_candidate_mapping`` inside the ``extract_facts_and_map_evidence``
run stage: assemble controlled context (ExtractedFacts + requirements + fields + frozen
fragments), call A1 through the ModelGateway, validate each proposed candidate against the
RunSourceSnapshot, and persist advisory **agent-origin EvidenceCandidates**. The existing
deterministic M5 pipeline then verifies (the only source of ``exact_verified``) and links
them. Never raises; the deterministic baseline always continues. A1 never sets a
verification status, creates ``human_verified``, or changes a RequirementAssessment.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import context as a1_context
from app.agents import data_policy, gateway
from app.agents.prompt_assets import prompt_version_for
from app.agents.schemas import (
    SchemaNotImplementedError,
    ValidationError,
    validate_payload,
)
from app.config.settings import get_settings
from app.db.models import (
    AgentInvocation,
    AnalysisRun,
    OpenIssue,
    SourceVersion,
)
from app.evidence.discovery import quote_hash as compute_quote_hash
from app.registry.loader import get_registry
from app.repositories import agent_proposals, audit, controls
from app.repositories import evidence as evidence_repo
from app.runs.cloud_policy import real_eval_confirmed

logger = logging.getLogger("app.agents.evidence_mapping")

PROFILE_ID = "A1.evidence_candidate_mapping"
OUTPUT_SCHEMA = "EvidenceCandidateMappingResult@v1"
INPUT_SCHEMA = "EvidenceCandidateMappingInput@v1"
_NO_CALL_MODES = ("deterministic_only", "local_only")

# Module-level resolver (real dormant adapters by default; tests monkeypatch).
_PROVIDER_RESOLVER = gateway.default_provider_resolver


def _default_resolver():
    """Wie A2/A3: mit ``agent_fake_provider`` liefert der Default einen
    deterministischen Fake (leeres, schema-gültiges Ergebnis) — CI/E2E machen
    nie echte Provider-Calls, auch wenn API-Keys gesetzt sind."""
    settings = get_settings()
    if settings.agent_fake_provider and settings.ai_eval_mode != "real":
        import json

        from app.agents.providers import FakeProvider

        payload = {"candidates": [], "unmapped_targets": [], "conflicts": []}
        return lambda _route: FakeProvider(raw_output=json.dumps(payload))
    return _PROVIDER_RESOLVER


@dataclass
class A1MappingOutcome:
    status: str  # reused | skipped | blocked | succeeded | failed
    reason: str = ""
    invocation_id: str | None = None
    candidates_persisted: int = 0
    candidates_deduplicated: int = 0
    candidates_rejected: int = 0


def _audit(db: Session, run: AnalysisRun, action: str, detail: dict | None = None) -> None:
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None, action=action,
        target_type="analysis_run", target_id=run.run_id, detail=detail,
    )


def _classification(run: AnalysisRun) -> dict:
    return dict(run.effective_data_classification or {})


def run_a1_evidence_mapping(
    db: Session, run: AnalysisRun, *, provider_resolver=None
) -> A1MappingOutcome:
    """Run A1 evidence mapping safely. Always returns; never raises into the graph."""
    try:
        return _run(db, run, provider_resolver or _default_resolver())
    except Exception:  # defensive: A1 must never break the run
        logger.exception("A1 evidence mapping crashed; continuing run %s", run.run_id)
        _audit(db, run, "agent.evidence_mapping.failed", {"reason": "internal_error"})
        return A1MappingOutcome(status="failed", reason="internal_error")


def _has_succeeded_invocation(db: Session, run_id: str) -> bool:
    return db.scalar(
        select(AgentInvocation.invocation_id).where(
            AgentInvocation.run_id == run_id,
            AgentInvocation.profile_id == PROFILE_ID,
            AgentInvocation.status == "succeeded",
        )
    ) is not None


def _run(db: Session, run: AnalysisRun, resolver) -> A1MappingOutcome:
    # 0. Replay-idempotency guard — a prior succeeded invocation means this stage
    #    already ran (checkpoint replay / repeated execution). Do not call the
    #    provider again; this is NOT a new CostGuard call.
    if _has_succeeded_invocation(db, run.run_id):
        _audit(db, run, "agent.evidence_mapping.reused", {"profile_id": PROFILE_ID})
        return A1MappingOutcome(status="reused", reason="already_succeeded")

    _audit(db, run, "agent.evidence_mapping.requested", {"profile_id": PROFILE_ID})
    registry = gateway.get_agent_registry()
    profile = registry.profile(PROFILE_ID)
    settings = get_settings()
    mode = run.processing_mode
    confirmed = real_eval_confirmed(run)

    # 1. Mode gate.
    if mode in _NO_CALL_MODES:
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            control_id="CTRL.DATA_POLICY", status="blocked",
            detail=f"processing_mode_{mode}", run_id=run.run_id,
        )
        _audit(db, run, "agent.evidence_mapping.skipped", {"reason": f"mode_{mode}"})
        return A1MappingOutcome(status="skipped", reason=f"mode_{mode}")

    # 2. Data Policy gate (before context assembly).
    decision = data_policy.evaluate(
        profile=profile, classification=_classification(run),
        processing_mode=mode, settings=settings, run_confirmation=confirmed,
    )
    if decision.blocked:
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            control_id="CTRL.DATA_POLICY", status="blocked", detail=decision.reason,
            run_id=run.run_id,
        )
        _audit(db, run, "agent.evidence_mapping.blocked", {"reason": decision.reason})
        return A1MappingOutcome(status="blocked", reason=decision.reason)

    # 3. Assemble context + validate input payload.
    max_fragments = int(profile.invocation_limits.get("max_input_fragments", 80))
    ctx = a1_context.assemble_evidence_mapping_context(db, run, max_fragments=max_fragments)
    input_payload = {
        "run_id": run.run_id,
        "facts": [{"fact_id": f["fact_id"], "statement": f["statement"]}
                  for f in ctx.extracted_facts],
        "fragment_ids": ctx.selected_fragment_ids,
        "target_requirement_ids": [d["requirement_id"] for d in ctx.requirement_defs],
        "target_field_ids": [d["field_id"] for d in ctx.field_defs],
    }
    try:
        validate_payload(INPUT_SCHEMA, input_payload)
    except (ValidationError, SchemaNotImplementedError):
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            control_id="CTRL.INPUT_SCHEMA", status="failed",
            detail="evidence_mapping_input_schema_invalid",
            run_id=run.run_id,
        )
        _audit(db, run, "agent.evidence_mapping.skipped", {"reason": "input_schema"})
        return A1MappingOutcome(status="skipped", reason="input_schema")

    _audit(db, run, "agent.evidence_mapping.started", {"profile_id": PROFILE_ID})

    # 4. Invoke A1 through the ModelGateway.
    request = gateway.ModelRequest(
        profile_id=PROFILE_ID, workspace_id=run.workspace_id, input_payload=input_payload,
        classification=_classification(run), processing_mode=mode, run_id=run.run_id,
        project_id=run.project_id,
        allowed_fragment_ids=frozenset(ctx.selected_fragment_ids),
        run_confirmation=confirmed,
        prompt_version=prompt_version_for(PROFILE_ID), context_text=ctx.context_text,
        context_hash=ctx.context_hash, context_meta=ctx.meta,
        skill_id="a1.evidence_candidate_mapping",
        input_artifact_refs=(
            {
                "kind": "run_source_snapshot",
                "run_id": run.run_id,
                "fragment_ids": ctx.selected_fragment_ids,
                "context_hash": ctx.context_hash,
            },
        ),
    )
    result = gateway.invoke(db, request, provider_resolver=resolver, registry=registry)

    for control_id, detail in (
        ("CTRL.TOOL_AUTHORIZATION", "a1_tools_authorized"),
        ("CTRL.INPUT_SCHEMA", "input_validated"),
        ("CTRL.EVIDENCE_REQUIREMENT", "agent_candidates_advisory"),
    ):
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            control_id=control_id, status="passed", detail=detail, run_id=run.run_id,
            agent_invocation_id=result.invocation_id,
        )

    if isinstance(result, gateway.SafeFailure):
        return _handle_failure(db, run, result)
    return _persist(db, run, result, ctx)


# --- failure handling (issue discipline, corr #3) --------------------------

# Not a genuine failure → internal-only, no OpenIssue.
_NON_ISSUE_DETAILS = ("provider_unavailable",)


def _handle_failure(db: Session, run: AnalysisRun, failure) -> A1MappingOutcome:
    if failure.status == "blocked":
        _audit(db, run, "agent.evidence_mapping.blocked", {"reason": failure.error_code})
        return A1MappingOutcome(status="blocked", reason=failure.error_code,
                                invocation_id=failure.invocation_id)
    if failure.safe_detail in _NON_ISSUE_DETAILS:
        _audit(db, run, "agent.evidence_mapping.skipped", {"reason": failure.safe_detail})
        return A1MappingOutcome(status="skipped", reason=failure.safe_detail,
                                invocation_id=failure.invocation_id)
    # Genuine unexpected failure: provider error after fallback, timeout, or schema
    # failure after retry → one idempotent info OpenIssue; targets left unanchored.
    _audit(db, run, "agent.evidence_mapping.failed", {"reason": failure.error_code})
    _open_issue(db, run, failure.invocation_id)
    return A1MappingOutcome(status="failed", reason=failure.error_code,
                            invocation_id=failure.invocation_id)


def _open_issue(db: Session, run: AnalysisRun, invocation_id: str | None) -> None:
    if not invocation_id:
        return
    existing = db.scalar(
        select(OpenIssue).where(
            OpenIssue.run_id == run.run_id,
            OpenIssue.target_type == "agent_invocation",
            OpenIssue.target_id == invocation_id,
        )
    )
    if existing is not None:
        return
    db.add(
        OpenIssue(
            issue_id=str(uuid.uuid4()), run_id=run.run_id,
            issue_type="ai_evidence_mapping_unavailable", severity="info",
            description=(
                "AI evidence mapping was unavailable for this run; deterministic "
                "evidence verification completed normally and is unaffected."
            ),
            target_type="agent_invocation", target_id=invocation_id,
            recommended_next_action="No action required. Optionally re-run the analysis.",
            status="open",
        )
    )
    db.flush()


# --- success: validate candidates + persist (partial) ----------------------


@dataclass
class _Counters:
    persisted: int = 0
    deduplicated: int = 0
    rejected: int = 0


def _candidate_reason(cand, requirement_ids, blocks, fact_ids, per_target_count):
    """Return (rejection_reason | None, block | None). Pure validation — no writes."""
    if cand.target_type != "requirement":
        return "non_requirement_target", None
    if cand.target_id not in requirement_ids:
        return "unknown_requirement", None
    block = blocks.get(cand.fragment_id)
    if block is None:
        return "fragment_out_of_snapshot", None
    if cand.extracted_fact_id is not None and cand.extracted_fact_id not in fact_ids:
        return "unknown_extracted_fact", block
    if cand.match_type != "exact_normalized":
        return "unsupported_match_type", block
    occurrences = block.text.count(cand.quote)
    if occurrences == 0:
        return "quote_not_in_fragment", block
    if occurrences > 1:  # span cannot be derived unambiguously
        return "ambiguous_quote_position", block
    if per_target_count.get(cand.target_id, 0) >= 5:  # max_candidates_per_target
        return "max_candidates_per_target", block
    return None, block


def _persist(db: Session, run: AnalysisRun, response, ctx) -> A1MappingOutcome:
    registry = get_registry()
    requirement_ids = set(registry.requirements.keys())
    blocks = {b.fragment_id: b for b in ctx.fragment_blocks}
    fact_ids = {f["fact_id"] for f in ctx.extracted_facts}
    invocation_id = response.invocation_id
    prompt_version = prompt_version_for(PROFILE_ID)
    per_target_count: dict[str, int] = {}
    c = _Counters()

    for cand in response.output.candidates:
        reason, block = _candidate_reason(
            cand, requirement_ids, blocks, fact_ids, per_target_count
        )
        if reason is not None:
            c.rejected += 1
            agent_proposals.record(
                db, run, agent_invocation_id=invocation_id, profile_id=PROFILE_ID,
                prompt_version=prompt_version, outcome="rejected", rejection_reason=reason,
                target_requirement_id=cand.target_id, fragment_id=cand.fragment_id,
            )
            _audit(db, run, "evidence_mapping.candidate_rejected", {"reason": reason})
            continue
        per_target_count[cand.target_id] = per_target_count.get(cand.target_id, 0) + 1
        _store_candidate(db, run, cand, block, invocation_id, prompt_version, c)

    _audit(db, run, "agent.evidence_mapping.succeeded",
           {"persisted": c.persisted, "deduplicated": c.deduplicated,
            "rejected": c.rejected, "unmapped": len(response.output.unmapped_targets)})
    return A1MappingOutcome(
        status="succeeded", invocation_id=invocation_id,
        candidates_persisted=c.persisted, candidates_deduplicated=c.deduplicated,
        candidates_rejected=c.rejected,
    )


def _store_candidate(db, run, cand, block, invocation_id, prompt_version, c: _Counters):
    start = block.text.find(cand.quote)
    qhash = compute_quote_hash(cand.quote)
    spec = evidence_repo.AgentCandidateSpec(
        target_requirement_id=cand.target_id, fragment_id=cand.fragment_id,
        source_version_id=block.source_version_id,
        source_id=_source_id_for_version(db, block.source_version_id),
        proposed_quote=cand.quote, quote_hash=qhash,
        span_start_in_fragment=start, span_end_in_fragment=start + len(cand.quote),
        agent_invocation_id=invocation_id, profile_id=PROFILE_ID,
        prompt_version=prompt_version, source_extracted_fact_id=cand.extracted_fact_id,
    )
    candidate, created = evidence_repo.upsert_agent_candidate(db, run, spec)
    if created:
        c.persisted += 1
        agent_proposals.record(
            db, run, agent_invocation_id=invocation_id, profile_id=PROFILE_ID,
            prompt_version=prompt_version, outcome="persisted_new",
            target_requirement_id=cand.target_id, fragment_id=cand.fragment_id,
            quote_hash=qhash, candidate_id=candidate.candidate_id,
        )
        _audit(db, run, "evidence_mapping.candidate_persisted",
               {"requirement_id": cand.target_id})
    else:
        c.deduplicated += 1
        agent_proposals.record(
            db, run, agent_invocation_id=invocation_id, profile_id=PROFILE_ID,
            prompt_version=prompt_version, outcome="deduplicated",
            target_requirement_id=cand.target_id, fragment_id=cand.fragment_id,
            quote_hash=qhash, candidate_id=candidate.candidate_id,
            existing_candidate_id=candidate.candidate_id,
            duplicate_of_deterministic=(
                candidate.generation_origin == "deterministic_lexical"
            ),
            duplicate_reason="same_run_target_fragment_quote",
        )
        _audit(db, run, "evidence_mapping.candidate_deduplicated",
               {"requirement_id": cand.target_id})


def _source_id_for_version(db: Session, source_version_id: str) -> str:
    version = db.get(SourceVersion, source_version_id)
    return version.source_document_id if version is not None else ""


def backfill_agent_evaluation(db: Session, run: AnalysisRun) -> int:
    """After verify + link stages, complete the evaluation trail (corr #4)."""
    return agent_proposals.backfill_outcomes(db, run)
