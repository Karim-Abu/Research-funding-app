"""A2 DraftSuggestion persistence (internal — no OpenAPI exposure).

Advisory proposals with explicit generation provenance. Immutable except the
status/decision fields; only an accepted suggestion creates a DraftVersion.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalysisRun, DraftSuggestion
from app.agents import missing_inputs as missing_input_service

# Statuses A2 may create / transition to.
PROPOSED = "proposed"
ACCEPTED = "accepted"
REJECTED = "rejected"
EXPIRED = "expired"
FAILED = "failed"


def content_hash(text: str) -> str:
    """Same hashing as DraftVersion content_hash, so accept can compare exactly."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create(
    db: Session,
    run: AnalysisRun,
    *,
    draft_id: str,
    base_version_id: str,
    field_id: str,
    profile_id: str,
    operation_id: str,
    agent_invocation_id: str | None,
    prompt_version: str | None,
    model_route: str | None,
    model_id: str | None,
    generation_kind: str,
    target_section: str | None,
    section_result_json: dict | None,
    suggested_text: str,
    rationale: str | None,
    evidence_anchor_ids: list[str],
    open_issue_ids: list[str],
    placeholders: list,
    character_count: int,
    manifest_id: str | None = None,
    improvement_mode: str | None = None,
    change_summary: list | None = None,
    used_rule_ids: list[str] | None = None,
    missing_inputs: list | None = None,
    unsupported_claim_warnings: list | None = None,
    factual_claims: list | None = None,
    source_version_ids: list[str] | None = None,
    market_comparison_id: str | None = None,
    registry_version: str | None = None,
    output_schema_version: str | None = None,
    context_hash: str | None = None,
    quality_state: str | None = None,
    accept_mode: str = "legacy_partial",
) -> DraftSuggestion:
    suggestion = DraftSuggestion(
        suggestion_id=str(uuid.uuid4()),
        run_id=run.run_id,
        workspace_id=run.workspace_id,
        draft_id=draft_id,
        base_version_id=base_version_id,
        field_id=field_id,
        profile_id=profile_id,
        operation_id=operation_id,
        agent_invocation_id=agent_invocation_id,
        prompt_version=prompt_version,
        model_route=model_route,
        model_id=model_id,
        generation_kind=generation_kind,
        target_section=target_section,
        section_result_json=(dict(section_result_json) if section_result_json else None),
        status=PROPOSED,
        suggested_text=suggested_text,
        rationale=rationale,
        evidence_anchor_ids=list(evidence_anchor_ids),
        open_issue_ids=list(open_issue_ids),
        placeholders=list(placeholders),
        content_hash=content_hash(suggested_text),
        character_count=character_count,
        project_id=run.project_id,
        manifest_id=manifest_id,
        improvement_mode=improvement_mode,
        change_summary=list(change_summary or []),
        used_rule_ids=list(used_rule_ids or []),
        missing_inputs=list(missing_inputs or []),
        unsupported_claim_warnings=list(unsupported_claim_warnings or []),
        factual_claims=list(factual_claims or []),
        source_version_ids=list(source_version_ids or []),
        market_comparison_id=market_comparison_id,
        registry_version=registry_version,
        output_schema_version=output_schema_version,
        context_hash=context_hash,
        quality_state=quality_state,
        accept_mode=accept_mode,
    )
    db.add(suggestion)
    db.flush()
    return suggestion


def get_by_operation(db: Session, operation_id: str) -> DraftSuggestion | None:
    return db.scalar(
        select(DraftSuggestion).where(DraftSuggestion.operation_id == operation_id)
    )


def get_scoped(
    db: Session, suggestion_id: str, *, run_id: str, workspace_id: str
) -> DraftSuggestion | None:
    return db.scalar(
        select(DraftSuggestion).where(
            DraftSuggestion.suggestion_id == suggestion_id,
            DraftSuggestion.run_id == run_id,
            DraftSuggestion.workspace_id == workspace_id,
        )
    )


def get_proposed_for(
    db: Session, run_id: str, draft_id: str, base_version_id: str,
    target_section: str | None = None,
) -> DraftSuggestion | None:
    """For replay/idempotency: a still-proposed suggestion for this exact base."""
    return db.scalar(
        select(DraftSuggestion).where(
            DraftSuggestion.run_id == run_id,
            DraftSuggestion.draft_id == draft_id,
            DraftSuggestion.base_version_id == base_version_id,
            DraftSuggestion.target_section == target_section,
            DraftSuggestion.status == PROPOSED,
        )
    )


def list_proposed_for(
    db: Session, run_id: str, draft_id: str, base_version_id: str
) -> list[DraftSuggestion]:
    """All field/section suggestions for one exact immutable base version."""
    return list(
        db.scalars(
            select(DraftSuggestion)
            .where(
                DraftSuggestion.run_id == run_id,
                DraftSuggestion.draft_id == draft_id,
                DraftSuggestion.base_version_id == base_version_id,
                DraftSuggestion.status == PROPOSED,
            )
            .order_by(DraftSuggestion.target_section, DraftSuggestion.created_at)
        )
    )


def mark_accepted(
    db: Session,
    suggestion: DraftSuggestion,
    *,
    accepted_draft_version_id: str,
    decided_by: str | None,
) -> None:
    suggestion.status = ACCEPTED
    suggestion.accepted_draft_version_id = accepted_draft_version_id
    suggestion.decided_at = _now()
    suggestion.decided_by = decided_by
    db.flush()


def mark_rejected(
    db: Session,
    suggestion: DraftSuggestion,
    *,
    decided_by: str | None,
) -> None:
    """C4 — ausdrückliche menschliche Ablehnung (HumanDecision-Pfad).

    Nur der Entscheid wird festgehalten (Status + decided_at/decided_by);
    der Vorschlagstext bleibt unverändert erhalten.
    """
    suggestion.status = REJECTED
    suggestion.decided_at = _now()
    suggestion.decided_by = decided_by
    db.flush()


def expire_superseded(db: Session, draft_id: str, current_base_version_id: str) -> int:
    """Mark proposed suggestions for a draft whose base no longer matches as
    expired (a newer DraftVersion supersedes them)."""
    count = 0
    for suggestion in db.scalars(
        select(DraftSuggestion).where(
            DraftSuggestion.draft_id == draft_id,
            DraftSuggestion.status == PROPOSED,
            DraftSuggestion.base_version_id != current_base_version_id,
        )
    ):
        suggestion.status = EXPIRED
        suggestion.stale_reason = "draft_version_changed"
        suggestion.decided_at = _now()
        missing_input_service.mark_suggestion_issues_stale(
            db, suggestion.suggestion_id, reason="draft_version_changed"
        )
        count += 1
    db.flush()
    return count
