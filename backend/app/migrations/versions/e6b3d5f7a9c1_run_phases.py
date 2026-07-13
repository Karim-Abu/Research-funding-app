"""run phases

Persistierter Phasenstatus je Analyse-Lauf (Reload zeigt denselben Stand):
je Lauf und Nutzerphase eine Zeile mit Status, Start/Ende, Fehlercode und
Zähler-Detail (nie Rohtexte/Prompts/Keys). Rein additiv: neue Tabelle;
Downgrade entfernt nur diese Tabelle.

Revision ID: e6b3d5f7a9c1
Revises: d8f2a4c6e0b3
Create Date: 2026-07-11 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e6b3d5f7a9c1'
down_revision: Union[str, None] = 'd8f2a4c6e0b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "run_phases",
        sa.Column("run_phase_id", sa.String(), primary_key=True),
        sa.Column(
            "run_id", sa.String(), sa.ForeignKey("analysis_runs.run_id"),
            nullable=False,
        ),
        sa.Column("phase_key", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "phase_key", name="uq_run_phase_key"),
    )
    op.create_index("ix_run_phases_run_id", "run_phases", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_run_phases_run_id", table_name="run_phases")
    op.drop_table("run_phases")
