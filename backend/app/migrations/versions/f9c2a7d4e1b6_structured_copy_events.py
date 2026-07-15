"""Generic metadata-only structured transfer copy events.

Revision ID: f9c2a7d4e1b6
Revises: 9d2f4a6b8c13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f9c2a7d4e1b6"
down_revision: Union[str, None] = "9d2f4a6b8c13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("copy_events") as batch_op:
        batch_op.add_column(sa.Column("target_type", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("target_key", sa.String(), nullable=True))
    op.execute("UPDATE copy_events SET target_type = 'portal_field', target_key = field_id")
    with op.batch_alter_table("copy_events") as batch_op:
        batch_op.alter_column("target_type", nullable=False)
        batch_op.alter_column("target_key", nullable=False)
        batch_op.alter_column("field_id", nullable=True)
        batch_op.alter_column("draft_version_id", nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("copy_events") as batch_op:
        batch_op.alter_column("field_id", nullable=False)
        batch_op.alter_column("draft_version_id", nullable=False)
        batch_op.drop_column("target_key")
        batch_op.drop_column("target_type")
