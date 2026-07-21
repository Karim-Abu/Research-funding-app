"""Central RUN 3C staleness checks for manifest-bound suggestions."""
from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisRun, DraftSuggestion, EvidenceAnchor, MarketComparison,
    PortalFieldDraft, Project, RunProjectSnapshot, SourceDocument,
    SuggestionContextManifest,
)
from app.registry.loader import get_registry
from app.runs import project_snapshot


def _hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def reason(
    db: Session, run: AnalysisRun, suggestion: DraftSuggestion
) -> str | None:
    if suggestion.manifest_id is None:
        return suggestion.stale_reason
    manifest = db.get(SuggestionContextManifest, suggestion.manifest_id)
    if manifest is None:
        return "context_manifest_missing"
    draft = db.get(PortalFieldDraft, suggestion.draft_id)
    if draft is None or draft.current_version_id != manifest.base_draft_version_id:
        return "draft_version_changed"
    snapshot = db.get(RunProjectSnapshot, run.run_id)
    if snapshot is None:
        return "run_snapshot_changed"
    primary_version = (snapshot.project_json or {}).get(
        "primary_application_source_version_id"
    )
    if (
        manifest.primary_application_source_version_id is not None
        and primary_version != manifest.primary_application_source_version_id
    ):
        return "primary_application_version_changed"
    project = db.get(Project, run.project_id) if run.project_id else None
    primary_document = (
        db.get(SourceDocument, project.primary_application_source_id)
        if project is not None and project.primary_application_source_id else None
    )
    current_primary_version = (
        primary_document.current_source_version_id if primary_document is not None else None
    )
    if (
        manifest.primary_application_source_version_id is not None
        and project is not None
        and current_primary_version != manifest.primary_application_source_version_id
    ):
        return "primary_application_version_changed"
    if project_snapshot.is_stale(db, snapshot):
        return "run_snapshot_changed"
    registry = get_registry()
    if (
        manifest.requirement_registry_version != registry.requirement_registry_version
        or manifest.rule_registry_version != registry.rule_registry_version
    ):
        return "registry_version_changed"
    field = registry.portal_fields.get(manifest.field_id)
    if field is None:
        return "field_instruction_changed"
    field_view = {
        "field_id": manifest.field_id,
        "label": field.label_or_question,
        "character_limit": field.character_limit,
        "mandatory_questions": [
            item.field_id for item in registry.mandatory_questions(manifest.field_id)
        ],
        "guidance": None,
    }
    if _hash(field_view) != manifest.field_instruction_hash:
        return "field_instruction_changed"
    retained_selected_anchors = set(manifest.selected_anchor_ids or []) - set(
        manifest.omitted_anchor_ids or []
    )
    for anchor_id in sorted(retained_selected_anchors):
        anchor = db.get(EvidenceAnchor, anchor_id)
        if anchor is None or anchor.verification_status not in (
            "exact_verified", "human_verified"
        ):
            return "anchor_changed"
        document = db.get(SourceDocument, anchor.source_id)
        if (
            document is None
            or document.current_source_version_id != anchor.source_version_id
            or anchor.source_version_id not in (manifest.source_version_ids or [])
        ):
            return "source_version_changed"
    if manifest.market_comparison_id:
        comparison = db.get(MarketComparison, manifest.market_comparison_id)
        if (
            comparison is None
            or comparison.status == "stale"
            or comparison.stale_reason is not None
        ):
            return "market_comparison_changed"
    return None
