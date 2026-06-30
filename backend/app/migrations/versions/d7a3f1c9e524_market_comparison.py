"""Milestone 9I-B — market & competitor comparison (beta-internal tables).

Revision ID: d7a3f1c9e524
Revises: c5f9a2d7b3e1
Create Date: 2026-06-29
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7a3f1c9e524"
down_revision: Union[str, None] = "c5f9a2d7b3e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_comparisons",
        sa.Column("comparison_id", sa.String(), primary_key=True),
        sa.Column(
            "project_id", sa.String(), sa.ForeignKey("projects.project_id"),
            nullable=False, index=True,
        ),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("research_task_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("research_gaps", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("comparison_version", sa.Integer(), nullable=False),
        sa.Column("source_scope_hash", sa.String(), nullable=True),
        sa.Column("generation_status", sa.String(), nullable=True),
        sa.Column("operation_id", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("safe_error_detail", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "market_comparison_items",
        sa.Column("item_id", sa.String(), primary_key=True),
        sa.Column(
            "comparison_id", sa.String(),
            sa.ForeignKey("market_comparisons.comparison_id"),
            nullable=False, index=True,
        ),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("name_normalized", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_customer_segment", sa.String(), nullable=True),
        sa.Column("offering_summary", sa.Text(), nullable=True),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("weaknesses", sa.Text(), nullable=True),
        sa.Column("differentiation_relevance", sa.Text(), nullable=True),
        sa.Column("relation_to_project", sa.String(), nullable=False),
        sa.Column("confidence_label", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("source_document_ids", sa.JSON(), nullable=False),
        sa.Column("verified_quote_refs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("market_comparison_items")
    op.drop_table("market_comparisons")
