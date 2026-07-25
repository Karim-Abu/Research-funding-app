"""Persist exact provider usage categories and USD cost snapshots.

Historic rows retain their original ``unknown_price`` semantics; this
migration deliberately does not attempt to reconstruct cache usage or costs.

Revision ID: c4d7e1f9a2b3
Revises: c3e5a7b9d024
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d7e1f9a2b3"
down_revision: Union[str, None] = "c3e5a7b9d024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("usage_records") as batch_op:
        batch_op.add_column(
            sa.Column("cached_input_tokens", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("cache_write_input_tokens", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("cost_usd", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("fx_chf_per_usd", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("usage_records") as batch_op:
        batch_op.drop_column("fx_chf_per_usd")
        batch_op.drop_column("cost_usd")
        batch_op.drop_column("cache_write_input_tokens")
        batch_op.drop_column("cached_input_tokens")
