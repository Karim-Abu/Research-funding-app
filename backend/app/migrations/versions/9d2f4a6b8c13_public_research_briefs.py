"""Public-safe research briefs and honest research provenance.

Revision ID: 9d2f4a6b8c13
Revises: 8c1e3f5a7b92
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9d2f4a6b8c13"
down_revision: Union[str, None] = "8c1e3f5a7b92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_briefs",
        sa.Column("research_brief_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("application_domain", sa.String(), nullable=False),
        sa.Column("technology_class", sa.String(), nullable=False),
        sa.Column("target_customer_segments", sa.JSON(), nullable=False),
        sa.Column("region", sa.String(), nullable=False),
        sa.Column("competence_needs", sa.JSON(), nullable=False),
        sa.Column("modules", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
        sa.PrimaryKeyConstraint("research_brief_id"),
        sa.UniqueConstraint(
            "project_id", "version", name="uq_research_briefs_project_version"
        ),
    )
    op.create_index("ix_research_briefs_project_id", "research_briefs", ["project_id"])
    op.create_index(
        "ix_research_briefs_workspace_id", "research_briefs", ["workspace_id"]
    )

    for table in ("research_tasks", "search_query_approvals"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("research_brief_id", sa.String(), nullable=True))
            batch.add_column(sa.Column("research_module", sa.String(), nullable=True))
            batch.add_column(sa.Column("planner_purpose", sa.String(), nullable=True))
            if table == "research_tasks":
                batch.add_column(sa.Column("execution_mode", sa.String(), nullable=True))
            batch.create_foreign_key(
                f"fk_{table}_research_brief_id",
                "research_briefs",
                ["research_brief_id"],
                ["research_brief_id"],
            )
            batch.create_index(
                f"ix_{table}_research_brief_id", ["research_brief_id"]
            )
    op.execute("UPDATE research_tasks SET execution_mode = 'fake_demo' WHERE provider = 'fake'")
    op.execute(
        "UPDATE research_tasks SET execution_mode = 'live' "
        "WHERE provider IS NOT NULL AND provider <> 'fake'"
    )

    with op.batch_alter_table("market_comparison_items") as batch:
        batch.add_column(sa.Column(
            "comparison_dimensions", sa.JSON(), nullable=False,
            server_default=sa.text("'{}'"),
        ))
        batch.add_column(sa.Column("coverage_status", sa.String(), nullable=True))
        batch.add_column(sa.Column("support_status", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("market_comparison_items") as batch:
        batch.drop_column("support_status")
        batch.drop_column("coverage_status")
        batch.drop_column("comparison_dimensions")
    for table in ("search_query_approvals", "research_tasks"):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_research_brief_id")
            batch.drop_constraint(
                f"fk_{table}_research_brief_id", type_="foreignkey"
            )
            if table == "research_tasks":
                batch.drop_column("execution_mode")
            batch.drop_column("planner_purpose")
            batch.drop_column("research_module")
            batch.drop_column("research_brief_id")
    op.drop_index("ix_research_briefs_workspace_id", table_name="research_briefs")
    op.drop_index("ix_research_briefs_project_id", table_name="research_briefs")
    op.drop_table("research_briefs")
