"""RUN 3C versioned suggestion context and missing-input lifecycle.

Revision ID: c3e5a7b9d024
Revises: b2d4f6a8c013
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c3e5a7b9d024"
down_revision = "b2d4f6a8c013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suggestion_context_manifests",
        sa.Column("manifest_id", sa.String(), primary_key=True),
        sa.Column(
            "schema_version", sa.String(), nullable=False,
            server_default="SuggestionContextManifest@v1",
        ),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=True),
        sa.Column("run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id"), nullable=False),
        sa.Column("field_id", sa.String(), nullable=False),
        sa.Column("base_draft_version_id", sa.String(), nullable=False),
        sa.Column("primary_application_source_version_id", sa.String(), nullable=True),
        sa.Column("requirement_registry_version", sa.String(), nullable=False),
        sa.Column("rule_registry_version", sa.String(), nullable=False),
        sa.Column("field_instruction_hash", sa.String(), nullable=False),
        sa.Column("improvement_mode", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("selected_anchor_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("source_version_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("market_comparison_id", sa.String(), nullable=True),
        sa.Column("requirement_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("rule_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("prompt_version", sa.String(), nullable=False),
        sa.Column("output_schema_version", sa.String(), nullable=False),
        sa.Column("omitted_anchor_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("component_hashes", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("context_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "run_id", "field_id", "base_draft_version_id", "context_hash",
            name="uq_suggestion_manifest_context",
        ),
    )
    for column in ("workspace_id", "project_id", "run_id", "field_id", "context_hash"):
        op.create_index(
            f"ix_suggestion_context_manifests_{column}",
            "suggestion_context_manifests", [column],
        )

    with op.batch_alter_table("draft_suggestions") as batch:
        batch.add_column(sa.Column("project_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("manifest_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("improvement_mode", sa.String(), nullable=True))
        batch.add_column(sa.Column("change_summary", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("used_rule_ids", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("missing_inputs", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("unsupported_claim_warnings", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("factual_claims", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("source_version_ids", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("market_comparison_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("registry_version", sa.String(), nullable=True))
        batch.add_column(sa.Column("output_schema_version", sa.String(), nullable=True))
        batch.add_column(sa.Column("context_hash", sa.String(), nullable=True))
        batch.add_column(sa.Column("quality_state", sa.String(), nullable=True))
        batch.add_column(sa.Column("stale_reason", sa.String(), nullable=True))
        batch.add_column(sa.Column("historical_status", sa.String(), nullable=True))
        batch.add_column(sa.Column("accept_mode", sa.String(), nullable=False, server_default="legacy_partial"))
        batch.create_foreign_key(
            "fk_draft_suggestion_manifest", "suggestion_context_manifests",
            ["manifest_id"], ["manifest_id"],
        )
        batch.create_index("ix_draft_suggestions_project_id", ["project_id"])
        batch.create_index("ix_draft_suggestions_manifest_id", ["manifest_id"])

    with op.batch_alter_table("open_issues") as batch:
        batch.add_column(sa.Column("field_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("requirement_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("missing_input_key", sa.String(), nullable=True))
        batch.add_column(sa.Column("source_suggestion_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("stale_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("status_reason", sa.String(), nullable=True))
        batch.create_index("ix_open_issues_field_id", ["field_id"])
        batch.create_index("ix_open_issues_requirement_id", ["requirement_id"])

    connection = op.get_bind()
    connection.execute(sa.text(
        "UPDATE draft_suggestions SET project_id=(SELECT project_id FROM analysis_runs "
        "WHERE analysis_runs.run_id=draft_suggestions.run_id)"
    ))
    connection.execute(sa.text(
        "UPDATE draft_suggestions SET historical_status=status, status='expired', "
        "stale_reason='historical_context_unavailable' WHERE manifest_id IS NULL"
    ))


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text(
        "UPDATE draft_suggestions SET status=historical_status "
        "WHERE status='expired' AND stale_reason='historical_context_unavailable' "
        "AND historical_status IS NOT NULL"
    ))
    with op.batch_alter_table("open_issues") as batch:
        batch.drop_index("ix_open_issues_requirement_id")
        batch.drop_index("ix_open_issues_field_id")
        batch.drop_column("status_reason")
        batch.drop_column("stale_at")
        batch.drop_column("resolved_at")
        batch.drop_column("source_suggestion_id")
        batch.drop_column("missing_input_key")
        batch.drop_column("requirement_id")
        batch.drop_column("field_id")
    with op.batch_alter_table("draft_suggestions") as batch:
        batch.drop_index("ix_draft_suggestions_manifest_id")
        batch.drop_index("ix_draft_suggestions_project_id")
        batch.drop_constraint("fk_draft_suggestion_manifest", type_="foreignkey")
        batch.drop_column("accept_mode")
        batch.drop_column("historical_status")
        batch.drop_column("stale_reason")
        batch.drop_column("quality_state")
        batch.drop_column("context_hash")
        batch.drop_column("output_schema_version")
        batch.drop_column("registry_version")
        batch.drop_column("market_comparison_id")
        batch.drop_column("source_version_ids")
        batch.drop_column("factual_claims")
        batch.drop_column("unsupported_claim_warnings")
        batch.drop_column("missing_inputs")
        batch.drop_column("used_rule_ids")
        batch.drop_column("change_summary")
        batch.drop_column("improvement_mode")
        batch.drop_column("manifest_id")
        batch.drop_column("project_id")
    for column in ("context_hash", "field_id", "run_id", "project_id", "workspace_id"):
        op.drop_index(
            f"ix_suggestion_context_manifests_{column}",
            table_name="suggestion_context_manifests",
        )
    op.drop_table("suggestion_context_manifests")
