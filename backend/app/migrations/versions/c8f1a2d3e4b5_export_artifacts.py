"""Milestone 8 — deterministic exports: export_artifacts + tool_invocations.

Revision ID: c8f1a2d3e4b5
Revises: b7e3f5a91c42
Create Date: 2026-06-25
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8f1a2d3e4b5"
down_revision: Union[str, None] = "b7e3f5a91c42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tool_invocations",
        sa.Column("invocation_id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column(
            "run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id"),
            nullable=False, index=True,
        ),
        sa.Column("tool_id", sa.String(), nullable=False),
        sa.Column("caller", sa.String(), nullable=False),
        sa.Column("input_hash", sa.String(), nullable=False),
        sa.Column("output_hash", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_class", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "export_artifacts",
        sa.Column("export_id", sa.String(), primary_key=True),
        sa.Column(
            "run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id"),
            nullable=False, index=True,
        ),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("project_id", sa.String(), nullable=False, index=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("draft_marked", sa.Boolean(), nullable=False),
        sa.Column("filename", sa.String(), nullable=True),
        sa.Column("storage_key", sa.String(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(), nullable=True),
        sa.Column("approval_id", sa.String(), nullable=True),
        sa.Column("approval_scope_hash", sa.String(), nullable=True),
        sa.Column("review_package_version", sa.String(), nullable=True),
        sa.Column("effective_data_classification", sa.JSON(), nullable=False),
        sa.Column("export_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("export_snapshot_hash", sa.String(), nullable=False),
        sa.Column("tool_invocation_id", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_detail", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "control_results",
        sa.Column("run_id", sa.String(), nullable=True),
    )
    op.add_column(
        "control_results",
        sa.Column("tool_invocation_id", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_control_results_run_id", "control_results", ["run_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_control_results_run_id", table_name="control_results")
    op.drop_column("control_results", "tool_invocation_id")
    op.drop_column("control_results", "run_id")
    op.drop_table("export_artifacts")
    op.drop_table("tool_invocations")
