"""Immutable export input snapshot (Milestone 8).

Freezes the *complete generator-facing representation* of every mutable entity
plus the immutable referenced rows, in one place, so generators read only the
snapshot — never mutable current-state rows. Canonical JSON + SHA-256.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisRun,
    AgentInvocation,
    AuditEvent,
    ClaimLineage,
    CopyEvent,
    DraftClaim,
    EvidenceAnchor,
    EvidenceLink,
    HumanDecision,
    OpenIssue,
    Project,
    ReviewApproval,
    ReviewFinding,
    ReviewPackage,
    RuleResult,
    RunProjectSnapshot,
    RunQualitySummary,
    RunSourceSnapshot,
    SourceDocument,
    StructuredImportCandidate,
    ResearchResult,
    ToolInvocation,
    ControlResult,
    UsageRecord,
)
from app.exports import EXPORT_SNAPSHOT_SCHEMA
from app.exports.eligibility import DraftDecision
from app.registry import get_registry
from app.repositories import drafts as drafts_repo
from app.repositories import evidence as evidence_repo
from app.repositories import requirements as requirements_repo
from app.runs import project_snapshot

# Deferred structured/repeated areas not covered by the Beta export (coverage
# disclosure, corr. #5). These are registry families with no M6 draft support.
DEFERRED_AREAS = [
    "Arbeitspakete (Work Packages)",
    "Meilensteine und Meilensteinziele",
]
COVERAGE_NOTE = (
    "Diese Beta exportiert nur die aktuell unterstützten Portalfelder. Strukturierte "
    "und wiederholte Bereiche sind noch nicht enthalten. Dieser Export ist daher "
    "nicht die vollständige Innosuisse-/Innolink-Eingabe."
)


def canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_BUDGET_FIELDS: tuple[tuple[str, str], ...] = (
    ("direct_total_project_costs_excluding_overhead", "Direkte Projektkosten (ohne Overhead)"),
    ("implementation_own_contribution", "Eigenleistung Umsetzungspartner"),
    ("cash_contribution", "Cash-Beitrag Umsetzungspartner"),
    ("total_requested_funding", "Beantragte direkte Förderung"),
    ("total_requested_funding_including_overhead", "Beantragte Förderung inkl. Overhead"),
)

_INSTRUMENT_LABELS = {
    "innosuisse_innovation_project_with_implementation_partner": (
        "Innosuisse Innovation Project mit Umsetzungspartner"
    ),
}
_PARTNER_TYPE_LABELS = {
    "research_partner": "Forschungspartner",
    "implementation_partner": "Umsetzungspartner",
    "other": "Weitere Organisation",
}
_ELIGIBILITY_LABELS = {
    "eligible": "Geprüft: berechtigt",
    "not_eligible": "Geprüft: nicht berechtigt",
    "needs_verification": "Prüfung erforderlich",
}
_RULE_STATUS_LABELS = {
    "passed": "Erfüllt",
    "failed": "Nicht erfüllt",
    "needs_input": "Eingabe erforderlich",
    "not_applicable": "Nicht anwendbar",
}


def _candidate_payload(candidate: StructuredImportCandidate) -> dict:
    return candidate.edited_payload_json or candidate.payload_json or {}


def _frozen_provenance(
    db: Session, *, project_id: str, frozen_at: datetime, target_id: str | None,
    target_keys: set[str], frozen_value: object | None = None,
) -> str:
    """Return an export-safe provenance label for the immutable value only."""
    rows = db.execute(
        select(StructuredImportCandidate, SourceDocument.name)
        .join(SourceDocument, SourceDocument.source_id == StructuredImportCandidate.source_id)
        .where(
            StructuredImportCandidate.project_id == project_id,
            StructuredImportCandidate.decision == "accepted",
            StructuredImportCandidate.decided_at.is_not(None),
            StructuredImportCandidate.decided_at <= frozen_at,
        )
        .order_by(StructuredImportCandidate.decided_at.desc(), StructuredImportCandidate.candidate_id.asc())
    ).all()
    for candidate, source_name in rows:
        if target_id is not None and candidate.applied_resource_id != target_id:
            continue
        if target_id is None and candidate.target_key not in target_keys:
            continue
        payload = _candidate_payload(candidate)
        if frozen_value is not None and frozen_value not in payload.values():
            continue
        location = f", {candidate.source_location}" if candidate.source_location else ""
        return f"Import bestätigt: {source_name}{location}"
    return "Manuell erfasst oder nach Import geändert"


def _budget_block(db: Session, snap: RunProjectSnapshot) -> dict:
    project = snap.project_json or {}
    direct = project.get("direct_total_project_costs_excluding_overhead")
    own = project.get("implementation_own_contribution")
    cash = project.get("cash_contribution")
    contribution = (own or 0) + (cash or 0) if own is not None or cash is not None else None
    values = []
    for key, label in _BUDGET_FIELDS:
        value = project.get(key)
        values.append({
            "key": key, "label": label, "value": value,
            "copy_target": f"budget:{key}",
            "provenance": _frozen_provenance(
                db, project_id=snap.project_id, frozen_at=snap.created_at,
                target_id=None, target_keys={f"project.{key}", key}, frozen_value=value,
            ),
        })
    ratios = []
    if direct and direct > 0:
        if contribution is not None:
            ratios.append({"label": "Anteil Eigenleistung und Cash an direkten Kosten", "value": contribution / direct})
        if cash is not None:
            ratios.append({"label": "Cash-Anteil an direkten Kosten", "value": cash / direct})
    return {"values": values, "ratios": ratios}


def _partner_block(db: Session, snap: RunProjectSnapshot) -> list[dict]:
    result = []
    for index, partner in enumerate(snap.partners_json or []):
        partner_id = partner.get("partner_id")
        result.append({
            "index": index,
            "name": partner.get("name") or "Nicht angegeben",
            "partner_type": partner.get("partner_type") or "Nicht angegeben",
            "partner_type_label": _PARTNER_TYPE_LABELS.get(partner.get("partner_type"), "Nicht angegeben"),
            "project_role": partner.get("project_role") or "Nicht angegeben",
            "country": partner.get("country") or "Nicht angegeben",
            "swiss_value_creation": partner.get("swiss_value_creation"),
            "eligibility_status": partner.get("research_partner_eligibility_status") or "Nicht geprüft",
            "eligibility_status_label": _ELIGIBILITY_LABELS.get(
                partner.get("research_partner_eligibility_status"), "Nicht geprüft"
            ),
            "provenance": _frozen_provenance(
                db, project_id=snap.project_id, frozen_at=snap.created_at,
                target_id=partner_id, target_keys=set(), frozen_value=partner.get("name"),
            ),
            "copy_target_row": f"partner:{index}",
        })
    return result


def _source_block(db: Session, run: AnalysisRun) -> list[dict]:
    """Return only sources frozen into this run; candidates never appear here."""
    source_ids = list(db.scalars(
        select(RunSourceSnapshot.source_id).where(RunSourceSnapshot.run_id == run.run_id)
    ))
    if not source_ids:
        return []
    public_urls = {
        row.source_document_id: (row.final_url or row.source_url)
        for row in db.scalars(
            select(ResearchResult).where(
                ResearchResult.source_document_id.in_(source_ids),
                ResearchResult.status == "imported",
            ).order_by(ResearchResult.result_id.asc())
        )
    }
    names = dict(db.execute(
        select(SourceDocument.source_id, SourceDocument.name).where(SourceDocument.source_id.in_(source_ids))
    ).all())
    return [
        {"source_id": source_id, "title": names.get(source_id, "Unbenannte Quelle"), "url": public_urls.get(source_id)}
        for source_id in sorted(source_ids)
    ]


def build_transfer_snapshot(db: Session, run: AnalysisRun) -> dict:
    """Immutable structured read model for exports and manual portal transfer.

    A legacy run without RunProjectSnapshot receives no current-project fallback.
    That prevents a document from silently mixing later edits into a past run.
    """
    snap = db.scalar(select(RunProjectSnapshot).where(RunProjectSnapshot.run_id == run.run_id))
    manual_tasks = ["Arbeitspakete (Work Packages)", "Meilensteine und Meilensteinziele"]
    if snap is None:
        return {
            "snapshot_available": False, "stale": False,
            "stale_message": "Strukturierter Run-Snapshot fehlt; Partner, Budget und Dauer werden nicht ersetzt.",
            "project": {}, "partners": [], "budget": {"values": [], "ratios": [], "rules": []},
            "sources": [], "manual_portal_tasks": manual_tasks, "snapshot_hash": None,
        }
    stale = project_snapshot.is_stale(db, snap)
    rules = [
        {
            "rule_id": r.rule_id, "status": r.status, "status_label": _RULE_STATUS_LABELS.get(r.status, "Prüfstatus unbekannt"),
            "outcome_label": r.outcome_label, "severity": r.severity,
        }
        for r in db.scalars(select(RuleResult).where(RuleResult.run_id == run.run_id).order_by(RuleResult.rule_result_id.asc()))
        if r.rule_id.startswith("INNO.BUDGET.") or r.rule_id == "INNO.PARTNER.INDEPENDENCE.FINANCIAL_20"
    ]
    project = snap.project_json or {}
    budget = _budget_block(db, snap)
    budget["rules"] = rules
    return {
        "snapshot_available": True,
        "stale": stale,
        "stale_message": "Projekt- oder Partnerdaten wurden nach dem Run geändert. Diese Arbeitskopie verwendet weiterhin den eingefrorenen Run-Snapshot." if stale else None,
        "snapshot_hash": snap.content_hash,
        "project": {
            "title": project.get("title") or "Ohne Projekttitel",
            "instrument": _INSTRUMENT_LABELS.get(
                project.get("funding_instrument_profile_id"), project.get("funding_instrument_profile_id") or "Nicht angegeben"
            ),
            "duration_months": project.get("duration_months"),
            "duration_copy_target": "duration",
            "application_language": None,
            "structured_answers": project.get("structured_answers") or {},
        },
        "partners": _partner_block(db, snap), "budget": budget,
        "sources": _source_block(db, run), "manual_portal_tasks": manual_tasks,
    }


def _approval_dict(approval: ReviewApproval | None) -> dict | None:
    if approval is None:
        return None
    return {
        "approval_id": approval.approval_id,
        "scope": approval.scope,
        "scope_id": approval.scope_id,
        "status": approval.status,
        "approval_scope_hash": approval.approval_scope_hash,
        "review_package_version": approval.review_package_version,
        "approved_by": approval.approved_by,
        "created_at": approval.created_at.isoformat() if approval.created_at else None,
    }


def _fields(db: Session, run: AnalysisRun) -> list[dict]:
    """Supported field drafts in canonical registry order; immutable text + hash."""
    out: list[dict] = []
    for field in get_registry().m6_draft_fields():
        draft = drafts_repo.get_draft(db, run.run_id, field.field_id)
        if draft is None:
            continue
        contract = drafts_repo.to_contract(db, draft).model_dump(mode="json")
        out.append(
            {
                "field_id": field.field_id,
                "field_name": contract["field_name"],
                "draft_id": contract["draft_id"],
                "draft_version_id": contract["current_version"]["draft_version_id"],
                "content_hash": contract["current_version"]["content_hash"],
                "character_count": contract["character_count"],
                "character_limit": contract["character_limit"],
                "text": contract["current_version"]["text"],
                "created_by": contract["current_version"]["created_by"],
                "evidence_links": sorted(
                    (
                        {
                            "evidence_link_id": link["evidence_link_id"],
                            "anchor_id": link["anchor_id"],
                            "status": link["status"],
                        }
                        for link in contract["evidence_links"]
                    ),
                    key=lambda link: link["evidence_link_id"],
                ),
                "open_issues": contract["open_issues"],
            }
        )
    return out


def _reliability_block(db: Session, run: AnalysisRun) -> dict:
    """Milestone 9K reliability metrics for the technical-evidence export. Uses the
    RunQualitySummary + per-claim *metadata* only — ``claim_hash`` + status, never
    ``claim_text`` (corr 5/14). Absent when no reliability pass has run."""
    summary = db.scalar(
        select(RunQualitySummary)
        .where(RunQualitySummary.run_id == run.run_id)
        .order_by(RunQualitySummary.generated_at.desc())
    )
    if summary is None:
        return {"available": False}
    lineages = {
        lin.claim_id: lin
        for lin in db.scalars(select(ClaimLineage).where(ClaimLineage.run_id == run.run_id))
    }
    claim_lineage_summary = [
        {
            "claim_hash": c.source_text_hash,
            "field_id": c.field_id,
            "claim_type": c.claim_type,
            "strength": c.strength,
            "requires_evidence": c.requires_evidence,
            "lineage_status": lineages[c.claim_id].lineage_status if c.claim_id in lineages else "no_evidence",
            "sufficiency_status": lineages[c.claim_id].sufficiency_status if c.claim_id in lineages else "insufficient_evidence",
        }
        for c in db.scalars(
            select(DraftClaim)
            .where(DraftClaim.run_id == run.run_id)
            .order_by(DraftClaim.field_id.asc(), DraftClaim.start_char.asc())
        )
    ]
    return {
        "available": True,
        "assurance_matrix_ref": "docs/reliability/Architecture_Assurance_Matrix.md",
        "note": (
            "Evidence sufficiency is a deterministic check under defined criteria "
            "(not semantic proof / not 'verified as true'). The raw claim wording is "
            "intentionally excluded; only claim_hash + status metadata are exported."
        ),
        "quality_summary": {
            "summary_version": summary.summary_version,
            "status": summary.status,
            "source_scope_hash": summary.source_scope_hash,
            "quality_flag": summary.quality_flag,
            "claim_count": summary.claim_count,
            "supported_claims": summary.supported_claims,
            "weakly_supported_claims": summary.weakly_supported_claims,
            "unsupported_claims": summary.unsupported_claims,
            "conflicting_claims": summary.conflicting_claims,
            "evidence_coverage": summary.evidence_coverage,
            "evidence_correctness_sample_size": summary.evidence_correctness_sample_size,
            "evidence_correctness_sample_pass_rate": summary.evidence_correctness_sample_pass_rate,
            "review_required_count": summary.review_required_count,
            "blocker_count": summary.blocker_count,
            "warning_count": summary.warning_count,
            "fields_ready": summary.fields_ready,
            "fields_needs_review": summary.fields_needs_review,
            "false_consensus_risk_count": summary.false_consensus_risk_count,
            "semantic_drift_count": summary.semantic_drift_count,
            "raw_logging_detected": summary.raw_logging_detected,
            "tool_leakage_detected": summary.tool_leakage_detected,
            "cost_chf": summary.cost_chf,
            "cost_placeholder": summary.cost_placeholder,
        },
        "claim_lineage_summary": claim_lineage_summary,
    }


def _technical_trace(db: Session, run: AnalysisRun) -> dict:
    """Technical IDs/hashes/counts only. Never copy human text into an audit export."""
    usage = {
        item.usage_record_id: item
        for item in db.scalars(select(UsageRecord).where(UsageRecord.run_id == run.run_id))
    }
    agents = []
    for inv in db.scalars(
        select(AgentInvocation).where(AgentInvocation.run_id == run.run_id).order_by(AgentInvocation.invocation_id.asc())
    ):
        context = inv.context_meta or {}
        real_call = bool(context.get("model_call_attempted")) and context.get("generation_kind") == "model_generated"
        item = {
            "invocation_id": inv.invocation_id, "agent_id": inv.agent_id,
            "profile_id": inv.profile_id, "model_route": inv.model_route,
            "input_schema_id": inv.input_schema_id, "output_schema_id": inv.output_schema_id,
            "prompt_version": inv.prompt_version, "status": inv.status,
            "input_hash": inv.input_hash, "output_hash": inv.output_hash,
            "latency_ms": inv.latency_ms, "usage_record_id": inv.usage_record_id,
            "generation_kind": context.get("generation_kind"),
            "call_kind": "real_model_call" if real_call else ("fake_or_stubbed_call" if context.get("generation_kind") else "no_model_call"),
            "context_meta_hash": _sha256(canonical_json(context)),
        }
        if real_call:
            record = usage.get(inv.usage_record_id)
            item["provider"] = inv.provider
            item["model_id"] = inv.model_id
            # Ebene E: angefragtes UND vom Provider gemeldetes Modell gehören
            # beide in den technischen Nachweis (None = nicht gemeldet).
            item["actual_model_id"] = inv.actual_model_id
            if record is not None:
                item["metering"] = {
                    "input_tokens": record.input_tokens, "output_tokens": record.output_tokens,
                    "cost_chf": record.cost_chf, "cost_status": record.cost_status,
                    "price_version": record.price_version,
                }
            else:
                item["metering"] = {"status": "missing_usage_record"}
        else:
            item["metering"] = {"status": "not_applicable_no_real_model_call"}
        agents.append(item)
    tools = [
        {
            "invocation_id": t.invocation_id, "tool_id": t.tool_id, "caller": t.caller,
            "input_hash": t.input_hash, "output_hash": t.output_hash, "status": t.status,
            "duration_ms": t.duration_ms, "error_class": t.error_class,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in db.scalars(select(ToolInvocation).where(ToolInvocation.run_id == run.run_id).order_by(ToolInvocation.invocation_id.asc()))
    ]
    controls = [
        {
            "control_result_id": c.control_result_id, "control_id": c.control_id,
            "status": c.status, "tool_invocation_id": c.tool_invocation_id,
            "agent_invocation_id": c.agent_invocation_id,
            "detail_hash": _sha256(c.detail or ""),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in db.scalars(select(ControlResult).where(ControlResult.run_id == run.run_id).order_by(ControlResult.control_result_id.asc()))
    ]
    copy_events = list(db.scalars(
        select(CopyEvent).where(CopyEvent.run_id == run.run_id).order_by(CopyEvent.copy_event_id.asc())
    ))
    copy_event_ids = [event.copy_event_id for event in copy_events]
    audit_scope = (AuditEvent.target_type == "run") & (AuditEvent.target_id == run.run_id)
    if copy_event_ids:
        audit_scope = audit_scope | ((AuditEvent.target_type == "copy_event") & AuditEvent.target_id.in_(copy_event_ids))
    audits = [
        {
            "audit_event_id": a.id, "action": a.action, "target_type": a.target_type,
            "target_id": a.target_id, "actor_user_id": a.actor_user_id,
            "detail_hash": _sha256(canonical_json(a.detail or {})),
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in db.scalars(
            select(AuditEvent).where(
                AuditEvent.workspace_id == run.workspace_id,
                audit_scope,
            ).order_by(AuditEvent.id.asc())
        )
    ]
    return {
        "agent_invocations": agents, "tool_invocations": tools, "control_results": controls,
        "copy_events": [
            {
                "copy_event_id": event.copy_event_id, "target_type": event.target_type,
                "target_key": event.target_key, "field_id": event.field_id,
                "draft_version_id": event.draft_version_id, "content_hash": event.content_hash,
                "client_warning_count": len(event.client_warnings or []),
                "server_warning_count": len(event.server_warnings or []),
                "override_reason_code": event.override_reason_code,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
            for event in copy_events
        ],
        "audit_events": audits,
    }


def build_snapshot(
    db: Session,
    run: AnalysisRun,
    *,
    export_type: str,
    decision: DraftDecision,
    actor_user_id: str,
    frozen_at: datetime,
) -> tuple[dict, str]:
    """Build the frozen snapshot dict + its SHA-256 hash."""
    registry = get_registry()
    snap = db.scalar(
        select(RunProjectSnapshot).where(RunProjectSnapshot.run_id == run.run_id)
    )
    structured = build_transfer_snapshot(db, run)
    stale = structured["stale"]

    review_pkg = db.get(ReviewPackage, run.run_id)

    rule_results = [
        {
            "rule_result_id": r.rule_result_id,
            "requirement_id": r.requirement_id,
            "rule_id": r.rule_id,
            "rule_version": r.rule_version,
            "status": r.status,
            "outcome_label": r.outcome_label,
            "severity": r.severity,
        }
        for r in db.scalars(
            select(RuleResult)
            .where(RuleResult.run_id == run.run_id)
            .order_by(RuleResult.rule_result_id.asc())
        )
    ]
    open_issues = [
        requirements_repo._issue_to_contract(i).model_dump(mode="json")
        for i in db.scalars(
            select(OpenIssue)
            .where(OpenIssue.run_id == run.run_id)
            .order_by(OpenIssue.issue_id.asc())
        )
    ]
    anchors = [
        evidence_repo.to_anchor_contract(a).model_dump(mode="json")
        for a in db.scalars(
            select(EvidenceAnchor)
            .where(EvidenceAnchor.run_id == run.run_id)
            .order_by(EvidenceAnchor.anchor_id.asc())
        )
    ]
    links = [
        evidence_repo.to_link_contract(link).model_dump(mode="json")
        for link in db.scalars(
            select(EvidenceLink)
            .where(EvidenceLink.run_id == run.run_id)
            .order_by(EvidenceLink.evidence_link_id.asc())
        )
    ]
    findings = [
        {
            "finding_id": f.finding_id,
            "field_id": f.field_id,
            "requirement_id": f.requirement_id,
            "severity": f.severity,
            "description": f.description,
            "status": f.status,
            "source": f.source,
            "advisory": f.advisory,
        }
        for f in db.scalars(
            select(ReviewFinding)
            .where(ReviewFinding.run_id == run.run_id)
            .order_by(ReviewFinding.finding_id.asc())
        )
    ]
    # Review-relevant HumanDecision data only (no PII beyond the internal actor id).
    decisions = [
        {
            "decision_id": d.decision_id,
            "target_type": d.target_type,
            "target_id": d.target_id,
            "action": d.action,
            "comment": d.comment,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in db.scalars(
            select(HumanDecision)
            .where(HumanDecision.run_id == run.run_id)
            .order_by(HumanDecision.decision_id.asc())
        )
    ]

    fields = _fields(db, run)
    snapshot = {
        "schema": EXPORT_SNAPSHOT_SCHEMA,
        "meta": {
            "run_id": run.run_id,
            "project_id": run.project_id,
            "project_title": structured["project"].get("title", "Ohne Projekttitel"),
            "funding_profile_id": structured["project"].get("instrument", "Nicht angegeben"),
            "funding_profile_version": run.snapshot_versions.get(
                "funding_instrument_profile_version"
            ),
            "export_type": export_type,
            "force_draft": "force_draft" in decision.reasons,
            "draft_marked": decision.draft_marked,
            "draft_reasons": list(decision.reasons),
            "created_by": actor_user_id,
            "frozen_at": frozen_at.isoformat(),
            "effective_data_classification": run.effective_data_classification,
        },
        "review": {
            "review_package_version": decision.review_package_version,
            "approval_scope_hash": decision.scope_hash,
            "approval_status": review_pkg.approval_status if review_pkg else None,
            "blocker_count": review_pkg.blocker_count if review_pkg else 0,
            "warning_count": review_pkg.warning_count if review_pkg else 0,
            "approval": _approval_dict(decision.approval),
        },
        "coverage": {
            "supported_field_ids": [f["field_id"] for f in fields],
            "deferred_areas": DEFERRED_AREAS,
            "note": COVERAGE_NOTE,
        },
        "structured": structured,
        "fields": fields,
        "requirements": [
            a.model_dump(mode="json")
            for a in requirements_repo.to_contracts(db, run.run_id, stale=stale)
        ],
        "rule_results": rule_results,
        "open_issues": open_issues,
        "evidence_anchors": anchors,
        "evidence_links": links,
        "review_findings": findings,
        "human_decisions": decisions,
        "reliability": _reliability_block(db, run),
        "technical_trace": _technical_trace(db, run),
        "config_versions": {
            "requirement_registry_version": registry.requirement_registry_version,
            "rule_registry_version": registry.rule_registry_version,
            "portal_field_profile_version": registry.portal_field_profile_version,
            "snapshot_versions": run.snapshot_versions,
        },
    }
    return snapshot, _sha256(canonical_json(snapshot))
