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
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.agents import critic_review_context as a3_context
from app.agents import data_policy, gateway
from app.agents import a3_review, field_drafting
from app.agents.a3_review import A3_PROFILE_ID
from app.agents.prompt_assets import prompt_version_for
from app.agents.schemas import SchemaNotImplementedError, ValidationError, validate_payload
from app.config.settings import get_settings
from app.db.models import AnalysisRun
from app.repositories import audit, controls
from app.runs.cloud_policy import real_eval_confirmed

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
    # Observability (Owner 2026-07-16): der Produktionsfilter darf Findings
    # nie still verschwinden lassen — Zählwerte + Reason-Codes je Verwerfung
    # (nur Codes/Counts, keine Inhalte).
    filter_stats: dict = field(default_factory=dict)


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
    from app.evaluation.preflight import live_fake_conflict, ready_route_for_role
    if live_fake_conflict(settings):
        return False, "live_fake_conflict"
    confirmed = real_eval_confirmed(run)
    is_demo = settings.agent_fake_provider and settings.ai_eval_mode != "real"
    if not is_demo and not confirmed:
        return False, "real_eval_confirmation_required"
    decision = data_policy.evaluate(
        profile=registry.profile(A3_PROFILE_ID), classification=_classification(run),
        processing_mode=mode, settings=settings, run_confirmation=confirmed,
    )
    if decision.blocked:
        return False, decision.reason
    if not is_demo:
        try:
            db = Session.object_session(run)
        except Exception:
            db = None
        _route_key, reason = ready_route_for_role(
            db, "A3_INNOSUISSE_CRITICAL_REVIEWER",
            settings=settings, registry=registry,
        )
        if reason:
            return False, reason
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
    settings = get_settings()
    if settings.agent_fake_provider and settings.ai_eval_mode != "real":
        return _fake_resolver(ctx)
    return _PROVIDER_RESOLVER


def _validate_findings(
    bundle, ctx: a3_context.CriticContext, bound_routing: dict | None = None
) -> tuple[list[A3Finding], dict]:
    """Drop findings whose target does not exist / is out of scope (the bundle schema
    is already validated by the gateway). A per-finding target failure never fails the
    whole bundle (STEP 6). Liefert zusätzlich eine Filter-Statistik
    (received/accepted/rejected + Reason-Codes) — nie stilles Verwerfen.

    ``bound_routing`` (Review EINES Abschnitts): der Caller kennt field_id und
    target_section und bindet sie an jedes Finding. Das Modell liefert dann nur
    noch Beschreibung, Begründung, Severity und Verbesserungsvorschlag — ein
    Finding verschwindet nie wegen einer fehlenden Routing-ID. Widersprüchliche
    Modellangaben werden gezählt (``model_routing_hint_mismatch``), nicht
    stillschweigend übernommen; inhaltliche Prüfungen bleiben unberührt.
    """
    out: list[A3Finding] = []
    rejected: dict[str, int] = {}
    routing_hint_mismatch = 0

    def _reject(code: str) -> None:
        rejected[code] = rejected.get(code, 0) + 1

    for rec in bundle.findings:
        if bound_routing is not None:
            bound_field = bound_routing["field_id"]
            bound_section = bound_routing["target_section"]
            if (
                (rec.field_id is not None and rec.field_id != bound_field)
                or (rec.target_section and rec.target_section != bound_section)
            ):
                routing_hint_mismatch += 1
            rec = rec.model_copy(update={
                "field_id": bound_field, "target_section": bound_section,
            })
        if rec.field_id is None or rec.field_id not in ctx.allowed_field_ids:
            _reject("field_out_of_scope")
            continue
        if rec.field_id in a3_review.A3_SCOPE_FIELDS:
            config = field_drafting.a2_fields.resolve_field_config(rec.field_id)
            if config is None or rec.target_section not in config.mandatory_markers:
                _reject("invalid_target_section")
                continue
        elif rec.field_id == "PS.RISK_MANAGEMENT.SECTION":
            if rec.target_section != "risk_register":
                _reject("invalid_target_section")
                continue
        if rec.requirement_id is not None and rec.requirement_id not in ctx.allowed_requirement_ids:
            _reject("unknown_requirement")
            continue
        if rec.evidence_anchor_id is not None and rec.evidence_anchor_id not in ctx.allowed_anchor_ids:
            _reject("unknown_evidence_anchor")
            continue
        if rec.evidence_link_id is not None and rec.evidence_link_id not in ctx.allowed_link_ids:
            _reject("unknown_evidence_link")
            continue
        if rec.field_id is None and rec.requirement_id is None:
            _reject("no_target")
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
    grouped = _group_similar_findings(out)
    stats = {
        "received": len(bundle.findings),
        "accepted": len(out),
        "rejected": sum(rejected.values()),
        "rejected_reasons": rejected,
        "grouped": len(grouped),
        "routing_metadata_source": (
            "caller_bound" if bound_routing is not None else "model_provided"
        ),
        "model_routing_hint_mismatch": routing_hint_mismatch,
    }
    return grouped, stats


_GROUP_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")


def _finding_family(text: str) -> str:
    """Stable, conservative grouping key for repeated A3 symptoms.

    A3 may identify many affected claims, but the user needs one actionable task.
    We only collapse findings that share target, severity, action and a normalized
    issue family; unrelated problems are never hidden.
    """
    normalized = _GROUP_NUMBER_RE.sub("#", " ".join((text or "").lower().split()))
    return normalized[:180]


def _group_similar_findings(findings: list[A3Finding]) -> list[A3Finding]:
    grouped: dict[tuple[str | None, str | None, str | None, str, str, str], A3Finding] = {}
    counts: dict[tuple[str | None, str | None, str | None, str, str, str], int] = {}
    for finding in findings:
        key = (
            finding.field_id, finding.target_section, finding.requirement_id,
            finding.severity, _finding_family(finding.description),
            _finding_family(finding.recommended_next_action or ""),
        )
        if key not in grouped:
            grouped[key] = finding
            counts[key] = 1
            continue
        counts[key] += 1
        # Keep the first concrete source/action: it remains traceable and avoids
        # turning a grouped task into an unbounded raw-claim collection.
    result: list[A3Finding] = []
    for key, finding in grouped.items():
        count = counts[key]
        if count > 1:
            finding = A3Finding(
                **{
                    **finding.__dict__,
                    "description": (
                        f"{finding.description} (betrifft {count} ähnliche Hinweise)"
                    ),
                }
            )
        result.append(finding)
    return result


def run_a3_evidence_consistency(
    db: Session, run: AnalysisRun, *, provider_resolver=None, bound_routing=None
) -> A3Outcome:
    """Generate + validate advisory A3 findings. Never raises. Only a 'succeeded'
    outcome carries findings the caller may persist.

    ``bound_routing={"field_id": …, "target_section": …}`` bindet die
    Routing-Metadaten beim Review eines einzelnen Abschnitts an den Request
    (Default None ⇒ unveränderter Mehrfeld-Review mit Modellangaben)."""
    try:
        return _run(
            db, run, provider_resolver=provider_resolver,
            bound_routing=bound_routing,
        )
    except Exception:  # defensive: A3 must never break the recheck
        logger.exception("A3 evidence consistency crashed; run %s", run.run_id)
        _audit(db, run, "agent.evidence_consistency.failed", {"reason": "internal_error"})
        return A3Outcome(status="failed", reason="internal_error")


def _run(db, run, *, provider_resolver, bound_routing=None) -> A3Outcome:
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
        skill_id="a3.critical_review",
        # Kein stiller Fallback für die provisorische Demo-Route.
        route_preference="primary_only",
        input_artifact_refs=(
            {
                "kind": "review_scope",
                "run_id": run.run_id,
                "field_ids": sorted(ctx.allowed_field_ids),
                "evidence_anchor_ids": sorted(ctx.allowed_anchor_ids),
                "context_hash": ctx.context_hash,
            },
        ),
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
    findings, filter_stats = _validate_findings(result.output, ctx, bound_routing)
    _audit(db, run, "agent.evidence_consistency.succeeded",
           {"finding_count": len(findings), "invocation_id": result.invocation_id,
            "filter_stats": filter_stats})
    return A3Outcome(status="succeeded", findings=findings,
                     invocation_id=result.invocation_id,
                     filter_stats=filter_stats)
