"""Add truthful live-model routing metadata.

Revision ID: c9e5a7b1d3f4
Revises: b8f4d6a2c9e1
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "c9e5a7b1d3f4"
down_revision = "b8f4d6a2c9e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("analysis_runs") as batch:
        batch.add_column(sa.Column("live_execution_status", sa.String(), nullable=True))
        batch.add_column(sa.Column("live_status_reason", sa.String(), nullable=True))
    with op.batch_alter_table("agent_invocations") as batch:
        batch.add_column(sa.Column("requested_model_id", sa.String(), nullable=True))
        batch.add_column(
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("termination_reason", sa.String(), nullable=True))

    op.create_table(
        "agent_invocation_attempts",
        sa.Column("attempt_id", sa.String(), primary_key=True),
        sa.Column("invocation_id", sa.String(), sa.ForeignKey("agent_invocations.invocation_id"), nullable=False),
        sa.Column("attempt_index", sa.Integer(), nullable=False),
        sa.Column("retry_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("route_key", sa.String(), nullable=False),
        sa.Column("route_alias", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("requested_model_id", sa.String(), nullable=True),
        sa.Column("actual_model_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_class", sa.String(), nullable=True),
        sa.Column("termination_reason", sa.String(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_chf", sa.Float(), nullable=True),
        sa.Column("estimated_cost_status", sa.String(), nullable=True),
        sa.Column("usage_record_id", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("invocation_id", "attempt_index", name="uq_agent_invocation_attempt_index"),
    )
    op.create_index("ix_agent_invocation_attempts_invocation_id", "agent_invocation_attempts", ["invocation_id"])

    op.create_table(
        "provider_preflight_results",
        sa.Column("preflight_id", sa.String(), primary_key=True),
        sa.Column("route_key", sa.String(), nullable=False),
        sa.Column("route_alias", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("requested_model_id", sa.String(), nullable=True),
        sa.Column("actual_model_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("checks_json", sa.JSON(), nullable=False),
        sa.Column("error_class", sa.String(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("triggered_by", sa.String(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_provider_preflight_results_route_key", "provider_preflight_results", ["route_key"])


def downgrade() -> None:
    op.drop_index("ix_provider_preflight_results_route_key", table_name="provider_preflight_results")
    op.drop_table("provider_preflight_results")
    op.drop_index("ix_agent_invocation_attempts_invocation_id", table_name="agent_invocation_attempts")
    op.drop_table("agent_invocation_attempts")
    with op.batch_alter_table("agent_invocations") as batch:
        batch.drop_column("termination_reason")
        batch.drop_column("retry_count")
        batch.drop_column("requested_model_id")
    with op.batch_alter_table("analysis_runs") as batch:
        batch.drop_column("live_status_reason")
        batch.drop_column("live_execution_status")
