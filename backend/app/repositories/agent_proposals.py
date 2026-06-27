"""Agent evidence-proposal trail (Milestone 9C, internal — no OpenAPI exposure).

Records, for each A1.evidence_candidate_mapping proposal, whether it was newly
persisted, deduplicated against an existing candidate, or rejected — plus the
post-verify verification status and post-link assessment — for later
baseline-vs-agent evaluation.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AgentEvidenceProposal,
    AnalysisRun,
    EvidenceAnchor,
    EvidenceCandidate,
    EvidenceLink,
)


def record(
    db: Session,
    run: AnalysisRun,
    *,
    agent_invocation_id: str | None,
    profile_id: str,
    prompt_version: str | None,
    outcome: str,  # persisted_new | deduplicated | rejected
    target_requirement_id: str | None = None,
    fragment_id: str | None = None,
    quote_hash: str | None = None,
    candidate_id: str | None = None,
    existing_candidate_id: str | None = None,
    duplicate_of_deterministic: bool | None = None,
    duplicate_reason: str | None = None,
    rejection_reason: str | None = None,
) -> AgentEvidenceProposal:
    proposal = AgentEvidenceProposal(
        proposal_id=str(uuid.uuid4()),
        run_id=run.run_id,
        workspace_id=run.workspace_id,
        agent_invocation_id=agent_invocation_id,
        profile_id=profile_id,
        prompt_version=prompt_version,
        target_requirement_id=target_requirement_id,
        fragment_id=fragment_id,
        quote_hash=quote_hash,
        proposed_by_agent=True,
        outcome=outcome,
        candidate_id=candidate_id,
        existing_candidate_id=existing_candidate_id,
        duplicate_of_deterministic=duplicate_of_deterministic,
        duplicate_reason=duplicate_reason,
        rejection_reason=rejection_reason,
    )
    db.add(proposal)
    db.flush()
    return proposal


def list_for_run(db: Session, run_id: str) -> list[AgentEvidenceProposal]:
    return list(
        db.scalars(
            select(AgentEvidenceProposal).where(
                AgentEvidenceProposal.run_id == run_id
            )
        )
    )


def backfill_outcomes(db: Session, run: AnalysisRun) -> int:
    """After the deterministic verify + link stages, fill each proposal's
    ``verification_status`` (from its candidate's anchor) and ``linked_assessment_id``
    (from the requirement-assessment EvidenceLink). Idempotent; safe under replay."""
    updated = 0
    for proposal in list_for_run(db, run.run_id):
        if proposal.candidate_id is None:
            continue
        candidate = db.get(EvidenceCandidate, proposal.candidate_id)
        if candidate is None or candidate.anchor_id is None:
            continue
        anchor = db.get(EvidenceAnchor, candidate.anchor_id)
        if anchor is not None:
            proposal.verification_status = anchor.verification_status
        link = db.scalar(
            select(EvidenceLink).where(
                EvidenceLink.anchor_id == candidate.anchor_id,
                EvidenceLink.target_type == "requirement_assessment",
                EvidenceLink.status == "active",
            )
        )
        if link is not None:
            proposal.linked_assessment_id = link.target_id
        updated += 1
    db.flush()
    return updated
