"""RUN 2B import revisions, primary application and evidence scope.

Revision ID: f7b9d2c4a681
Revises: e4a7c2f9b6d1
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "f7b9d2c4a681"
down_revision = "e4a7c2f9b6d1"
branch_labels = None
depends_on = None


def _json_value(field_name: str, value: object) -> str:
    if isinstance(value, (datetime,)):
        value = value.isoformat()
    return json.dumps({field_name: value}, ensure_ascii=False)


def _backfill_import_revisions() -> None:
    connection = op.get_bind()
    now = datetime.now(timezone.utc)
    rows = connection.execute(
        sa.text(
            "SELECT import_candidate_id, decision, edited_text, "
            "accepted_draft_version_id, decided_by, created_at "
            "FROM import_candidates"
        )
    ).mappings()
    for row in rows:
        revision_id = str(uuid.uuid4())
        connection.execute(
            sa.text(
                "INSERT INTO import_candidate_revisions "
                "(revision_id, import_candidate_id, revision_number, status, action, "
                "user_text, run_id, previous_draft_version_id, "
                "applied_draft_version_id, actor_user_id, created_at) "
                "VALUES (:revision_id, :candidate_id, 1, :status, "
                "'legacy_migrated', :user_text, NULL, NULL, :draft_id, "
                ":actor, :created_at)"
            ),
            {
                "revision_id": revision_id,
                "candidate_id": row["import_candidate_id"],
                "status": row["decision"],
                "user_text": row["edited_text"],
                "draft_id": row["accepted_draft_version_id"],
                "actor": row["decided_by"],
                "created_at": row["created_at"] or now,
            },
        )
        connection.execute(
            sa.text(
                "UPDATE import_candidates SET current_revision_id=:revision_id, "
                "revision_number=1 WHERE import_candidate_id=:candidate_id"
            ),
            {"revision_id": revision_id, "candidate_id": row["import_candidate_id"]},
        )

    rows = connection.execute(
        sa.text(
            "SELECT candidate_id, decision, edited_payload_json, "
            "applied_resource_id, decided_by, created_at "
            "FROM structured_import_candidates"
        )
    ).mappings()
    for row in rows:
        revision_id = str(uuid.uuid4())
        connection.execute(
            sa.text(
                "INSERT INTO structured_import_candidate_revisions "
                "(revision_id, candidate_id, revision_number, status, action, "
                "user_payload_json, previous_target_json, target_resource_id, "
                "previous_target_revision_number, applied_target_revision_number, "
                "project_field_revision_id, actor_user_id, created_at) "
                "VALUES (:revision_id, :candidate_id, 1, :status, "
                "'legacy_migrated', :payload, NULL, :target_id, NULL, NULL, NULL, "
                ":actor, :created_at)"
            ),
            {
                "revision_id": revision_id,
                "candidate_id": row["candidate_id"],
                "status": row["decision"],
                "payload": row["edited_payload_json"],
                "target_id": row["applied_resource_id"],
                "actor": row["decided_by"],
                "created_at": row["created_at"] or now,
            },
        )
        connection.execute(
            sa.text(
                "UPDATE structured_import_candidates "
                "SET current_revision_id=:revision_id, revision_number=1 "
                "WHERE candidate_id=:candidate_id"
            ),
            {"revision_id": revision_id, "candidate_id": row["candidate_id"]},
        )


def _backfill_project_fields_and_primary_source() -> None:
    connection = op.get_bind()
    now = datetime.now(timezone.utc)
    fields = (
        "title",
        "title_en",
        "start_date",
        "end_date",
        "description",
        "innovation_field",
        "budget_framework_chf",
        "direct_total_project_costs_excluding_overhead",
        "implementation_own_contribution",
        "cash_contribution",
        "total_requested_funding",
        "total_requested_funding_including_overhead",
        "budget_exception_basis",
        "status",
    )
    columns = ", ".join(("project_id", "workspace_id", "created_by", *fields))
    projects = connection.execute(sa.text(f"SELECT {columns} FROM projects")).mappings()
    for project in projects:
        has_revision = False
        for field_name in fields:
            value = project[field_name]
            if value is None:
                continue
            has_revision = True
            connection.execute(
                sa.text(
                    "INSERT INTO project_field_revisions "
                    "(revision_id, workspace_id, project_id, field_name, "
                    "revision_number, value_json, source, source_revision_id, "
                    "actor_user_id, created_at) VALUES "
                    "(:revision_id, :workspace_id, :project_id, :field_name, 1, "
                    ":value_json, 'legacy_migrated', NULL, :actor, :created_at)"
                ),
                {
                    "revision_id": str(uuid.uuid4()),
                    "workspace_id": project["workspace_id"],
                    "project_id": project["project_id"],
                    "field_name": field_name,
                    "value_json": _json_value(field_name, value),
                    "actor": project["created_by"],
                    "created_at": now,
                },
            )
        if has_revision:
            connection.execute(
                sa.text(
                    "UPDATE projects SET field_revision_number=1 "
                    "WHERE project_id=:project_id"
                ),
                {"project_id": project["project_id"]},
            )

    source_rows = connection.execute(
        sa.text(
            "SELECT project_id, source_id FROM import_candidates "
            "UNION SELECT project_id, source_id FROM structured_import_candidates"
        )
    ).mappings()
    by_project: dict[str, set[str]] = {}
    for row in source_rows:
        by_project.setdefault(row["project_id"], set()).add(row["source_id"])
    for project_id, source_ids in by_project.items():
        if len(source_ids) == 1:
            connection.execute(
                sa.text(
                    "UPDATE projects SET primary_application_source_id=:source_id "
                    "WHERE project_id=:project_id"
                ),
                {"source_id": next(iter(source_ids)), "project_id": project_id},
            )


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("primary_application_source_id", sa.String(), nullable=True))
        batch.add_column(
            sa.Column(
                "field_revision_number",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch.create_index(
            "ix_projects_primary_application_source_id",
            ["primary_application_source_id"],
            unique=False,
        )
    with op.batch_alter_table("partners") as batch:
        batch.add_column(
            sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1")
        )
    with op.batch_alter_table("import_candidates") as batch:
        batch.add_column(sa.Column("current_revision_id", sa.String(), nullable=True))
        batch.add_column(
            sa.Column("revision_number", sa.Integer(), nullable=False, server_default="0")
        )
    with op.batch_alter_table("structured_import_candidates") as batch:
        batch.add_column(sa.Column("current_revision_id", sa.String(), nullable=True))
        batch.add_column(
            sa.Column("revision_number", sa.Integer(), nullable=False, server_default="0")
        )
    with op.batch_alter_table("evidence_candidates") as batch:
        batch.add_column(
            sa.Column("scope", sa.String(), nullable=False, server_default="application")
        )
        batch.add_column(sa.Column("rejection_reason_code", sa.String(), nullable=True))
    with op.batch_alter_table("evidence_anchors") as batch:
        batch.add_column(
            sa.Column("scope", sa.String(), nullable=False, server_default="application")
        )
        batch.add_column(sa.Column("rejection_reason_code", sa.String(), nullable=True))

    op.create_table(
        "import_candidate_revisions",
        sa.Column("revision_id", sa.String(), primary_key=True),
        sa.Column(
            "import_candidate_id",
            sa.String(),
            sa.ForeignKey("import_candidates.import_candidate_id"),
            nullable=False,
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("user_text", sa.Text(), nullable=True),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("previous_draft_version_id", sa.String(), nullable=True),
        sa.Column("applied_draft_version_id", sa.String(), nullable=True),
        sa.Column("actor_user_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "import_candidate_id",
            "revision_number",
            name="uq_import_candidate_revision_number",
        ),
    )
    op.create_index(
        "ix_import_candidate_revisions_import_candidate_id",
        "import_candidate_revisions",
        ["import_candidate_id"],
        unique=False,
    )
    op.create_table(
        "structured_import_candidate_revisions",
        sa.Column("revision_id", sa.String(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(),
            sa.ForeignKey("structured_import_candidates.candidate_id"),
            nullable=False,
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("user_payload_json", sa.JSON(), nullable=True),
        sa.Column("previous_target_json", sa.JSON(), nullable=True),
        sa.Column("target_resource_id", sa.String(), nullable=True),
        sa.Column("previous_target_revision_number", sa.Integer(), nullable=True),
        sa.Column("applied_target_revision_number", sa.Integer(), nullable=True),
        sa.Column("project_field_revision_id", sa.String(), nullable=True),
        sa.Column("actor_user_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "candidate_id",
            "revision_number",
            name="uq_structured_import_candidate_revision_number",
        ),
    )
    op.create_index(
        "ix_structured_import_candidate_revisions_candidate_id",
        "structured_import_candidate_revisions",
        ["candidate_id"],
        unique=False,
    )
    op.create_table(
        "project_field_revisions",
        sa.Column("revision_id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column(
            "project_id",
            sa.String(),
            sa.ForeignKey("projects.project_id"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("source_revision_id", sa.String(), nullable=True),
        sa.Column("actor_user_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "project_id",
            "field_name",
            "revision_number",
            name="uq_project_field_revision_number",
        ),
    )
    op.create_index(
        "ix_project_field_revisions_workspace_id",
        "project_field_revisions",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_field_revisions_project_id",
        "project_field_revisions",
        ["project_id"],
        unique=False,
    )

    _backfill_import_revisions()
    _backfill_project_fields_and_primary_source()


def downgrade() -> None:
    op.drop_index(
        "ix_project_field_revisions_project_id",
        table_name="project_field_revisions",
    )
    op.drop_index(
        "ix_project_field_revisions_workspace_id",
        table_name="project_field_revisions",
    )
    op.drop_table("project_field_revisions")
    op.drop_index(
        "ix_structured_import_candidate_revisions_candidate_id",
        table_name="structured_import_candidate_revisions",
    )
    op.drop_table("structured_import_candidate_revisions")
    op.drop_index(
        "ix_import_candidate_revisions_import_candidate_id",
        table_name="import_candidate_revisions",
    )
    op.drop_table("import_candidate_revisions")
    with op.batch_alter_table("evidence_anchors") as batch:
        batch.drop_column("rejection_reason_code")
        batch.drop_column("scope")
    with op.batch_alter_table("evidence_candidates") as batch:
        batch.drop_column("rejection_reason_code")
        batch.drop_column("scope")
    with op.batch_alter_table("structured_import_candidates") as batch:
        batch.drop_column("revision_number")
        batch.drop_column("current_revision_id")
    with op.batch_alter_table("import_candidates") as batch:
        batch.drop_column("revision_number")
        batch.drop_column("current_revision_id")
    with op.batch_alter_table("partners") as batch:
        batch.drop_column("revision_number")
    with op.batch_alter_table("projects") as batch:
        batch.drop_index("ix_projects_primary_application_source_id")
        batch.drop_column("field_revision_number")
        batch.drop_column("primary_application_source_id")
