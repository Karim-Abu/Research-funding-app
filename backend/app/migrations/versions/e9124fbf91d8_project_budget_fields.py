"""project budget fields

Slice 1: nullable structured budget/duration columns on projects — inputs for
the deterministic 40-60% and 5%-cash budget rules (no BudgetPlan entity).

Revision ID: e9124fbf91d8
Revises: f3d7a9c2e5b1
Create Date: 2026-07-05 01:56:47.542168

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e9124fbf91d8'
down_revision: Union[str, None] = 'f3d7a9c2e5b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FLOAT_COLUMNS = (
    "direct_total_project_costs_excluding_overhead",
    "implementation_own_contribution",
    "cash_contribution",
    "total_requested_funding",
)


def upgrade() -> None:
    for name in _FLOAT_COLUMNS:
        op.add_column("projects", sa.Column(name, sa.Float(), nullable=True))
    op.add_column(
        "projects", sa.Column("budget_exception_basis", sa.String(), nullable=True)
    )
    op.add_column(
        "projects", sa.Column("duration_months", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("projects", "duration_months")
    op.drop_column("projects", "budget_exception_basis")
    for name in reversed(_FLOAT_COLUMNS):
        op.drop_column("projects", name)
