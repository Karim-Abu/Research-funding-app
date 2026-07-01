"""Reliability (M9K) API schemas — beta-internal, code-only (not in the finalized OpenAPI).

``claim_text`` is returned only to the authenticated, workspace-scoped Review UI (same
authorization as DraftVersion.text); it never enters audit/logs/export.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReliabilityClaimView(BaseModel):
    claim_id: str
    field_id: str
    claim_type: str
    strength: str
    requires_evidence: bool
    claim_text: str  # authenticated UI only (corr 14)
    lineage_status: str
    sufficiency_status: str
    reason: str | None = None


class ReliabilityFindingView(BaseModel):
    finding_id: str
    field_id: str | None = None
    severity: str
    description: str
    status: str
    finding_code: str
    target_type: str | None = None
    target_id: str | None = None


class RunQualitySummaryView(BaseModel):
    summary_id: str
    run_id: str
    status: str
    stale: bool
    quality_flag: str
    claim_count: int
    supported_claims: int
    weakly_supported_claims: int
    unsupported_claims: int
    conflicting_claims: int
    evidence_coverage: float
    evidence_correctness_sample_size: int
    evidence_correctness_sample_pass_rate: float
    review_required_count: int
    blocker_count: int
    warning_count: int
    fields_ready: int
    fields_needs_review: int
    false_consensus_risk_count: int
    semantic_drift_count: int
    raw_logging_detected: bool
    tool_leakage_detected: bool
    cost_chf: float | None = None
    cost_placeholder: bool = True
    latency_seconds: float | None = None
    summary_version: str
    generated_at: datetime


class ReliabilityView(BaseModel):
    run_id: str
    available: bool
    reliability_stale: bool
    summary: RunQualitySummaryView | None = None
    claims: list[ReliabilityClaimView] = []
    findings: list[ReliabilityFindingView] = []
