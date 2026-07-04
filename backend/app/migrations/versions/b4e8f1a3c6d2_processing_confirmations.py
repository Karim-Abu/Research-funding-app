"""Milestone 9D.2 — cloud-processing confirmations + policy-snapshot provenance.

Revision ID: b4e8f1a3c6d2
Revises: a7d2e4c8b1f6
Create Date: 2026-06-29
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4e8f1a3c6d2"
down_revision: Union[str, None] = "a7d2e4c8b1f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "processing_confirmations",
        sa.Column("confirmation_id", sa.String(), primary_key=True),
        sa.Column(
            "project_id", sa.String(), sa.ForeignKey("projects.project_id"),
            nullable=False, index=True,
        ),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("processing_mode", sa.String(), nullable=False),
        sa.Column("source_version_ids", sa.JSON(), nullable=False),
        sa.Column("accepted_policy_version", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("provider_route_class", sa.String(), nullable=False),
        sa.Column("confirmation_text_version", sa.String(), nullable=False),
        sa.Column("data_classification_shown", sa.JSON(), nullable=False),
        sa.Column("expires_after_one_run", sa.Boolean(), nullable=False),
        sa.Column("used_by_run_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "run_policy_snapshots",
        sa.Column("cloud_confirmation_id", sa.String(), nullable=True),
    )
    op.add_column(
        "run_policy_snapshots",
        sa.Column("provider_route_class", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("run_policy_snapshots", "provider_route_class")
    op.drop_column("run_policy_snapshots", "cloud_confirmation_id")
    op.drop_table("processing_confirmations")
