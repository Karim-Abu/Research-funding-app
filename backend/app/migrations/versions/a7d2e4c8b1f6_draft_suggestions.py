"""Milestone 9D — A2 solution & innovation draft suggestions.

Revision ID: a7d2e4c8b1f6
Revises: f3c5d7e9a1b2
Create Date: 2026-06-27
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7d2e4c8b1f6"
down_revision: Union[str, None] = "f3c5d7e9a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "draft_suggestions",
        sa.Column("suggestion_id", sa.String(), primary_key=True),
        sa.Column(
            "run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id"),
            nullable=False, index=True,
        ),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("draft_id", sa.String(), nullable=False, index=True),
        sa.Column("base_version_id", sa.String(), nullable=False),
        sa.Column("field_id", sa.String(), nullable=False),
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("operation_id", sa.String(), nullable=False, index=True),
        sa.Column("agent_invocation_id", sa.String(), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=True),
        sa.Column("model_route", sa.String(), nullable=True),
        sa.Column("model_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("suggested_text", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("evidence_anchor_ids", sa.JSON(), nullable=False),
        sa.Column("open_issue_ids", sa.JSON(), nullable=False),
        sa.Column("placeholders", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(), nullable=True),
        sa.Column("accepted_draft_version_id", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("draft_suggestions")
