"""RUN 3A readiness metadata and simplified research brief.

Revision ID: a1c3e5f7b902
Revises: f7b9d2c4a681
"""
from __future__ import annotations

import json
import unicodedata

from alembic import op
import sqlalchemy as sa


revision = "a1c3e5f7b902"
down_revision = "f7b9d2c4a681"
branch_labels = None
depends_on = None


def _normalize(value: object) -> str:
    return unicodedata.normalize("NFC", str(value or "")).strip()


def _list(value: object) -> list[str]:
    if isinstance(value, list):
        items = value
    else:
        try:
            items = json.loads(str(value or "[]"))
        except (TypeError, ValueError, json.JSONDecodeError):
            items = []
    result: list[str] = []
    seen: set[str] = set()
    for value in items if isinstance(items, list) else []:
        item = _normalize(value)
        key = item.casefold()
        if item and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _backfill_research_briefs() -> None:
    connection = op.get_bind()
    rows = connection.execute(sa.text(
        "SELECT research_brief_id, application_domain, technology_class, "
        "target_customer_segments, competence_needs FROM research_briefs"
    )).mappings()
    for row in rows:
        domain = _normalize(row["application_domain"])
        technology = _normalize(row["technology_class"])
        goal = ": ".join(value for value in (domain, technology) if value)
        tags = _list(row["target_customer_segments"])
        for item in _list(row["competence_needs"]):
            if item.casefold() not in {value.casefold() for value in tags}:
                tags.append(item)
        connection.execute(
            sa.text(
                "UPDATE research_briefs SET research_goal=:goal, search_tags=:tags "
                "WHERE research_brief_id=:brief_id"
            ),
            {
                "brief_id": row["research_brief_id"],
                "goal": goal,
                "tags": json.dumps(tags, ensure_ascii=False),
            },
        )


def upgrade() -> None:
    with op.batch_alter_table("provider_preflight_results") as batch:
        batch.add_column(sa.Column("reason_code", sa.String(), nullable=True))
        batch.add_column(sa.Column(
            "retryable", sa.Boolean(), nullable=False, server_default=sa.false()
        ))
        batch.add_column(sa.Column(
            "configuration_fingerprint", sa.String(), nullable=True
        ))
        batch.add_column(sa.Column("registry_version", sa.String(), nullable=True))
        batch.add_column(sa.Column("pricing_version", sa.String(), nullable=True))
    with op.batch_alter_table("research_briefs") as batch:
        batch.add_column(sa.Column(
            "research_goal", sa.String(), nullable=False, server_default=""
        ))
        batch.add_column(sa.Column(
            "search_tags", sa.JSON(), nullable=False, server_default="[]"
        ))
    _backfill_research_briefs()


def downgrade() -> None:
    with op.batch_alter_table("research_briefs") as batch:
        batch.drop_column("search_tags")
        batch.drop_column("research_goal")
    with op.batch_alter_table("provider_preflight_results") as batch:
        batch.drop_column("pricing_version")
        batch.drop_column("registry_version")
        batch.drop_column("configuration_fingerprint")
        batch.drop_column("retryable")
        batch.drop_column("reason_code")
