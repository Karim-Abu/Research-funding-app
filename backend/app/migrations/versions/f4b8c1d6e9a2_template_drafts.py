"""Milestone 6 — deterministic template drafts: portal field drafts + versions.

Revision ID: f4b8c1d6e9a2
Revises: e7c2a9d4b8f1
Create Date: 2026-06-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f4b8c1d6e9a2"
down_revision: Union[str, None] = "e7c2a9d4b8f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portal_field_drafts",
        sa.Column("draft_id", sa.String(), primary_key=True),
        sa.Column(
            "run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id"),
            nullable=False, index=True,
        ),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("field_id", sa.String(), nullable=False),
        sa.Column("field_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("character_limit", sa.Integer(), nullable=True),
        sa.Column("current_version_id", sa.String(), nullable=True),
        sa.Column("open_issue_count", sa.Integer(), nullable=False),
        sa.Column("template_catalog_version", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "field_id", name="uq_draft_run_field"),
    )
    op.create_table(
        "draft_versions",
        sa.Column("draft_version_id", sa.String(), primary_key=True),
        sa.Column(
            "draft_id", sa.String(), sa.ForeignKey("portal_field_drafts.draft_id"),
            nullable=False, index=True,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("base_version_id", sa.String(), nullable=True),
        sa.Column("source_operation_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("draft_versions")
    op.drop_table("portal_field_drafts")
