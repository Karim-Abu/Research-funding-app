"""Comparison-scoped guards (Milestone 9I-B).

The structuring model call runs with run_id=None, so the gateway's run-scoped CostGuard
performs no aggregation (binding rule: never aggregate under run_id=null). The
comparison-level limits are enforced here: at most ONE successful generation per
comparison and a hard cap on persisted items.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.db.models import MarketComparison

MAX_ITEMS_PER_COMPARISON = 20


@dataclass(frozen=True)
class CostDecision:
    allowed: bool
    reason: str


def pre_check_generation(comparison: MarketComparison) -> CostDecision:
    """Allow generation only once per comparison (idempotent re-runs are skipped)."""
    if comparison.generation_status == "succeeded":
        return CostDecision(False, "already_generated")
    return CostDecision(True, "")
