"""Milestone 9J — search query firewall approvals (beta-internal privacy control).

Revision ID: e2b6c4f8a1d3
Revises: d7a3f1c9e524
Create Date: 2026-07-01
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2b6c4f8a1d3"
down_revision: Union[str, None] = "d7a3f1c9e524"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "search_query_approvals",
        sa.Column("approval_id", sa.String(), primary_key=True),
        sa.Column(
            "project_id", sa.String(), sa.ForeignKey("projects.project_id"),
            nullable=False, index=True,
        ),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("actor_user_id", sa.String(), nullable=False),
        sa.Column("intended_tool", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=True),
        sa.Column("data_class", sa.String(), nullable=False),
        # SHA256 of the normalized raw query — the raw query is never stored.
        sa.Column("raw_query_hash", sa.String(), nullable=False, index=True),
        sa.Column("sanitized_query", sa.Text(), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("redaction_summary", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("used_by_research_task_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Firewall provenance on the research task (nullable; D0 tasks leave both null).
    op.add_column(
        "research_tasks",
        sa.Column("firewall_data_class", sa.String(), nullable=True),
    )
    op.add_column(
        "research_tasks",
        sa.Column("firewall_approval_id", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_tasks", "firewall_approval_id")
    op.drop_column("research_tasks", "firewall_data_class")
    op.drop_table("search_query_approvals")
