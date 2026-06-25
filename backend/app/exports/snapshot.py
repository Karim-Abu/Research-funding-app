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
    "Budget- und Finanzierungsplan",
    "Wiederholte Partner-/Positionsinstanzen",
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
    project = db.get(Project, run.project_id)
    snap = db.scalar(
        select(RunProjectSnapshot).where(RunProjectSnapshot.run_id == run.run_id)
    )
    stale = snap is not None and project_snapshot.is_stale(db, snap)

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
            "project_title": project.title if project else "",
            "funding_profile_id": (
                project.funding_instrument_profile_id if project else ""
            ),
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
        "config_versions": {
            "requirement_registry_version": registry.requirement_registry_version,
            "rule_registry_version": registry.rule_registry_version,
            "portal_field_profile_version": registry.portal_field_profile_version,
            "snapshot_versions": run.snapshot_versions,
        },
    }
    return snapshot, _sha256(canonical_json(snapshot))
