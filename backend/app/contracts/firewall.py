"""Search Query Firewall API schemas (Milestone 9J) — beta-internal, code-only.

Deliberately provider-agnostic and leak-free: no provider/model names, no raw query is
ever echoed back, and the numeric risk score is mapped to a coarse label for the UI.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FirewallDecision = Literal["allow", "require_human_approval", "block"]
RiskLabel = Literal["low", "medium", "high"]


class FirewallPreviewRequest(BaseModel):
    raw_query: str = Field(min_length=1)
    intended_tool: Literal["firecrawl", "web_research"] = "firecrawl"
    purpose: str | None = None


class RedactionItem(BaseModel):
    category: str
    label: str
    count: int


class FirewallPreviewResponse(BaseModel):
    data_class: str
    decision: FirewallDecision
    risk_label: RiskLabel
    # The sanitized public-safe query (what Firecrawl would receive). Empty when blocked.
    sanitized_query: str
    redaction_summary: list[RedactionItem] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    # Present only when decision == require_human_approval (a pending approval was created).
    approval_id: str | None = None


class ApprovalStatusResponse(BaseModel):
    approval_id: str
    status: Literal["pending", "approved", "rejected", "expired", "used"]
    decision: FirewallDecision
    risk_label: RiskLabel
    sanitized_query: str
    redaction_summary: list[RedactionItem] = Field(default_factory=list)
