"""usage cost status

EVAL.1 — additive Kostensemantik-Spalten auf ``usage_records``:
``cost_status`` (priced | unknown_price | not_applicable, kein DB-Enum) und
``price_version`` (nullable). Rein additiv: keine Tabelle/Zeile wird entfernt;
Downgrade entfernt nur die beiden neuen Spalten. server_default
``unknown_price`` ist der fail-closed Backfill für Bestandszeilen (deren
tatsächliche Kostenlage nicht mehr pro Zeile beweisbar ist).

Revision ID: b2c4e6a8d0f1
Revises: a3f8c2d91e47
Create Date: 2026-07-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c4e6a8d0f1'
down_revision: Union[str, None] = 'a3f8c2d91e47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usage_records",
        sa.Column(
            "cost_status", sa.String(), nullable=False,
            server_default="unknown_price",
        ),
    )
    op.add_column(
        "usage_records", sa.Column("price_version", sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("usage_records", "price_version")
    op.drop_column("usage_records", "cost_status")
