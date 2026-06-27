"""Deterministic UTF-8 technical-evidence JSON export (Milestone 8).

Internal audit artifact. Byte-deterministic for an identical snapshot
(`sort_keys`, fixed indent, `ensure_ascii=false`). Traceability only — no
secrets, sessions, provider payloads, full source text or filesystem paths.
"""
from __future__ import annotations

import json

from app.exports import TECHNICAL_EVIDENCE_SCHEMA
from app.exports.generators.common import NO_SUBMISSION


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
            "type": meta["export_type"],
            "run_id": meta["run_id"],
            "project_id": meta["project_id"],
            "project_title": meta["project_title"],
            "funding_profile_id": meta["funding_profile_id"],
            "funding_profile_version": meta["funding_profile_version"],
            "created_by": meta["created_by"],
            "frozen_at": meta["frozen_at"],
            "effective_data_classification": meta["effective_data_classification"],
        },
        "coverage": snapshot["coverage"],
        "review": snapshot["review"],
        "fields": [
            {
                "field_id": f["field_id"],
                "draft_version_id": f["draft_version_id"],
                "content_hash": f["content_hash"],
                "character_count": f["character_count"],
                "character_limit": f["character_limit"],
                "text": f["text"],
                "evidence_links": f["evidence_links"],
            }
            for f in snapshot["fields"]
        ],
        "requirement_assessments": snapshot["requirements"],
        "rule_results": snapshot["rule_results"],
        "open_issues": snapshot["open_issues"],
        "evidence_anchors": snapshot["evidence_anchors"],
        "evidence_links": snapshot["evidence_links"],
        "review_findings": snapshot["review_findings"],
        "human_decisions": snapshot["human_decisions"],
        "config_versions": snapshot["config_versions"],
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
    return (text + "\n").encode("utf-8")
