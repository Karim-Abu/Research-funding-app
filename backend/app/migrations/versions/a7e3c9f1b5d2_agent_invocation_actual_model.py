"""agent invocation actual model

Ebene E (Live-Readiness) — additive nullable Spalte ``actual_model_id`` auf
``agent_invocations``: das vom Provider in der Antwort GEMELDETE Modell
(Alias-Auflösung). ``model_id`` bleibt das angefragte Routen-Modell.
Bestandszeilen bleiben NULL (nicht mehr beweisbar). Downgrade entfernt nur
die neue Spalte.

Revision ID: a7e3c9f1b5d2
Revises: f9c2a7d4e1b6
Create Date: 2026-07-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7e3c9f1b5d2'
down_revision: Union[str, None] = 'f9c2a7d4e1b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_invocations",
        sa.Column("actual_model_id", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_invocations", "actual_model_id")
