"""import candidate edited text

«Bearbeitet übernommen» vor dem ersten Analyse-Run: der editierte Text eines
ImportCandidate braucht einen Speicherort, solange kein run-gebundener Draft
existiert. ``extracted_text`` bleibt unverändert erhalten (Originalausschnitt
für den HITL-Vergleich). Rein additiv: eine nullable Text-Spalte; Downgrade
entfernt nur diese Spalte (batch mode für SQLite).

Revision ID: c7d9e2f4a6b8
Revises: b2c4e6a8d0f1
Create Date: 2026-07-11 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7d9e2f4a6b8'
down_revision: Union[str, None] = 'b2c4e6a8d0f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("import_candidates") as batch:
        batch.add_column(sa.Column("edited_text", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("import_candidates") as batch:
        batch.drop_column("edited_text")
