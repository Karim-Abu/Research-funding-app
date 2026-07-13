"""import candidates

R3.2 — neue Tabelle ``import_candidates`` für den Innolink-Antragsimport
(HITL-Review-Flow). Rein additiv: keine bestehende Tabelle/Spalte wird
verändert; Downgrade entfernt nur die neue Tabelle.

Revision ID: a3f8c2d91e47
Revises: 7b091c3d3e24
Create Date: 2026-07-07 22:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3f8c2d91e47'
down_revision: Union[str, None] = '7b091c3d3e24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_candidates",
        sa.Column("import_candidate_id", sa.String(), primary_key=True),
        sa.Column(
            "workspace_id", sa.String(), sa.ForeignKey("workspaces.id"),
            nullable=False,
        ),
        sa.Column(
            "project_id", sa.String(), sa.ForeignKey("projects.project_id"),
            nullable=False,
        ),
        sa.Column(
            "source_id", sa.String(), sa.ForeignKey("source_documents.source_id"),
            nullable=False,
        ),
        sa.Column(
            "source_version_id", sa.String(),
            sa.ForeignKey("source_versions.source_version_id"), nullable=False,
        ),
        sa.Column("field_id", sa.String(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(), nullable=False),
        sa.Column("source_location", sa.String(), nullable=True),
        sa.Column("decision", sa.String(), nullable=False, server_default="pending"),
        sa.Column(
            "decided_by", sa.String(), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_draft_version_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "source_version_id", "field_id", name="uq_import_candidate_version_field"
        ),
    )
    op.create_index(
        "ix_import_candidates_workspace_id", "import_candidates", ["workspace_id"]
    )
    op.create_index(
        "ix_import_candidates_project_id", "import_candidates", ["project_id"]
    )
    op.create_index(
        "ix_import_candidates_source_id", "import_candidates", ["source_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_import_candidates_source_id", table_name="import_candidates")
    op.drop_index("ix_import_candidates_project_id", table_name="import_candidates")
    op.drop_index("ix_import_candidates_workspace_id", table_name="import_candidates")
    op.drop_table("import_candidates")
