"""Milestone 9C — A1 evidence mapping: candidate origin + agent proposal trail.

Revision ID: f3c5d7e9a1b2
Revises: e1b7f3a9c2d4
Create Date: 2026-06-27
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3c5d7e9a1b2"
down_revision: Union[str, None] = "e1b7f3a9c2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evidence_candidates",
        sa.Column(
            "generation_origin", sa.String(), nullable=False,
            server_default="deterministic_lexical",
        ),
    )
    op.add_column(
        "evidence_candidates",
        sa.Column("agent_invocation_id", sa.String(), nullable=True),
    )
    op.add_column(
        "evidence_candidates", sa.Column("profile_id", sa.String(), nullable=True)
    )
    op.add_column(
        "evidence_candidates", sa.Column("prompt_version", sa.String(), nullable=True)
    )
    op.add_column(
        "evidence_candidates",
        sa.Column("source_extracted_fact_id", sa.String(), nullable=True),
    )
    op.create_table(
        "agent_evidence_proposals",
        sa.Column("proposal_id", sa.String(), primary_key=True),
        sa.Column(
            "run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id"),
            nullable=False, index=True,
        ),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("agent_invocation_id", sa.String(), nullable=True),
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("prompt_version", sa.String(), nullable=True),
        sa.Column("target_requirement_id", sa.String(), nullable=True),
        sa.Column("fragment_id", sa.String(), nullable=True),
        sa.Column("quote_hash", sa.String(), nullable=True),
        sa.Column("proposed_by_agent", sa.Boolean(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("candidate_id", sa.String(), nullable=True),
        sa.Column("existing_candidate_id", sa.String(), nullable=True),
        sa.Column("duplicate_of_deterministic", sa.Boolean(), nullable=True),
        sa.Column("duplicate_reason", sa.String(), nullable=True),
        sa.Column("rejection_reason", sa.String(), nullable=True),
        sa.Column("verification_status", sa.String(), nullable=True),
        sa.Column("linked_assessment_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("agent_evidence_proposals")
    op.drop_column("evidence_candidates", "source_extracted_fact_id")
    op.drop_column("evidence_candidates", "prompt_version")
    op.drop_column("evidence_candidates", "profile_id")
    op.drop_column("evidence_candidates", "agent_invocation_id")
    op.drop_column("evidence_candidates", "generation_origin")
