"""Exact verification and External-Evidence anchoring for market facts.

Only current, reviewed imported source fragments are eligible. Search snippets and
provider payloads never enter this verifier.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    EvidenceAnchor,
    EvidenceLink,
    SourceDocument,
    SourceFragment,
    SourceVersion,
)
from app.evidence.discovery import quote_hash

VERIFICATION_METHOD = "deterministic_position_match"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def verify_quote(
    db: Session,
    *,
    fragment: SourceFragment,
    source_document_id: str,
    quote: str,
    project_id: str | None = None,
    workspace_id: str | None = None,
    research_task_id: str | None = None,
    target_id: str | None = None,
) -> dict | None:
    candidate = (quote or "").strip()
    if not candidate:
        return None
    local = (fragment.normalized_text or "").find(candidate)
    if local < 0:
        return None
    version = db.get(SourceVersion, fragment.source_version_id)
    if version is None or version.normalized_text is None:
        return None
    start = fragment.start_offset + local
    end = start + len(candidate)
    if not 0 <= start <= end <= len(version.normalized_text):
        return None
    if version.normalized_text[start:end] != candidate:
        return None

    qhash = quote_hash(candidate)
    anchor_id = _existing_anchor_id(db, version.source_version_id, start, end, qhash)
    if project_id and workspace_id:
        document = db.get(SourceDocument, source_document_id)
        if (
            document is None
            or document.project_id != project_id
            or document.workspace_id != workspace_id
            or document.current_source_version_id != version.source_version_id
            or version.content_review_status != "reviewed"
            or version.content_safety_status not in ("passed", "human_released")
        ):
            return None
        anchor_id = _ensure_external_anchor(
            db,
            document=document,
            version=version,
            fragment=fragment,
            quote=candidate,
            qhash=qhash,
            start=start,
            end=end,
            project_id=project_id,
            workspace_id=workspace_id,
            research_task_id=research_task_id,
        )
        if target_id:
            _ensure_link(
                db, anchor_id=anchor_id, workspace_id=workspace_id, target_id=target_id
            )

    return {
        "source_document_id": source_document_id,
        "source_version_id": version.source_version_id,
        "fragment_id": fragment.fragment_id,
        "quote": candidate,
        "start_char": start,
        "end_char": end,
        "quote_hash": qhash,
        "normalizer_version": version.normalizer_version,
        "verification_method": VERIFICATION_METHOD,
        "verified_at": _now_iso(),
        "linked_evidence_anchor_id": anchor_id,
    }


def _existing_anchor_id(
    db: Session, source_version_id: str, start: int, end: int, qhash: str
) -> str | None:
    return db.scalar(select(EvidenceAnchor.anchor_id).where(
        EvidenceAnchor.source_version_id == source_version_id,
        EvidenceAnchor.start_offset == start,
        EvidenceAnchor.end_offset == end,
        EvidenceAnchor.quote_hash == qhash,
        EvidenceAnchor.verification_status == "exact_verified",
    ))


def _ensure_external_anchor(
    db: Session,
    *,
    document: SourceDocument,
    version: SourceVersion,
    fragment: SourceFragment,
    quote: str,
    qhash: str,
    start: int,
    end: int,
    project_id: str,
    workspace_id: str,
    research_task_id: str | None,
) -> str:
    existing = db.scalar(select(EvidenceAnchor).where(
        EvidenceAnchor.run_id.is_(None),
        EvidenceAnchor.project_id == project_id,
        EvidenceAnchor.workspace_id == workspace_id,
        EvidenceAnchor.source_version_id == version.source_version_id,
        EvidenceAnchor.start_offset == start,
        EvidenceAnchor.end_offset == end,
        EvidenceAnchor.quote_hash == qhash,
        EvidenceAnchor.scope == "external",
    ))
    if existing is not None:
        return existing.anchor_id
    anchor = EvidenceAnchor(
        anchor_id=str(uuid.uuid4()),
        run_id=None,
        project_id=project_id,
        research_task_id=research_task_id,
        workspace_id=workspace_id,
        source_version_id=version.source_version_id,
        source_id=document.source_id,
        source_name=document.name,
        source_type=document.type,
        fragment_id=fragment.fragment_id,
        quote=quote,
        quote_hash=qhash,
        page=fragment.page,
        section=fragment.section,
        start_offset=start,
        end_offset=end,
        match_type="exact_normalized",
        match_score=None,
        coverage=None,
        normalizer_version=version.normalizer_version or "",
        verification_status="exact_verified",
        scope="external",
        source_accessed_at=version.created_at,
    )
    db.add(anchor)
    db.flush()
    return anchor.anchor_id


def _ensure_link(
    db: Session, *, anchor_id: str, workspace_id: str, target_id: str
) -> None:
    existing = db.scalar(select(EvidenceLink).where(
        EvidenceLink.anchor_id == anchor_id,
        EvidenceLink.target_type == "market_comparison_item",
        EvidenceLink.target_id == target_id,
    ))
    if existing is None:
        db.add(EvidenceLink(
            evidence_link_id=str(uuid.uuid4()),
            run_id=None,
            workspace_id=workspace_id,
            anchor_id=anchor_id,
            target_type="market_comparison_item",
            target_id=target_id,
            status="active",
        ))
