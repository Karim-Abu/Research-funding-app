"""Milestone 9K — MAS reliability tables (beta-internal, run-scoped).

Revision ID: f3d7a9c2e5b1
Revises: e2b6c4f8a1d3
Create Date: 2026-07-02
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3d7a9c2e5b1"
down_revision: Union[str, None] = "e2b6c4f8a1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "draft_claims",
        sa.Column("claim_id", sa.String(), primary_key=True),
        sa.Column(
            "run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id"),
            nullable=False, index=True,
        ),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("draft_id", sa.String(), nullable=False),
        sa.Column("draft_version_id", sa.String(), nullable=False),
        sa.Column("field_id", sa.String(), nullable=False, index=True),
        sa.Column("start_char", sa.Integer(), nullable=False),
        sa.Column("end_char", sa.Integer(), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(), nullable=False),
        sa.Column("strength", sa.String(), nullable=False),
        sa.Column("requires_evidence", sa.Boolean(), nullable=False),
        sa.Column("extraction_method", sa.String(), nullable=False),
        sa.Column("source_text_hash", sa.String(), nullable=False),
        sa.Column("source_scope_hash", sa.String(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "claim_lineages",
        sa.Column("lineage_id", sa.String(), primary_key=True),
        sa.Column(
            "claim_id", sa.String(), sa.ForeignKey("draft_claims.claim_id"),
            nullable=False, index=True,
        ),
        sa.Column("run_id", sa.String(), nullable=False, index=True),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("lineage_status", sa.String(), nullable=False),
        sa.Column("sufficiency_status", sa.String(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("matched_terms", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "run_quality_summaries",
        sa.Column("summary_id", sa.String(), primary_key=True),
        sa.Column(
            "run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id"),
            nullable=False, index=True,
        ),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("operation_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("source_scope_hash", sa.String(), nullable=False, index=True),
        sa.Column("claim_count", sa.Integer(), nullable=False),
        sa.Column("supported_claims", sa.Integer(), nullable=False),
        sa.Column("weakly_supported_claims", sa.Integer(), nullable=False),
        sa.Column("unsupported_claims", sa.Integer(), nullable=False),
        sa.Column("conflicting_claims", sa.Integer(), nullable=False),
        sa.Column("evidence_coverage", sa.Float(), nullable=False),
        sa.Column("evidence_correctness_sample_size", sa.Integer(), nullable=False),
        sa.Column("evidence_correctness_sample_pass_rate", sa.Float(), nullable=False),
        sa.Column("review_required_count", sa.Integer(), nullable=False),
        sa.Column("blocker_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("fields_ready", sa.Integer(), nullable=False),
        sa.Column("fields_needs_review", sa.Integer(), nullable=False),
        sa.Column("false_consensus_risk_count", sa.Integer(), nullable=False),
        sa.Column("semantic_drift_count", sa.Integer(), nullable=False),
        sa.Column("raw_logging_detected", sa.Boolean(), nullable=False),
        sa.Column("tool_leakage_detected", sa.Boolean(), nullable=False),
        sa.Column("quality_flag", sa.String(), nullable=False),
        sa.Column("cost_chf", sa.Float(), nullable=True),
        sa.Column("cost_placeholder", sa.Boolean(), nullable=False),
        sa.Column("latency_seconds", sa.Float(), nullable=True),
        sa.Column("summary_version", sa.String(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("run_quality_summaries")
    op.drop_table("claim_lineages")
    op.drop_table("draft_claims")
