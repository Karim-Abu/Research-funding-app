"""partner review comment

Pflicht-MVP-Feld «Kommentar bei unklar/Nein»: kurze menschliche Begründung,
wenn Unabhängigkeit/Beitragsberechtigung/Wertschöpfung explizit als unklar
oder nicht bestätigt erfasst wird. Rein additiv: eine nullable Text-Spalte;
Downgrade entfernt nur diese Spalte (batch mode für SQLite).

Revision ID: d8f2a4c6e0b3
Revises: c7d9e2f4a6b8
Create Date: 2026-07-11 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8f2a4c6e0b3'
down_revision: Union[str, None] = 'c7d9e2f4a6b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("partners") as batch:
        batch.add_column(sa.Column("review_comment", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("partners") as batch:
        batch.drop_column("review_comment")
