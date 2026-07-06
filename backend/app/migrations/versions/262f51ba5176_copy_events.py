"""copy events

Slice 3 (Council E2-A): server-side CopyEvent per Innolink copy action —
governance metadata only (content hash, warning codes, override reason),
never the raw field text.

Revision ID: 262f51ba5176
Revises: e9124fbf91d8
Create Date: 2026-07-05 12:28:08.451441

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '262f51ba5176'
down_revision: Union[str, None] = 'e9124fbf91d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "copy_events",
        sa.Column("copy_event_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("field_id", sa.String(), nullable=False),
        sa.Column("draft_version_id", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("client_warnings", sa.JSON(), nullable=False),
        sa.Column("server_warnings", sa.JSON(), nullable=False),
        sa.Column("override_reason_code", sa.String(), nullable=True),
        sa.Column("override_reason_note", sa.String(), nullable=True),
        sa.Column("actor_user_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.run_id"]),
        sa.PrimaryKeyConstraint("copy_event_id"),
    )
    op.create_index(
        op.f("ix_copy_events_run_id"), "copy_events", ["run_id"], unique=False
    )
    op.create_index(
        op.f("ix_copy_events_workspace_id"),
        "copy_events",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_copy_events_workspace_id"), table_name="copy_events")
    op.drop_index(op.f("ix_copy_events_run_id"), table_name="copy_events")
    op.drop_table("copy_events")
