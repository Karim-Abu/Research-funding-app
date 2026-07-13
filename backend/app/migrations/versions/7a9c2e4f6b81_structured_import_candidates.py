"""Strukturierte Importkandidaten und additive Zielmodell-Felder.

Revision ID: 7a9c2e4f6b81
Revises: 1d4f8a2c6b90
Create Date: 2026-07-13
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7a9c2e4f6b81"
down_revision: Union[str, None] = "1d4f8a2c6b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("title_en", sa.String(), nullable=True))
        batch.add_column(sa.Column("start_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("end_date", sa.Date(), nullable=True))
        batch.add_column(
            sa.Column(
                "total_requested_funding_including_overhead",
                sa.Float(),
                nullable=True,
            )
        )

    with op.batch_alter_table("partners") as batch:
        batch.add_column(sa.Column("department", sa.String(), nullable=True))

    op.create_table(
        "structured_import_candidates",
        sa.Column("candidate_id", sa.String(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(),
            sa.ForeignKey("workspaces.id"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.String(),
            sa.ForeignKey("projects.project_id"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.String(),
            sa.ForeignKey("source_documents.source_id"),
            nullable=False,
        ),
        sa.Column(
            "source_version_id",
            sa.String(),
            sa.ForeignKey("source_versions.source_version_id"),
            nullable=False,
        ),
        sa.Column("candidate_kind", sa.String(), nullable=False),
        sa.Column("target_key", sa.String(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("edited_payload_json", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.String(), nullable=False),
        sa.Column("source_location", sa.String(), nullable=True),
        sa.Column("mapping_version", sa.String(), nullable=False),
        sa.Column(
            "decision", sa.String(), nullable=False, server_default="pending"
        ),
        sa.Column("decided_by", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_resource_id", sa.String(), nullable=True),
        sa.Column(
            "supersedes_candidate_id",
            sa.String(),
            sa.ForeignKey("structured_import_candidates.candidate_id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "source_version_id",
            "candidate_kind",
            "target_key",
            name="uq_structured_import_version_kind_target",
        ),
    )
    op.create_index(
        "ix_structured_import_candidates_workspace_id",
        "structured_import_candidates",
        ["workspace_id"],
    )
    op.create_index(
        "ix_structured_import_candidates_project_id",
        "structured_import_candidates",
        ["project_id"],
    )
    op.create_index(
        "ix_structured_import_candidates_source_id",
        "structured_import_candidates",
        ["source_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_structured_import_candidates_source_id",
        table_name="structured_import_candidates",
    )
    op.drop_index(
        "ix_structured_import_candidates_project_id",
        table_name="structured_import_candidates",
    )
    op.drop_index(
        "ix_structured_import_candidates_workspace_id",
        table_name="structured_import_candidates",
    )
    op.drop_table("structured_import_candidates")

    with op.batch_alter_table("partners") as batch:
        batch.drop_column("department")

    with op.batch_alter_table("projects") as batch:
        batch.drop_column("total_requested_funding_including_overhead")
        batch.drop_column("end_date")
        batch.drop_column("start_date")
        batch.drop_column("title_en")
