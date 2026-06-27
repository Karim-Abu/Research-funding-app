"""A1 Project Fact Extraction orchestrator (Milestone 9B).

The single entrypoint that activates ``A1.project_fact_extraction`` inside the
``extract_facts_and_map_evidence`` run stage: assemble controlled context from the
immutable RunSourceSnapshot, call A1 through the ModelGateway, validate provenance
and persist advisory ExtractedFacts (proposed / conflicted / missing). Never
raises — the deterministic pipeline always continues. A1 output is advisory only;
it never confirms facts, changes RequirementAssessments, verifies evidence or
satisfies hard rules.
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
from app.db.models import AnalysisRun, OpenIssue
from app.registry.loader import get_registry
from app.repositories import audit, controls
from app.repositories import extracted_facts as facts_repo

logger = logging.getLogger("app.agents.fact_extraction")

PROFILE_ID = "A1.project_fact_extraction"
OUTPUT_SCHEMA = "ProjectFactExtractionResult@v1"
INPUT_SCHEMA = "ProjectFactExtractionInput@v1"
_NO_CALL_MODES = ("deterministic_only", "local_only")

# Module-level resolver so the graph uses the real (dormant) adapters by default;
# tests monkeypatch this to inject the fake provider.
_PROVIDER_RESOLVER = gateway.default_provider_resolver


@dataclass
class A1Outcome:
    status: str  # skipped | blocked | succeeded | failed
    reason: str = ""
    invocation_id: str | None = None
    facts_persisted: int = 0
    facts_rejected: int = 0


def _audit(db: Session, run: AnalysisRun, action: str, detail: dict | None = None) -> None:
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None, action=action,
        target_type="analysis_run", target_id=run.run_id, detail=detail,
    )


def _skip_control(db: Session, run: AnalysisRun, status: str, reason: str) -> None:
    controls.record(
        db, workspace_id=run.workspace_id, project_id=run.project_id,
        control_id="CTRL.DATA_POLICY", status=status, detail=reason[:200],
        run_id=run.run_id,
    )


def _classification(run: AnalysisRun) -> dict:
    return dict(run.effective_data_classification or {})


def run_a1_fact_extraction(
    db: Session, run: AnalysisRun, *, provider_resolver=None
) -> A1Outcome:
    """Run A1 safely. Always returns; never raises into the graph."""
    try:
        return _run(db, run, provider_resolver or _PROVIDER_RESOLVER)
    except Exception:  # defensive: A1 must never break the run
        logger.exception("A1 fact extraction crashed; continuing run %s", run.run_id)
        _audit(db, run, "agent.fact_extraction.failed", {"reason": "internal_error"})
        return A1Outcome(status="failed", reason="internal_error")


def _run(db: Session, run: AnalysisRun, resolver) -> A1Outcome:
    _audit(db, run, "agent.fact_extraction.requested", {"profile_id": PROFILE_ID})
    registry = gateway.get_agent_registry()
    profile = registry.profile(PROFILE_ID)
    settings = get_settings()
    mode = run.processing_mode

    # 1. Mode gate — deterministic_only / local_only never call a provider.
    if mode in _NO_CALL_MODES:
        _skip_control(db, run, "blocked", f"processing_mode_{mode}")
        _audit(db, run, "agent.fact_extraction.skipped", {"reason": f"mode_{mode}"})
        return A1Outcome(status="skipped", reason=f"mode_{mode}")

    # 2. Data Policy gate (before context assembly — no blocked payload built).
    decision = data_policy.evaluate(
        profile=profile, classification=_classification(run),
        processing_mode=mode, settings=settings, run_confirmation=False,
    )
    if decision.blocked:
        _skip_control(db, run, "blocked", decision.reason)
        _audit(db, run, "agent.fact_extraction.blocked", {"reason": decision.reason})
        return A1Outcome(status="blocked", reason=decision.reason)

    # 3. Assemble controlled context + validate the input payload.
    max_fragments = int(profile.invocation_limits.get("max_input_fragments", 80))
    ctx = a1_context.assemble_a1_context(db, run, max_fragments=max_fragments)
    input_payload = {
        "run_id": run.run_id,
        "fragment_ids": ctx.selected_fragment_ids,
        "active_requirement_ids": [d["requirement_id"] for d in ctx.requirement_defs],
        "active_field_ids": [d["field_id"] for d in ctx.field_defs],
        "data_classification": _input_classification(run, mode),
    }
    try:
        validate_payload(INPUT_SCHEMA, input_payload)
    except (ValidationError, SchemaNotImplementedError) as exc:
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            control_id="CTRL.INPUT_SCHEMA", status="failed",
            detail=str(exc)[:200], run_id=run.run_id,
        )
        _audit(db, run, "agent.fact_extraction.skipped", {"reason": "input_schema"})
        return A1Outcome(status="skipped", reason="input_schema")

    _audit(db, run, "agent.fact_extraction.started", {"profile_id": PROFILE_ID})

    # 4. Invoke A1 through the ModelGateway.
    request = gateway.ModelRequest(
        profile_id=PROFILE_ID,
        workspace_id=run.workspace_id,
        input_payload=input_payload,
        classification=_classification(run),
        processing_mode=mode,
        run_id=run.run_id,
        project_id=run.project_id,
        allowed_fragment_ids=frozenset(ctx.selected_fragment_ids),
        run_confirmation=False,
        prompt_version=prompt_version_for(PROFILE_ID),
        context_text=ctx.context_text,
        context_hash=ctx.context_hash,
        context_meta=ctx.meta,
    )
    result = gateway.invoke(db, request, provider_resolver=resolver, registry=registry)

    # Record the two orchestrator-side controls now linked to the invocation.
    _link_control(db, run, result.invocation_id, "CTRL.TOOL_AUTHORIZATION", "passed",
                  "a1_tools_authorized")
    _link_control(db, run, result.invocation_id, "CTRL.INPUT_SCHEMA", "passed",
                  "input_validated")

    if isinstance(result, gateway.SafeFailure):
        return _handle_failure(db, run, result)
    return _persist(db, run, result, ctx)


def _input_classification(run: AnalysisRun, mode: str) -> dict:
    cls = _classification(run)
    return {
        "sensitivity": cls.get("sensitivity", "confidential"),
        "origin": cls.get("origin", "real_project"),
        "processing_mode": mode,
    }


def _link_control(db, run, invocation_id, control_id, status, detail) -> None:
    controls.record(
        db, workspace_id=run.workspace_id, project_id=run.project_id,
        control_id=control_id, status=status, detail=detail, run_id=run.run_id,
        agent_invocation_id=invocation_id,
    )


# --- failure handling ------------------------------------------------------

# safe_detail values that are not "genuine failures" → no OpenIssue.
_NON_ISSUE_DETAILS = ("provider_unavailable",)


def _handle_failure(db: Session, run: AnalysisRun, failure) -> A1Outcome:
    if failure.status == "blocked":
        _audit(db, run, "agent.fact_extraction.blocked",
               {"reason": failure.error_code})
        return A1Outcome(status="blocked", reason=failure.error_code,
                         invocation_id=failure.invocation_id)

    if failure.safe_detail in _NON_ISSUE_DETAILS:
        # e.g. no provider key configured — internal-only, non-alarming.
        _audit(db, run, "agent.fact_extraction.skipped",
               {"reason": failure.safe_detail})
        return A1Outcome(status="skipped", reason=failure.safe_detail,
                         invocation_id=failure.invocation_id)

    # Genuine failure (schema-fail-after-retry / provider error / timeout):
    # info-severity OpenIssue targeting the agent invocation, then continue.
    _audit(db, run, "agent.fact_extraction.failed", {"reason": failure.error_code})
    _open_issue(db, run, failure.invocation_id)
    return A1Outcome(status="failed", reason=failure.error_code,
                     invocation_id=failure.invocation_id)


def _open_issue(db: Session, run: AnalysisRun, invocation_id: str | None) -> None:
    if not invocation_id:
        return  # no invocation row → record via audit/control only
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
            issue_id=str(uuid.uuid4()),
            run_id=run.run_id,
            issue_type="ai_extraction_unavailable",
            severity="info",
            description=(
                "AI fact extraction was unavailable for this run; the deterministic "
                "analysis completed normally and is unaffected."
            ),
            target_type="agent_invocation",
            target_id=invocation_id,
            recommended_next_action=(
                "No action required. Optionally re-run the analysis later."
            ),
            status="open",
        )
    )
    db.flush()


# --- success: validate provenance + persist (partial) ----------------------


def _persist(db: Session, run: AnalysisRun, response, ctx) -> A1Outcome:
    registry = get_registry()
    requirement_ids = set(registry.requirements.keys())
    field_ids = set(registry.portal_fields.keys())
    version_by_fragment = {b.fragment_id: b.source_version_id for b in ctx.fragment_blocks}
    result = response.output

    persisted = rejected = 0

    def reject(reason: str, statement: str) -> None:
        nonlocal rejected
        rejected += 1
        _audit(db, run, "extracted_fact.rejected",
               {"reason": reason, "statement_hash": facts_repo.fact_fingerprint(
                   run_id=run.run_id, fact_type="x", status="rejected",
                   value=statement, fragment_ids=[])})

    # Facts → proposed. (References are already snapshot-valid via the gateway.)
    for fact in result.facts:
        requirement_id, field_id, ok = _resolve_target(
            fact.target_ref, requirement_ids, field_ids
        )
        if not ok:
            reject("unresolvable_target", fact.statement)
            continue
        version_ids = sorted({
            version_by_fragment[f] for f in fact.source_fragment_ids
            if f in version_by_fragment
        })
        created = _store(
            db, run, response, status="proposed",
            fact_type=fact.fact_type or "project_fact",
            normalized_value=fact.normalized_value,
            statement=fact.statement, requirement_id=requirement_id, field_id=field_id,
            fragment_ids=fact.source_fragment_ids, version_ids=version_ids,
        )
        persisted += int(created)

    # Conflicts → conflicted.
    fragments_by_fact = {f.fact_id: f.source_fragment_ids for f in result.facts}
    for conflict in result.conflicts:
        frags = sorted({
            f for fid in conflict.fact_ids for f in fragments_by_fact.get(fid, [])
        })
        version_ids = sorted({
            version_by_fragment[f] for f in frags if f in version_by_fragment
        })
        created = _store(
            db, run, response, status="conflicted", fact_type="conflict",
            normalized_value=None, statement=conflict.description,
            requirement_id=None, field_id=None, fragment_ids=frags,
            version_ids=version_ids,
        )
        persisted += int(created)

    # Missing information → missing (no provenance required).
    for missing in result.missing_information:
        requirement_id, field_id, ok = _resolve_target(
            missing.target_ref, requirement_ids, field_ids
        )
        if not ok:
            reject("unresolvable_target", missing.description)
            continue
        created = _store(
            db, run, response, status="missing", fact_type="missing",
            normalized_value=None, statement=missing.description,
            requirement_id=requirement_id, field_id=field_id,
            fragment_ids=[], version_ids=[],
        )
        persisted += int(created)

    if rejected:
        _link_control(db, run, response.invocation_id, "CTRL.OUTPUT_SCHEMA",
                      "warning", f"rejected_facts:{rejected}")
    _audit(db, run, "agent.fact_extraction.succeeded",
           {"persisted": persisted, "rejected": rejected,
            "context": ctx.meta.get("selected_fragment_count")})
    return A1Outcome(status="succeeded", invocation_id=response.invocation_id,
                     facts_persisted=persisted, facts_rejected=rejected)


def _resolve_target(
    target_ref: str | None, requirement_ids: set[str], field_ids: set[str]
) -> tuple[str | None, str | None, bool]:
    """(requirement_id, field_id, ok). A non-null target must resolve to a known
    requirement or field, else the fact is rejected (ok=False)."""
    if target_ref is None:
        return None, None, True
    if target_ref in requirement_ids:
        return target_ref, None, True
    if target_ref in field_ids:
        return None, target_ref, True
    return None, None, False


def _store(
    db, run, response, *, status, fact_type, normalized_value, statement,
    requirement_id, field_id, fragment_ids, version_ids,
) -> bool:
    _, created = facts_repo.upsert(
        db, run_id=run.run_id, workspace_id=run.workspace_id, fact_type=fact_type,
        normalized_value=normalized_value, original_statement=statement, status=status,
        requirement_id=requirement_id, field_id=field_id,
        source_fragment_ids=list(fragment_ids), source_version_ids=list(version_ids),
        profile_id=PROFILE_ID, model_route=response.provider,
        model_id=response.model_id, schema_version=OUTPUT_SCHEMA,
        prompt_version=prompt_version_for(PROFILE_ID),
        agent_invocation_id=response.invocation_id,
    )
    if created:
        _audit(db, run, "extracted_fact.persisted",
               {"status": status, "fact_type": fact_type})
    return created
