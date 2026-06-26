"""Milestone 9B — A1 fact extraction: extracted_facts + invocation context_meta.

Revision ID: e1b7f3a9c2d4
Revises: d9a4b2c6e8f3
Create Date: 2026-06-26
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1b7f3a9c2d4"
down_revision: Union[str, None] = "d9a4b2c6e8f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "extracted_facts",
        sa.Column("fact_id", sa.String(), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(),
            sa.ForeignKey("analysis_runs.run_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("fact_type", sa.String(), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("original_statement", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("requirement_id", sa.String(), nullable=True),
        sa.Column("field_id", sa.String(), nullable=True),
        sa.Column("source_fragment_ids", sa.JSON(), nullable=False),
        sa.Column("source_version_ids", sa.JSON(), nullable=False),
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("model_route", sa.String(), nullable=True),
        sa.Column("model_id", sa.String(), nullable=True),
        sa.Column("schema_version", sa.String(), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=True),
        sa.Column("agent_invocation_id", sa.String(), nullable=True),
        sa.Column("fact_fingerprint", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "run_id", "fact_fingerprint", name="uq_run_fact_fingerprint"
        ),
    )
    op.add_column(
        "agent_invocations",
        sa.Column("context_meta", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_invocations", "context_meta")
    op.drop_table("extracted_facts")
