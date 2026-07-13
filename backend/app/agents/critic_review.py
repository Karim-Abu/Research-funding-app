"""A3 evidence-consistency orchestrator (Milestone 9G).

Runs A3.evidence_consistency through the ModelGateway to produce **advisory**
ReviewFinding records for the scoped fields (SOL + VC). Never raises, never mutates
drafts/requirements/evidence/approvals. Eligibility mirrors the M9E cloud gate
(cloud_assisted + public/synthetic + provider/fake available). A skipped/failed run
preserves prior A3 findings (the caller only applies findings on a successful,
schema-valid bundle).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.agents import critic_review_context as a3_context
from app.agents import data_policy, gateway
from app.agents import a3_review, field_drafting
from app.agents.a3_review import A3_PROFILE_ID
from app.agents.field_drafting import real_eval_confirmed
from app.agents.prompt_assets import prompt_version_for
from app.agents.schemas import SchemaNotImplementedError, ValidationError, validate_payload
from app.config.settings import get_settings
from app.db.models import AnalysisRun
from app.repositories import audit, controls

logger = logging.getLogger("app.agents.critic_review")

INPUT_SCHEMA = "CriticReviewInput@v1"
_NO_CALL_MODES = ("deterministic_only", "local_only")
_PROVIDER_RESOLVER = gateway.default_provider_resolver


@dataclass
class A3Finding:
    origin_profile_id: str
    severity: str
    status: str
    description: str
    field_id: str | None = None
    target_section: str | None = None
    requirement_id: str | None = None
    evidence_anchor_id: str | None = None
    evidence_link_id: str | None = None
    suggested_improvement: str | None = None
    recommended_next_action: str | None = None


@dataclass
class A3Outcome:
    status: str  # succeeded | skipped | blocked | failed
    reason: str = ""
    findings: list[A3Finding] = field(default_factory=list)
    invocation_id: str | None = None


def _classification(run: AnalysisRun) -> dict:
    return dict(run.effective_data_classification or {})


def _audit(db: Session, run: AnalysisRun, action: str, detail: dict | None = None) -> None:
    audit.record(
        db, workspace_id=run.workspace_id, actor_user_id=None, action=action,
        target_type="run", target_id=run.run_id, detail=detail,
    )


def availability(run: AnalysisRun) -> tuple[bool, str]:
    """Per-run A3 availability (not field-scoped). cloud_assisted + public/synthetic
    + provider/fake available. Never upgrades the run's mode."""
    mode = run.processing_mode
    if mode in _NO_CALL_MODES:
        return False, f"processing_mode_{mode}"
    registry = gateway.get_agent_registry()
    settings = get_settings()
    confirmed = real_eval_confirmed(run)
    if not settings.agent_fake_provider and not confirmed:
        return False, "real_eval_confirmation_required"
    decision = data_policy.evaluate(
        profile=registry.profile(A3_PROFILE_ID), classification=_classification(run),
        processing_mode=mode, settings=settings, run_confirmation=confirmed,
    )
    if decision.blocked:
        return False, decision.reason
    if not settings.agent_fake_provider:
        route = registry.route(registry.profile(A3_PROFILE_ID).primary_model)
        adapter = _PROVIDER_RESOLVER(route)
        if adapter is None or not adapter.available():
            return False, "provider_unavailable"
    return True, "available"


def _fake_resolver(ctx: a3_context.CriticContext):
    """Deterministic dev/test fake: one in-scope warning finding (valid bundle)."""
    import json

    from app.agents.providers import FakeProvider

    field_id = ctx.payload["current_drafts"][0]["field_id"]
    config = field_drafting.a2_fields.resolve_field_config(field_id)
    target_section = (
        config.mandatory_markers[0]
        if config is not None and config.mandatory_markers
        else "risk_register"
    )
    bundle = {
        "findings": [{
            "origin_profile_id": A3_PROFILE_ID, "severity": "warning", "status": "open",
            "field_id": field_id,
            "target_section": target_section,
            "description": "Mehrere Aussagen sind noch nicht mit verifizierten Belegen verknüpft.",
            "suggested_improvement": "Verknüpfen Sie zentrale Aussagen mit geprüften Belegen "
                                     "oder markieren Sie offene Punkte.",
            "recommended_next_action": "Belege ergänzen oder offene Punkte kennzeichnen.",
        }],
        "profile_summaries": [{"profile_id": A3_PROFILE_ID, "finding_count": 1}],
        "overall_limitations": [],
    }
    return lambda _route: FakeProvider(raw_output=json.dumps(bundle))


def _resolver(ctx: a3_context.CriticContext, provider_resolver):
    if provider_resolver is not None:
        return provider_resolver
    if get_settings().agent_fake_provider:
        return _fake_resolver(ctx)
    return _PROVIDER_RESOLVER


def _validate_findings(bundle, ctx: a3_context.CriticContext) -> list[A3Finding]:
    """Drop findings whose target does not exist / is out of scope (the bundle schema
    is already validated by the gateway). A per-finding target failure never fails the
    whole bundle (STEP 6)."""
    out: list[A3Finding] = []
    for rec in bundle.findings:
        if rec.field_id is None or rec.field_id not in ctx.allowed_field_ids:
            continue
        if rec.field_id in a3_review.A3_SCOPE_FIELDS:
            config = field_drafting.a2_fields.resolve_field_config(rec.field_id)
            if config is None or rec.target_section not in config.mandatory_markers:
                continue
        elif rec.field_id == "PS.RISK_MANAGEMENT.SECTION":
            if rec.target_section != "risk_register":
                continue
        if rec.requirement_id is not None and rec.requirement_id not in ctx.allowed_requirement_ids:
            continue
        if rec.evidence_anchor_id is not None and rec.evidence_anchor_id not in ctx.allowed_anchor_ids:
            continue
        if rec.evidence_link_id is not None and rec.evidence_link_id not in ctx.allowed_link_ids:
            continue
        if rec.field_id is None and rec.requirement_id is None:
            continue  # a finding must target a scoped field or a known requirement
        out.append(A3Finding(
            origin_profile_id=rec.origin_profile_id, severity=rec.severity,
            status=rec.status, description=rec.description, field_id=rec.field_id,
            target_section=rec.target_section,
            requirement_id=rec.requirement_id, evidence_anchor_id=rec.evidence_anchor_id,
            evidence_link_id=rec.evidence_link_id,
            suggested_improvement=rec.suggested_improvement,
            recommended_next_action=rec.recommended_next_action,
        ))
    return out


def run_a3_evidence_consistency(
    db: Session, run: AnalysisRun, *, provider_resolver=None
) -> A3Outcome:
    """Generate + validate advisory A3 findings. Never raises. Only a 'succeeded'
    outcome carries findings the caller may persist."""
    try:
        return _run(db, run, provider_resolver=provider_resolver)
    except Exception:  # defensive: A3 must never break the recheck
        logger.exception("A3 evidence consistency crashed; run %s", run.run_id)
        _audit(db, run, "agent.evidence_consistency.failed", {"reason": "internal_error"})
        return A3Outcome(status="failed", reason="internal_error")


def _run(db, run, *, provider_resolver) -> A3Outcome:
    ctx = a3_context.assemble_critic_context(db, run)
    if ctx is None:
        # corr 5: no scoped draft content — skip, never fabricate.
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            control_id="CTRL.DATA_POLICY", status="passed", detail="a3_scope_empty_skipped",
            run_id=run.run_id,
        )
        _audit(db, run, "agent.evidence_consistency.skipped", {"reason": "scope_empty"})
        return A3Outcome(status="skipped", reason="scope_empty")

    try:
        validate_payload(INPUT_SCHEMA, ctx.payload)
    except (ValidationError, SchemaNotImplementedError):
        controls.record(
            db, workspace_id=run.workspace_id, project_id=run.project_id,
            control_id="CTRL.INPUT_SCHEMA", status="failed",
            detail="a3_input_schema_invalid",
            run_id=run.run_id,
        )
        _audit(db, run, "agent.evidence_consistency.skipped", {"reason": "input_schema"})
        return A3Outcome(status="skipped", reason="input_schema")

    request = gateway.ModelRequest(
        profile_id=A3_PROFILE_ID, workspace_id=run.workspace_id, input_payload=ctx.payload,
        classification=_classification(run), processing_mode=run.processing_mode,
        run_id=run.run_id, project_id=run.project_id,
        run_confirmation=real_eval_confirmed(run),
        prompt_version=prompt_version_for(A3_PROFILE_ID), context_text=ctx.context_text,
        context_hash=ctx.context_hash, context_meta=ctx.meta,
    )
    result = gateway.invoke(db, request, provider_resolver=_resolver(ctx, provider_resolver))

    if isinstance(result, gateway.SafeFailure):
        # policy block / provider unavailable / timeout / schema failure / cost block.
        _audit(db, run, "agent.evidence_consistency.failed", {"reason": result.error_code})
        status = "blocked" if result.status == "blocked" else "failed"
        return A3Outcome(status=status, reason=result.error_code,
                         invocation_id=result.invocation_id)

    controls.record(
        db, workspace_id=run.workspace_id, project_id=run.project_id,
        control_id="CTRL.OUTPUT_SCHEMA", status="passed", detail="a3_bundle_validated",
        run_id=run.run_id, agent_invocation_id=result.invocation_id,
    )
    findings = _validate_findings(result.output, ctx)
    _audit(db, run, "agent.evidence_consistency.succeeded",
           {"finding_count": len(findings), "invocation_id": result.invocation_id})
    return A3Outcome(status="succeeded", findings=findings, invocation_id=result.invocation_id)
