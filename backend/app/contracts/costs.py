"""Read-only, project-scoped provider usage and cost view."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


CostCompleteness = Literal["priced", "partial", "unknown_price", "not_applicable"]


class UsageCost(BaseModel):
    status: CostCompleteness
    # Exact provider list-price total. ``None`` means at least one external
    # call is not fully priceable, so no seemingly exact total is returned.
    usd: float | None = None
    chf_reference: float | None = None
    known_usd: float = 0.0
    known_chf_reference: float = 0.0
    unpriced_call_count: int = 0


class CostExecution(BaseModel):
    id: str
    role_label: str
    # Stable system-role identifier (A1/A2/A3/RESEARCH_*), null for historic or
    # deterministic rows. The UI maps it to a human role label; kept separate
    # from ``role_label`` (which stays the technical route alias for
    # backward compatibility).
    role_id: str | None = None
    provider: str | None = None
    model: str | None = None
    status: str
    input_tokens: int
    cached_input_tokens: int
    cache_write_input_tokens: int
    output_tokens: int
    latency_ms: int | None = None
    cost: UsageCost
    price_version: str | None = None


class ProjectCostRun(BaseModel):
    id: str
    started_at: datetime
    ended_at: datetime | None = None
    status: str
    stop_reason: str | None = None
    processing_mode: str
    user: str
    max_cost_chf: float | None = None
    input_tokens: int
    cached_input_tokens: int
    cache_write_input_tokens: int
    output_tokens: int
    llm_calls: int
    web_calls: int
    cost: UsageCost
    executions: list[CostExecution]


class ProjectCostView(BaseModel):
    project_id: str
    billing_currency: Literal["USD"] = "USD"
    chf_reference_source: str
    chf_reference_rate: float
    chf_reference_as_of: str
    # Project-scoped public web-research (Firecrawl) tool calls. These are
    # credit-based and carry no per-call USD list price, so they are reported as
    # a count only, never folded into the priced USD totals.
    web_research_calls: int = 0
    runs: list[ProjectCostRun]
