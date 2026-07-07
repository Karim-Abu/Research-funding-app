"""finding v2 fields

R2.2 — additive nullable Spalten für das Issue-Modell v2 (Dedupe/Fix Queue):
``fingerprint`` (stabile technische Identität, R2.1), ``severity_class``
(sechs Klassen, R2.3), ``fix_recommendation``, ``last_seen_at`` — auf
``review_findings`` und ``open_issues``. Keine Daten werden verändert oder
gelöscht; ``finding_code`` bleibt unangetastet. ``message_template``/
``specific_message`` werden NICHT ergänzt: die spezifische Meldung ist
bereits ``description``, die Meldungsfamilie ist deterministisch aus
``finding_code`` ableitbar (Lesezeit, R2.4).

Revision ID: 7b091c3d3e24
Revises: 262f51ba5176
Create Date: 2026-07-07 19:42:32.745357

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7b091c3d3e24'
down_revision: Union[str, None] = '262f51ba5176'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("review_findings", "open_issues")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("fingerprint", sa.String(), nullable=True))
        op.add_column(table, sa.Column("severity_class", sa.String(), nullable=True))
        op.add_column(table, sa.Column("fix_recommendation", sa.Text(), nullable=True))
        op.add_column(
            table,
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "last_seen_at")
        op.drop_column(table, "fix_recommendation")
        op.drop_column(table, "severity_class")
        op.drop_column(table, "fingerprint")
