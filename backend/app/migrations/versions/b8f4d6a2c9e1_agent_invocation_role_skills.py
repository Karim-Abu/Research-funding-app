"""add versioned role and skill metadata to agent invocations

Revision ID: b8f4d6a2c9e1
Revises: a7e3c9f1b5d2
Create Date: 2026-07-15 00:30:00.000000

Existing invocation rows deliberately remain nullable: no historic role/skill
split is inferred from a legacy profile id. New gateway writes contain IDs,
versions and safe input-artifact references only.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8f4d6a2c9e1"
down_revision: Union[str, None] = "a7e3c9f1b5d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agent_invocations", sa.Column("role_id", sa.String(), nullable=True))
    op.add_column("agent_invocations", sa.Column("role_version", sa.String(), nullable=True))
    op.add_column("agent_invocations", sa.Column("skill_id", sa.String(), nullable=True))
    op.add_column("agent_invocations", sa.Column("skill_version", sa.String(), nullable=True))
    op.add_column("agent_invocations", sa.Column("contract_version", sa.String(), nullable=True))
    op.add_column("agent_invocations", sa.Column("input_artifact_refs", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_invocations", "input_artifact_refs")
    op.drop_column("agent_invocations", "contract_version")
    op.drop_column("agent_invocations", "skill_version")
    op.drop_column("agent_invocations", "skill_id")
    op.drop_column("agent_invocations", "role_version")
    op.drop_column("agent_invocations", "role_id")
