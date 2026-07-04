"""Milestone 9I-A — public web research: research_tasks + research_results,
and research-task scoping for tool_invocations / control_results / usage_records.

Revision ID: c5f9a2d7b3e1
Revises: b4e8f1a3c6d2
Create Date: 2026-06-29
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5f9a2d7b3e1"
down_revision: Union[str, None] = "b4e8f1a3c6d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_tasks",
        sa.Column("research_task_id", sa.String(), primary_key=True),
        sa.Column(
            "project_id", sa.String(), sa.ForeignKey("projects.project_id"),
            nullable=False, index=True,
        ),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("operation_id", sa.String(), nullable=True),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("subject_type", sa.String(), nullable=False),
        sa.Column("subject_name", sa.String(), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("normalized_query_hash", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("preferred_domains", sa.JSON(), nullable=False),
        sa.Column("disallowed_domains", sa.JSON(), nullable=False),
        sa.Column("competence_needs", sa.JSON(), nullable=False),
        sa.Column("requested_partner_roles", sa.JSON(), nullable=False),
        sa.Column("max_results", sa.Integer(), nullable=False),
        sa.Column("max_pages", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("provider_usage", sa.JSON(), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("a1_synthesis_status", sa.String(), nullable=True),
        sa.Column("internal_public_confirmation_id", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("safe_error_detail", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "research_results",
        sa.Column("result_id", sa.String(), primary_key=True),
        sa.Column(
            "research_task_id", sa.String(),
            sa.ForeignKey("research_tasks.research_task_id"),
            nullable=False, index=True,
        ),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("final_url", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("provider_rank", sa.Integer(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("identity_match_status", sa.String(), nullable=False),
        sa.Column("source_document_id", sa.String(), nullable=True),
        sa.Column("professional_evidence", sa.JSON(), nullable=False),
        sa.Column("partner_role_suggestions", sa.JSON(), nullable=False),
        sa.Column("safe_error_detail", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Research-task-scoped cost/audit (corr 4): never aggregate under run_id=null.
    op.add_column(
        "control_results",
        sa.Column("research_task_id", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_control_results_research_task_id", "control_results", ["research_task_id"]
    )
    with op.batch_alter_table("tool_invocations", schema=None) as batch_op:
        batch_op.alter_column("run_id", existing_type=sa.String(), nullable=True)
        batch_op.add_column(sa.Column("research_task_id", sa.String(), nullable=True))
        batch_op.create_index(
            "ix_tool_invocations_research_task_id", ["research_task_id"]
        )
    with op.batch_alter_table("usage_records", schema=None) as batch_op:
        batch_op.alter_column("run_id", existing_type=sa.String(), nullable=True)
        batch_op.add_column(sa.Column("research_task_id", sa.String(), nullable=True))
        batch_op.create_index(
            "ix_usage_records_research_task_id", ["research_task_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("usage_records", schema=None) as batch_op:
        batch_op.drop_index("ix_usage_records_research_task_id")
        batch_op.drop_column("research_task_id")
        batch_op.alter_column("run_id", existing_type=sa.String(), nullable=False)
    with op.batch_alter_table("tool_invocations", schema=None) as batch_op:
        batch_op.drop_index("ix_tool_invocations_research_task_id")
        batch_op.drop_column("research_task_id")
        batch_op.alter_column("run_id", existing_type=sa.String(), nullable=False)
    op.drop_index("ix_control_results_research_task_id", table_name="control_results")
    op.drop_column("control_results", "research_task_id")
    op.drop_table("research_results")
    op.drop_table("research_tasks")
