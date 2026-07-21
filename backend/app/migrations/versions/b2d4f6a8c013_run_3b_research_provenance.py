"""RUN 3B source provenance, external anchors and market traceability.

Revision ID: b2d4f6a8c013
Revises: a1c3e5f7b902
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa


revision = "b2d4f6a8c013"
down_revision = "a1c3e5f7b902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("source_versions") as batch:
        batch.add_column(sa.Column("retrieval_provenance", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("content_review_status", sa.String(), nullable=False, server_default="not_applicable"))
        batch.add_column(sa.Column("content_safety_status", sa.String(), nullable=False, server_default="not_checked"))
        batch.add_column(sa.Column("quarantine_reason_code", sa.String(), nullable=True))
        batch.add_column(sa.Column("similarity_hash", sa.String(), nullable=True))
        batch.add_column(sa.Column("possible_duplicate_source_id", sa.String(), nullable=True))

    with op.batch_alter_table("evidence_anchors") as batch:
        batch.alter_column("run_id", existing_type=sa.String(), nullable=True)
        batch.add_column(sa.Column("project_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("research_task_id", sa.String(), nullable=True))
    op.create_index("ix_evidence_anchors_project_id", "evidence_anchors", ["project_id"])
    op.create_index("ix_evidence_anchors_research_task_id", "evidence_anchors", ["research_task_id"])
    with op.batch_alter_table("evidence_links") as batch:
        batch.alter_column("run_id", existing_type=sa.String(), nullable=True)

    with op.batch_alter_table("research_results") as batch:
        batch.add_column(sa.Column("canonical_url", sa.String(), nullable=True))
        batch.add_column(sa.Column("fetched_content_type", sa.String(), nullable=True))
        batch.add_column(sa.Column("fetched_content_hash", sa.String(), nullable=True))
        batch.add_column(sa.Column("content_safety_status", sa.String(), nullable=False, server_default="not_checked"))
        batch.add_column(sa.Column("quarantine_reason_code", sa.String(), nullable=True))
        batch.add_column(sa.Column("possible_duplicate_source_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("partner_candidate_status", sa.String(), nullable=True))
        batch.add_column(sa.Column("eligibility_status", sa.String(), nullable=False, server_default="not_checked"))
        batch.add_column(sa.Column("eligibility_anchor_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("eligibility_source_version_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("eligibility_official_url", sa.String(), nullable=True))
        batch.add_column(sa.Column("eligibility_source_location", sa.String(), nullable=True))
        batch.add_column(sa.Column("eligibility_last_checked", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("eligibility_reviewed_by", sa.String(), nullable=True))
        batch.add_column(sa.Column("eligibility_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_research_results_canonical_url", "research_results", ["canonical_url"])

    with op.batch_alter_table("market_comparisons") as batch:
        batch.add_column(sa.Column("research_brief_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("query_approval_ids", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("source_version_ids", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("provider", sa.String(), nullable=True))
        batch.add_column(sa.Column("model_ref", sa.String(), nullable=True))
        batch.add_column(sa.Column("prompt_version", sa.String(), nullable=True))
        batch.add_column(sa.Column("context_hash", sa.String(), nullable=True))
        batch.add_column(sa.Column("stale_reason", sa.String(), nullable=True))
        batch.add_column(sa.Column("consequences", sa.JSON(), nullable=False, server_default="[]"))
    with op.batch_alter_table("market_comparison_items") as batch:
        batch.add_column(sa.Column("evidence_anchor_ids", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("cell_evidence", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("uncertainty", sa.Text(), nullable=True))

    connection = op.get_bind()
    connection.execute(sa.text(
        "UPDATE evidence_anchors SET project_id=(SELECT project_id FROM analysis_runs "
        "WHERE analysis_runs.run_id=evidence_anchors.run_id) WHERE run_id IS NOT NULL"
    ))
    connection.execute(sa.text(
        "UPDATE research_results SET canonical_url=COALESCE(final_url, source_url)"
    ))
    connection.execute(sa.text(
        "UPDATE research_results SET partner_candidate_status='research_partner_candidate', "
        "eligibility_status='not_checked' WHERE research_task_id IN "
        "(SELECT research_task_id FROM research_tasks WHERE purpose='partner_research_org_topic')"
    ))

    # Preserve existing public-source review state in the immutable current version.
    rows = connection.execute(sa.text(
        "SELECT rr.source_document_id, rr.content_review_status, sd.current_source_version_id "
        "FROM research_results rr JOIN source_documents sd "
        "ON sd.source_id=rr.source_document_id WHERE rr.source_document_id IS NOT NULL"
    )).mappings()
    for row in rows:
        if row["current_source_version_id"]:
            connection.execute(sa.text(
                "UPDATE source_versions SET content_review_status=:review, "
                "retrieval_provenance=:provenance WHERE source_version_id=:version_id"
            ), {
                "review": row["content_review_status"],
                "version_id": row["current_source_version_id"],
                "provenance": json.dumps({"migration_backfill": True}),
            })


def downgrade() -> None:
    # RUN 3A requires a run_id on every anchor/link. External research anchors
    # introduced by RUN 3B are deliberately not analysis-run evidence and
    # therefore cannot be represented below this revision. Remove only those
    # RUN-3B-only rows; source documents, versions and older run evidence stay.
    connection = op.get_bind()
    connection.execute(sa.text(
        "DELETE FROM evidence_links WHERE run_id IS NULL OR anchor_id IN "
        "(SELECT anchor_id FROM evidence_anchors WHERE run_id IS NULL)"
    ))
    connection.execute(sa.text(
        "DELETE FROM evidence_anchors WHERE run_id IS NULL"
    ))

    with op.batch_alter_table("market_comparison_items") as batch:
        batch.drop_column("uncertainty")
        batch.drop_column("cell_evidence")
        batch.drop_column("evidence_anchor_ids")
    with op.batch_alter_table("market_comparisons") as batch:
        batch.drop_column("consequences")
        batch.drop_column("stale_reason")
        batch.drop_column("context_hash")
        batch.drop_column("prompt_version")
        batch.drop_column("model_ref")
        batch.drop_column("provider")
        batch.drop_column("source_version_ids")
        batch.drop_column("query_approval_ids")
        batch.drop_column("research_brief_id")
    op.drop_index("ix_research_results_canonical_url", table_name="research_results")
    with op.batch_alter_table("research_results") as batch:
        batch.drop_column("eligibility_reviewed_at")
        batch.drop_column("eligibility_reviewed_by")
        batch.drop_column("eligibility_last_checked")
        batch.drop_column("eligibility_source_location")
        batch.drop_column("eligibility_official_url")
        batch.drop_column("eligibility_source_version_id")
        batch.drop_column("eligibility_anchor_id")
        batch.drop_column("eligibility_status")
        batch.drop_column("partner_candidate_status")
        batch.drop_column("possible_duplicate_source_id")
        batch.drop_column("quarantine_reason_code")
        batch.drop_column("content_safety_status")
        batch.drop_column("fetched_content_hash")
        batch.drop_column("fetched_content_type")
        batch.drop_column("canonical_url")
    with op.batch_alter_table("evidence_links") as batch:
        batch.alter_column("run_id", existing_type=sa.String(), nullable=False)
    op.drop_index("ix_evidence_anchors_research_task_id", table_name="evidence_anchors")
    op.drop_index("ix_evidence_anchors_project_id", table_name="evidence_anchors")
    with op.batch_alter_table("evidence_anchors") as batch:
        batch.drop_column("research_task_id")
        batch.drop_column("project_id")
        batch.alter_column("run_id", existing_type=sa.String(), nullable=False)
    with op.batch_alter_table("source_versions") as batch:
        batch.drop_column("possible_duplicate_source_id")
        batch.drop_column("similarity_hash")
        batch.drop_column("quarantine_reason_code")
        batch.drop_column("content_safety_status")
        batch.drop_column("content_review_status")
        batch.drop_column("retrieval_provenance")
