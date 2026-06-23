"""Milestone 4 — partners, project snapshot, rule results, assessments, issues.

Revision ID: d3a1b6e4f2c7
Revises: c0774f9f2c38
Create Date: 2026-06-23
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3a1b6e4f2c7"
down_revision: Union[str, None] = "c0774f9f2c38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "partners",
        sa.Column("partner_id", sa.String(), primary_key=True),
        sa.Column(
            "project_id", sa.String(), sa.ForeignKey("projects.project_id"),
            nullable=False, index=True,
        ),
        sa.Column(
            "workspace_id", sa.String(), sa.ForeignKey("workspaces.id"),
            nullable=False, index=True,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("partner_type", sa.String(), nullable=False),
        sa.Column("project_role", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("contribution", sa.String(), nullable=True),
        sa.Column("uid", sa.String(), nullable=True),
        sa.Column("industry", sa.String(), nullable=True),
        sa.Column("fte", sa.Float(), nullable=True),
        sa.Column("startup_status", sa.Boolean(), nullable=True),
        sa.Column("swiss_value_creation", sa.Boolean(), nullable=True),
        sa.Column("research_partner_eligibility_status", sa.String(), nullable=True),
        sa.Column("official_representative", sa.JSON(), nullable=True),
        sa.Column("personnel_independence_status", sa.String(), nullable=True),
        sa.Column("financial_independence_status", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "run_project_snapshots",
        sa.Column(
            "run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id"),
            primary_key=True,
        ),
        sa.Column("project_id", sa.String(), nullable=False, index=True),
        sa.Column("project_json", sa.JSON(), nullable=False),
        sa.Column("partners_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("requirement_registry_version", sa.String(), nullable=False),
        sa.Column("rule_registry_version", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "rule_results",
        sa.Column("rule_result_id", sa.String(), primary_key=True),
        sa.Column(
            "run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id"),
            nullable=False, index=True,
        ),
        sa.Column("requirement_id", sa.String(), nullable=True),
        sa.Column("rule_id", sa.String(), nullable=False),
        sa.Column("rule_version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("outcome_label", sa.String(), nullable=False),
        sa.Column("mapping_key", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("execution_mode", sa.String(), nullable=False),
        sa.Column("observed", sa.JSON(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "requirement_assessments",
        sa.Column("assessment_id", sa.String(), primary_key=True),
        sa.Column(
            "run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id"),
            nullable=False, index=True,
        ),
        sa.Column("requirement_id", sa.String(), nullable=False),
        sa.Column("requirement_version", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("basis", sa.String(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("stale", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "requirement_id", name="uq_run_requirement"),
    )

    op.create_table(
        "open_issues",
        sa.Column("issue_id", sa.String(), primary_key=True),
        sa.Column(
            "run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id"),
            nullable=False, index=True,
        ),
        sa.Column("issue_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("recommended_next_action", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("responsible_user_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "run_id", "target_type", "target_id", name="uq_run_issue_target"
        ),
    )


def downgrade() -> None:
    op.drop_table("open_issues")
    op.drop_table("requirement_assessments")
    op.drop_table("rule_results")
    op.drop_table("run_project_snapshots")
    op.drop_table("partners")
