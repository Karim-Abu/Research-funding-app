"""Redacted technical evidence artifact (technical-evidence-2).

It is traceable by IDs, hashes and safe counts, but deliberately excludes every
proposal, project, quote, review-description and free-text-comment payload.
"""
from __future__ import annotations

import hashlib
import json

from app.exports import TECHNICAL_EVIDENCE_SCHEMA
from app.exports.generators.common import NO_SUBMISSION


def _hash(value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _requirements(snapshot: dict) -> list[dict]:
    return [
        {
            "requirement_id": item.get("requirement_id"), "status": item.get("status"),
            "severity": item.get("severity"), "basis": item.get("basis"),
            "evidence_status": item.get("evidence_status"),
            "detail_hash": _hash(item),
        }
        for item in snapshot.get("requirements", [])
    ]


def generate_technical_evidence(snapshot: dict, snapshot_hash: str) -> bytes:
    meta = snapshot["meta"]
    payload = {
        "artifact_kind": "internal_audit_export",
        "schema": TECHNICAL_EVIDENCE_SCHEMA,
        "disclaimer": NO_SUBMISSION,
        "draft_marked": meta["draft_marked"],
        "draft_reasons": meta["draft_reasons"],
        "snapshot_hash": snapshot_hash,
        "export": {
            "type": meta["export_type"], "run_id": meta["run_id"],
            "project_id": meta["project_id"], "funding_profile_version": meta["funding_profile_version"],
            "created_by": meta["created_by"], "frozen_at": meta["frozen_at"],
            "effective_data_classification": meta["effective_data_classification"],
        },
        "structured_snapshot": {
            "available": snapshot["structured"].get("snapshot_available", False),
            "stale": snapshot["structured"].get("stale", False),
            "run_project_snapshot_hash": snapshot["structured"].get("snapshot_hash"),
            "partner_count": len(snapshot["structured"].get("partners", [])),
            "budget_value_count": len(snapshot["structured"].get("budget", {}).get("values", [])),
            "source_count": len(snapshot["structured"].get("sources", [])),
        },
        "coverage": {
            "supported_field_ids": snapshot["coverage"]["supported_field_ids"],
            "deferred_area_count": len(snapshot["coverage"].get("deferred_areas", [])),
        },
        "review": {
            "review_package_version": snapshot["review"].get("review_package_version"),
            "approval_scope_hash": snapshot["review"].get("approval_scope_hash"),
            "approval_status": snapshot["review"].get("approval_status"),
            "blocker_count": snapshot["review"].get("blocker_count"),
            "warning_count": snapshot["review"].get("warning_count"),
            "approval": snapshot["review"].get("approval"),
        },
        "fields": [
            {
                "field_id": f["field_id"], "draft_id": f["draft_id"],
                "draft_version_id": f["draft_version_id"], "content_hash": f["content_hash"],
                "character_count": f["character_count"], "character_limit": f["character_limit"],
                "created_by": f["created_by"], "evidence_links": f["evidence_links"],
                "open_issue_count": len(f.get("open_issues", [])),
            }
            for f in snapshot["fields"]
        ],
        "requirement_assessments": _requirements(snapshot),
        "rule_results": snapshot["rule_results"],
        "open_issues": [
            {"issue_id": i.get("issue_id"), "target_type": i.get("target_type"), "target_id": i.get("target_id"),
             "severity": i.get("severity"), "description_hash": _hash(i.get("description", ""))}
            for i in snapshot.get("open_issues", [])
        ],
        "evidence_anchors": [
            {"anchor_id": a["anchor_id"], "source_id": a["source_id"], "source_version_id": a["source_version_id"],
             "fragment_id": a["fragment_id"], "quote_hash": _hash(a.get("quote", "")),
             "verification_status": a.get("verification_status"), "support_status": a.get("support_status"),
             "page": a.get("page"), "section_hash": _hash(a.get("section", ""))}
            for a in snapshot.get("evidence_anchors", [])
        ],
        "evidence_links": [
            {key: link.get(key) for key in ("evidence_link_id", "anchor_id", "target_type", "target_id", "status", "claim_id", "support_status")}
            for link in snapshot.get("evidence_links", [])
        ],
        "review_findings": [
            {"finding_id": f["finding_id"], "field_id": f.get("field_id"), "requirement_id": f.get("requirement_id"),
             "severity": f["severity"], "status": f["status"], "source": f["source"],
             "description_hash": _hash(f.get("description", ""))}
            for f in snapshot.get("review_findings", [])
        ],
        "human_decisions": [
            {"decision_id": d["decision_id"], "target_type": d["target_type"], "target_id": d["target_id"],
             "action": d["action"], "comment_hash": _hash(d.get("comment", "")), "created_at": d["created_at"]}
            for d in snapshot.get("human_decisions", [])
        ],
        "reliability": snapshot.get("reliability", {"available": False}),
        "technical_trace": snapshot.get("technical_trace", {}),
        "config_versions": snapshot["config_versions"],
    }
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
