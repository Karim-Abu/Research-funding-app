"""Deterministic MarketTopic suggestion from a project (RESEARCH.1b).

Only reads ``project.innovation_field`` — a broad field-of-innovation label (e.g. "ICT /
Industrial AI"), never the raw idea/description. ``target_customers``/``region`` are
always generic, public-safe defaults. The result is a *suggestion* the user reviews and
may edit before any query is generated or executed (see the Query Preview / review step).
"""
from __future__ import annotations

import re

from app.db.models import Project
from app.market_research.planner import MarketTopic

_SPLIT_RE = re.compile(r"\s*(?:/| und | and |,)\s*", re.IGNORECASE)
_DEFAULT_DOMAIN = "Technologie"
_DEFAULT_TECHNOLOGY = "Innovation"
_DEFAULT_CUSTOMERS = "Unternehmen und Organisationen in der Schweiz"
_DEFAULT_REGION = "Schweiz"


def suggest_market_topic(project: Project) -> MarketTopic:
    field = (project.innovation_field or "").strip()
    if not field:
        return MarketTopic(
            application_domain=_DEFAULT_DOMAIN,
            technology_area=_DEFAULT_TECHNOLOGY,
            target_customers=_DEFAULT_CUSTOMERS,
            region=_DEFAULT_REGION,
        )
    parts = [p for p in _SPLIT_RE.split(field) if p]
    domain = parts[0] if parts else _DEFAULT_DOMAIN
    technology = parts[1] if len(parts) > 1 else domain
    return MarketTopic(
        application_domain=domain,
        technology_area=technology,
        target_customers=_DEFAULT_CUSTOMERS,
        region=_DEFAULT_REGION,
    )
