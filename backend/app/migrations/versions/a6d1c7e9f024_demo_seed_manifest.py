"""Milestone 6.1 - deterministic demo seed manifest.

Revision ID: a6d1c7e9f024
Revises: f4b8c1d6e9a2
Create Date: 2026-06-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a6d1c7e9f024"
down_revision: Union[str, None] = "f4b8c1d6e9a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "demo_seed_manifest",
        sa.Column("manifest_id", sa.String(), primary_key=True),
        sa.Column("seed_version", sa.String(), nullable=False, index=True),
        sa.Column("object_type", sa.String(), nullable=False, index=True),
        sa.Column("object_id", sa.String(), nullable=False, index=True),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("project_id", sa.String(), nullable=True, index=True),
        sa.Column("storage_ref", sa.String(), nullable=True),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "seed_version", "object_type", "object_id",
            name="uq_demo_seed_manifest_object",
        ),
    )


def downgrade() -> None:
    op.drop_table("demo_seed_manifest")
