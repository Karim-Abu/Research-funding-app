"""Honest generation semantics and subsection A2 suggestions.

Revision ID: 8c1e3f5a7b92
Revises: 7a9c2e4f6b81
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8c1e3f5a7b92"
down_revision: Union[str, None] = "7a9c2e4f6b81"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "review_findings",
        sa.Column("target_section", sa.String(), nullable=True),
    )
    op.add_column(
        "draft_suggestions",
        sa.Column("generation_kind", sa.String(), nullable=True),
    )
    op.add_column(
        "draft_suggestions",
        sa.Column("target_section", sa.String(), nullable=True),
    )
    op.add_column(
        "draft_suggestions",
        sa.Column("section_result_json", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_draft_suggestions_run_draft_section_status",
        "draft_suggestions",
        ["run_id", "draft_id", "target_section", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_draft_suggestions_run_draft_section_status",
        table_name="draft_suggestions",
    )
    op.drop_column("draft_suggestions", "section_result_json")
    op.drop_column("draft_suggestions", "target_section")
    op.drop_column("draft_suggestions", "generation_kind")
    op.drop_column("review_findings", "target_section")
