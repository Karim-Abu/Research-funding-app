"""Milestone 9A — agent infrastructure: agent_invocations + control link.

Revision ID: d9a4b2c6e8f3
Revises: c8f1a2d3e4b5
Create Date: 2026-06-26
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9a4b2c6e8f3"
down_revision: Union[str, None] = "c8f1a2d3e4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_invocations",
        sa.Column("invocation_id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=True, index=True),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("project_id", sa.String(), nullable=True),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("model_route", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("input_schema_id", sa.String(), nullable=False),
        sa.Column("output_schema_id", sa.String(), nullable=False),
        sa.Column("prompt_version", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("input_hash", sa.String(), nullable=True),
        sa.Column("output_hash", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("safe_error_detail", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("usage_record_id", sa.String(), nullable=True),
        sa.Column("created_by_system", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "control_results",
        sa.Column("agent_invocation_id", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("control_results", "agent_invocation_id")
    op.drop_table("agent_invocations")
