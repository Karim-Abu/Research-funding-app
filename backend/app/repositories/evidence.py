"""Evidence persistence (upsert-only, immutable) + deterministic read model.

Never deletes or rewrites a run's artifacts: persistence is insert-if-not-exists
on stable uniqueness keys, so a terminal run stays immutable and re-execution
(checkpoint replay) produces no duplicates. A new evaluation needs a new run.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.evidence import EvidenceAnchor as AnchorSchema
from app.contracts.evidence import EvidenceLink as LinkSchema
from app.db.models import (
    AnalysisRun,
    EvidenceAnchor,
    EvidenceCandidate,
    EvidenceLink,
    SourceVersion,
)
from app.evidence.discovery import RETRIEVAL_ALGORITHM_VERSION, CandidateSpec
from app.evidence.verification import VerificationOutcome

_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


# --- candidates ------------------------------------------------------------


def upsert_candidate(
    db: Session, run: AnalysisRun, spec: CandidateSpec
) -> EvidenceCandidate:
    existing = db.scalar(
        select(EvidenceCandidate).where(
            EvidenceCandidate.run_id == run.run_id,
            EvidenceCandidate.target_requirement_id == spec.target_requirement_id,
            EvidenceCandidate.fragment_id == spec.fragment_id,
            EvidenceCandidate.quote_hash == spec.quote_hash,
        )
    )
    if existing is not None:
        return existing
    candidate = EvidenceCandidate(
        candidate_id=str(uuid.uuid4()),
        run_id=run.run_id,
        workspace_id=run.workspace_id,
        target_type="requirement",
        target_requirement_id=spec.target_requirement_id,
        fragment_id=spec.fragment_id,
        source_version_id=spec.source_version_id,
        source_id=spec.source_id,
        proposed_quote=spec.proposed_quote,
        quote_hash=spec.quote_hash,
        span_start_in_fragment=spec.span_start_in_fragment,
        span_end_in_fragment=spec.span_end_in_fragment,
        match_type="exact_normalized",
        retrieval_score=spec.retrieval_score,
        status="proposed",
        retrieval_algorithm_version=RETRIEVAL_ALGORITHM_VERSION,
    )
    db.add(candidate)
    db.flush()
    return candidate


def list_candidates_for_run(db: Session, run_id: str) -> list[EvidenceCandidate]:
    return list(
        db.scalars(
            select(EvidenceCandidate).where(EvidenceCandidate.run_id == run_id)
        )
    )


# --- anchors ---------------------------------------------------------------


def _find_anchor(
    db: Session,
    run_id: str,
    source_version_id: str,
    quote_hash: str,
    start: int | None,
    end: int | None,
) -> EvidenceAnchor | None:
    # Python-side comparison so NULL offsets (unverified) dedup correctly while
    # distinct occurrences of an identical quote stay separate.
    rows = db.scalars(
        select(EvidenceAnchor).where(
            EvidenceAnchor.run_id == run_id,
            EvidenceAnchor.source_version_id == source_version_id,
            EvidenceAnchor.quote_hash == quote_hash,
        )
    )
    for anchor in rows:
        if anchor.start_offset == start and anchor.end_offset == end:
            return anchor
    return None


def upsert_anchor(
    db: Session,
    run: AnalysisRun,
    candidate: EvidenceCandidate,
    outcome: VerificationOutcome,
) -> EvidenceAnchor:
    existing = _find_anchor(
        db, run.run_id, candidate.source_version_id, candidate.quote_hash,
        outcome.start_offset, outcome.end_offset,
    )
    if existing is not None:
        return existing
    version = db.get(SourceVersion, candidate.source_version_id)
    # Canonical source-acquisition timestamp for a local source.
    source_accessed_at = version.created_at if version is not None else None
    anchor = EvidenceAnchor(
        anchor_id=str(uuid.uuid4()),
        run_id=run.run_id,
        workspace_id=run.workspace_id,
        source_version_id=candidate.source_version_id,
        source_id=candidate.source_id,
        source_name=_source_name(db, candidate),
        source_type=_source_type(db, candidate),
        fragment_id=candidate.fragment_id,
        quote=candidate.proposed_quote,
        quote_hash=candidate.quote_hash,
        page=_fragment_page(db, candidate),
        section=_fragment_section(db, candidate),
        start_offset=outcome.start_offset,
        end_offset=outcome.end_offset,
        match_type=outcome.match_type,
        match_score=None,  # M5: contract semantics undefined for exactness
        coverage=None,
        normalizer_version=version.normalizer_version if version else "",
        verification_status=outcome.verification_status,
        human_checked_by=None,
        human_checked_at=None,
        source_accessed_at=source_accessed_at,
    )
    db.add(anchor)
    db.flush()
    return anchor


# Anchor metadata is denormalised from the run-frozen fragment/source at create
# time (the snapshot is immutable, so this never goes stale within the run).
def _fragment(db, candidate):
    from app.db.models import SourceFragment

    return db.get(SourceFragment, candidate.fragment_id)


def _fragment_page(db, candidate):
    fragment = _fragment(db, candidate)
    return fragment.page if fragment else None


def _fragment_section(db, candidate):
    fragment = _fragment(db, candidate)
    return fragment.section if fragment else None


def _source_name(db, candidate):
    from app.db.models import SourceDocument

    document = db.get(SourceDocument, candidate.source_id)
    return document.name if document else ""


def _source_type(db, candidate):
    from app.db.models import SourceDocument

    document = db.get(SourceDocument, candidate.source_id)
    return document.type if document else "txt"


def list_anchors_for_run(db: Session, run_id: str) -> list[EvidenceAnchor]:
    """Explicit deterministic order computed in code (corr. #4): canonical
    source-acquisition order then page, start_offset, anchor_id."""
    anchors = list(
        db.scalars(select(EvidenceAnchor).where(EvidenceAnchor.run_id == run_id))
    )
    anchors.sort(
        key=lambda a: (
            a.source_accessed_at is None,
            a.source_accessed_at or _EPOCH,
            a.source_id,
            a.page if a.page is not None else -1,
            a.start_offset if a.start_offset is not None else -1,
            a.anchor_id,
        )
    )
    return anchors


# --- links -----------------------------------------------------------------


def upsert_link(
    db: Session, run: AnalysisRun, anchor_id: str, assessment_id: str
) -> EvidenceLink:
    existing = db.scalar(
        select(EvidenceLink).where(
            EvidenceLink.anchor_id == anchor_id,
            EvidenceLink.target_type == "requirement_assessment",
            EvidenceLink.target_id == assessment_id,
        )
    )
    if existing is not None:
        return existing
    link = EvidenceLink(
        evidence_link_id=str(uuid.uuid4()),
        run_id=run.run_id,
        workspace_id=run.workspace_id,
        anchor_id=anchor_id,
        target_type="requirement_assessment",
        target_id=assessment_id,
        claim_id=None,
        claim_text=None,
        status="active",
    )
    db.add(link)
    db.flush()
    return link


# --- draft-version links (Milestone 6) -------------------------------------


def upsert_draft_link(
    db: Session, run: AnalysisRun, anchor_id: str, draft_version_id: str
) -> EvidenceLink:
    """Link an anchor to a current draft version (active). Idempotent."""
    existing = db.scalar(
        select(EvidenceLink).where(
            EvidenceLink.anchor_id == anchor_id,
            EvidenceLink.target_type == "draft_version",
            EvidenceLink.target_id == draft_version_id,
        )
    )
    if existing is not None:
        if existing.status == "removed":
            existing.status = "active"
        return existing
    link = EvidenceLink(
        evidence_link_id=str(uuid.uuid4()),
        run_id=run.run_id,
        workspace_id=run.workspace_id,
        anchor_id=anchor_id,
        target_type="draft_version",
        target_id=draft_version_id,
        claim_id=None,
        claim_text=None,
        status="active",
    )
    db.add(link)
    db.flush()
    return link


def mark_draft_version_links_stale(db: Session, draft_version_id: str) -> int:
    """A new draft version supersedes the old one — active links targeting the
    previous version become stale (never copied forward)."""
    count = 0
    for link in db.scalars(
        select(EvidenceLink).where(
            EvidenceLink.target_type == "draft_version",
            EvidenceLink.target_id == draft_version_id,
            EvidenceLink.status == "active",
        )
    ):
        link.status = "stale"
        count += 1
    return count


def get_link_scoped(
    db: Session, evidence_link_id: str, run_id: str
) -> EvidenceLink | None:
    return db.scalar(
        select(EvidenceLink).where(
            EvidenceLink.evidence_link_id == evidence_link_id,
            EvidenceLink.run_id == run_id,
        )
    )


def remove_link(db: Session, link: EvidenceLink) -> None:
    """Preserve history: active/stale → removed (no physical delete)."""
    link.status = "removed"
    db.flush()


def links_for_draft_versions(
    db: Session, version_ids: list[str]
) -> list[EvidenceLink]:
    if not version_ids:
        return []
    links = list(
        db.scalars(
            select(EvidenceLink).where(
                EvidenceLink.target_type == "draft_version",
                EvidenceLink.target_id.in_(version_ids),
            )
        )
    )
    links.sort(key=lambda link: link.created_at)
    return links


def links_by_assessment(db: Session, run_id: str) -> dict[str, list[EvidenceLink]]:
    grouped: dict[str, list[EvidenceLink]] = {}
    rows = db.scalars(
        select(EvidenceLink).where(
            EvidenceLink.run_id == run_id,
            EvidenceLink.target_type == "requirement_assessment",
        )
    )
    for link in rows:
        grouped.setdefault(link.target_id, []).append(link)
    for links in grouped.values():
        links.sort(key=lambda link: link.created_at)
    return grouped


# --- contract mapping ------------------------------------------------------


def to_anchor_contract(anchor: EvidenceAnchor) -> AnchorSchema:
    return AnchorSchema(
        anchor_id=anchor.anchor_id,
        source_version_id=anchor.source_version_id,
        fragment_id=anchor.fragment_id,
        quote=anchor.quote,
        verification_status=anchor.verification_status,
        source_id=anchor.source_id,
        source_name=anchor.source_name,
        source_type=anchor.source_type,
        normalizer_version=anchor.normalizer_version,
        page=anchor.page,
        section=anchor.section,
        match_type=anchor.match_type,
        human_checked_by=anchor.human_checked_by,
        human_checked_at=anchor.human_checked_at,
        start_offset=anchor.start_offset,
        end_offset=anchor.end_offset,
        match_score=anchor.match_score,
        coverage=anchor.coverage,
        source_accessed_at=anchor.source_accessed_at,
    )


def to_link_contract(link: EvidenceLink) -> LinkSchema:
    return LinkSchema(
        evidence_link_id=link.evidence_link_id,
        anchor_id=link.anchor_id,
        target_type=link.target_type,
        target_id=link.target_id,
        status=link.status,
        created_at=link.created_at,
        claim_id=link.claim_id,
        claim_text=link.claim_text,
    )
