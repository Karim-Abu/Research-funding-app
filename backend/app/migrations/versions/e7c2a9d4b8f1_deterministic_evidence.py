"""Milestone 5 — deterministic evidence: candidates, anchors, links.

Revision ID: e7c2a9d4b8f1
Revises: d3a1b6e4f2c7
Create Date: 2026-06-23
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7c2a9d4b8f1"
down_revision: Union[str, None] = "d3a1b6e4f2c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evidence_candidates",
        sa.Column("candidate_id", sa.String(), primary_key=True),
        sa.Column(
            "run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id"),
            nullable=False, index=True,
        ),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_requirement_id", sa.String(), nullable=False),
        sa.Column("fragment_id", sa.String(), nullable=False),
        sa.Column("source_version_id", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("proposed_quote", sa.Text(), nullable=False),
        sa.Column("quote_hash", sa.String(), nullable=False),
        sa.Column("span_start_in_fragment", sa.Integer(), nullable=False),
        sa.Column("span_end_in_fragment", sa.Integer(), nullable=False),
        sa.Column("match_type", sa.String(), nullable=False),
        sa.Column("retrieval_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("retrieval_algorithm_version", sa.String(), nullable=False),
        sa.Column("anchor_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "run_id", "target_requirement_id", "fragment_id", "quote_hash",
            name="uq_candidate_run_target_fragment_quote",
        ),
    )

    op.create_table(
        "evidence_anchors",
        sa.Column("anchor_id", sa.String(), primary_key=True),
        sa.Column(
            "run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id"),
            nullable=False, index=True,
        ),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("source_version_id", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("source_name", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("fragment_id", sa.String(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("quote_hash", sa.String(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(), nullable=True),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.Column("match_type", sa.String(), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("coverage", sa.Float(), nullable=True),
        sa.Column("normalizer_version", sa.String(), nullable=False),
        sa.Column("verification_status", sa.String(), nullable=False),
        sa.Column("human_checked_by", sa.String(), nullable=True),
        sa.Column("human_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "run_id", "source_version_id", "start_offset", "end_offset",
            "quote_hash", name="uq_anchor_run_version_offsets_quote",
        ),
    )

    op.create_table(
        "evidence_links",
        sa.Column("evidence_link_id", sa.String(), primary_key=True),
        sa.Column(
            "run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id"),
            nullable=False, index=True,
        ),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column(
            "anchor_id", sa.String(), sa.ForeignKey("evidence_anchors.anchor_id"),
            nullable=False, index=True,
        ),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("claim_id", sa.String(), nullable=True),
        sa.Column("claim_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "anchor_id", "target_type", "target_id", name="uq_link_anchor_target"
        ),
    )


def downgrade() -> None:
    op.drop_table("evidence_links")
    op.drop_table("evidence_anchors")
    op.drop_table("evidence_candidates")
