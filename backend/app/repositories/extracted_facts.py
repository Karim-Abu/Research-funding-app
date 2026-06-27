"""ExtractedFact persistence (Milestone 9B, A1 advisory proposals).

Idempotent insert-if-absent keyed by (run_id, fact_fingerprint). M9B writes only
proposed | conflicted | missing; never confirmed/rejected. Stores provenance refs
and metadata — never full source documents.
"""
from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ExtractedFact

# Statuses A1 may create in M9B (confirmed/rejected require a real HumanDecision).
M9B_STATUSES = ("proposed", "conflicted", "missing")


def fact_fingerprint(
    *, run_id: str, fact_type: str, status: str, value: str, fragment_ids: list[str]
) -> str:
    """Stable identity for a fact within a run → deduplicates repeated execution."""
    payload = "|".join(
        [run_id, status, fact_type, value, ",".join(sorted(fragment_ids))]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def upsert(
    db: Session,
    *,
    run_id: str,
    workspace_id: str,
    fact_type: str,
    normalized_value: str | None,
    original_statement: str,
    status: str,
    requirement_id: str | None,
    field_id: str | None,
    source_fragment_ids: list[str],
    source_version_ids: list[str],
    profile_id: str,
    model_route: str | None,
    model_id: str | None,
    schema_version: str | None,
    prompt_version: str | None,
    agent_invocation_id: str | None,
) -> tuple[ExtractedFact, bool]:
    """Insert the fact if no row with the same (run_id, fingerprint) exists.
    Returns (row, created). Terminal historical facts are never rewritten."""
    fingerprint = fact_fingerprint(
        run_id=run_id, fact_type=fact_type, status=status,
        value=normalized_value or original_statement, fragment_ids=source_fragment_ids,
    )
    existing = db.scalar(
        select(ExtractedFact).where(
            ExtractedFact.run_id == run_id,
            ExtractedFact.fact_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return existing, False

    row = ExtractedFact(
        fact_id=str(uuid.uuid4()),
        run_id=run_id,
        workspace_id=workspace_id,
        fact_type=fact_type,
        normalized_value=normalized_value,
        original_statement=original_statement,
        status=status,
        requirement_id=requirement_id,
        field_id=field_id,
        source_fragment_ids=list(source_fragment_ids),
        source_version_ids=list(source_version_ids),
        profile_id=profile_id,
        model_route=model_route,
        model_id=model_id,
        schema_version=schema_version,
        prompt_version=prompt_version,
        agent_invocation_id=agent_invocation_id,
        fact_fingerprint=fingerprint,
    )
    db.add(row)
    db.flush()
    return row, True


def list_for_run(db: Session, run_id: str) -> list[ExtractedFact]:
    return list(
        db.scalars(
            select(ExtractedFact)
            .where(ExtractedFact.run_id == run_id)
            .order_by(ExtractedFact.created_at, ExtractedFact.fact_id)
        )
    )
