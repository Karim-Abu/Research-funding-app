"""Import-Mapping-Version und Abschnittsmetadaten.

Revision ID: 1d4f8a2c6b90
Revises: e6b3d5f7a9c1
Create Date: 2026-07-13
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1d4f8a2c6b90"
down_revision: Union[str, None] = "e6b3d5f7a9c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("import_candidates") as batch:
        batch.add_column(
            sa.Column(
                "mapping_version",
                sa.String(),
                nullable=False,
                server_default="legacy-anchor-v1",
            )
        )
        batch.add_column(
            sa.Column(
                "mapping_status",
                sa.String(),
                nullable=False,
                server_default="content_detected",
            )
        )
        batch.add_column(
            sa.Column(
                "section_metadata",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )

    # Nur sichere, bereits vorhandene Zustände zurückfüllen. Alte Rohtexte
    # werden weder gelesen noch in Migrationsausgaben geschrieben.
    op.execute(
        "UPDATE import_candidates SET mapping_status = 'empty' "
        "WHERE trim(extracted_text) = ''"
    )
    op.execute(
        "UPDATE import_candidates SET mapping_status = 'uncertain' "
        "WHERE confidence = 'uncertain' AND trim(extracted_text) <> ''"
    )


def downgrade() -> None:
    with op.batch_alter_table("import_candidates") as batch:
        batch.drop_column("section_metadata")
        batch.drop_column("mapping_status")
        batch.drop_column("mapping_version")
