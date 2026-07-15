"""Add truthful live-research metadata and review states.

Revision ID: e4a7c2f9b6d1
Revises: c9e5a7b1d3f4
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "e4a7c2f9b6d1"
down_revision = "c9e5a7b1d3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("source_documents") as batch:
        batch.add_column(sa.Column("source_url", sa.String(), nullable=True))
    with op.batch_alter_table("research_results") as batch:
        batch.add_column(sa.Column("publisher", sa.String(), nullable=True))
        batch.add_column(sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("source_category", sa.String(), nullable=True))
        batch.add_column(sa.Column(
            "source_quality", sa.String(), nullable=False, server_default="unassessed"
        ))
        batch.add_column(sa.Column(
            "potential_sections", sa.JSON(), nullable=False, server_default="[]"
        ))
        batch.add_column(sa.Column(
            "coverage_status", sa.String(), nullable=False, server_default="not_checked"
        ))
        batch.add_column(sa.Column(
            "support_status", sa.String(), nullable=False, server_default="not_checked"
        ))
        batch.add_column(sa.Column(
            "content_review_status", sa.String(), nullable=False, server_default="unreviewed"
        ))
    with op.batch_alter_table("market_comparisons") as batch:
        batch.add_column(sa.Column("generation_kind", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("market_comparisons") as batch:
        batch.drop_column("generation_kind")
    with op.batch_alter_table("research_results") as batch:
        batch.drop_column("content_review_status")
        batch.drop_column("support_status")
        batch.drop_column("coverage_status")
        batch.drop_column("potential_sections")
        batch.drop_column("source_quality")
        batch.drop_column("source_category")
        batch.drop_column("published_at")
        batch.drop_column("publisher")
    with op.batch_alter_table("source_documents") as batch:
        batch.drop_column("source_url")
