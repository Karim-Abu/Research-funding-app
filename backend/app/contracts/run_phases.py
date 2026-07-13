"""Read-only Phasen-Contract für GET /runs/{run_id}/phases (additiv).

Nutzerphasen + technische Zusammenfassung. Das Status-Vokabular der Phasen ist
eigenständig (kein Requirement-/Evidenz-Status): pending | running | succeeded
| failed | skipped. ``detail`` enthält Zähler und Skip-Gründe, nie Rohtexte.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RunPhaseKey = Literal[
    "prepare_documents",
    "detect_facts",
    "formal_checks",
    "web_research",
    "draft_fields",
    "quality_review",
]
RunPhaseStatus = Literal["pending", "running", "succeeded", "failed", "skipped"]


class RunPhaseOut(BaseModel):
    phase_key: RunPhaseKey
    status: RunPhaseStatus
    started_at: datetime | None = None
    ended_at: datetime | None = None
    error_code: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class AgentUsageSummary(BaseModel):
    agent_id: str
    invocations: int
    providers: list[str]
    models: list[str]
    input_tokens: int
    output_tokens: int
    # Summe NUR über cost_status='priced'; unbepreiste Calls werden separat
    # ausgewiesen und nie als «kostenlos» gelesen.
    priced_cost_chf: float
    has_unpriced_usage: bool
    latency_ms_total: int
    generation_kinds: list[str] = []
    model_calls: int = 0
    prompt_versions: list[str] = []


class RunTechnicalSummary(BaseModel):
    run_id: str
    agents: list[AgentUsageSummary]
    priced_cost_chf_total: float
    has_unpriced_usage: bool
    # True/False nur wenn A2 UND A3 gelaufen sind; sonst null. Bei True darf
    # die UI keine «unabhängige Zweitmeinung» darstellen.
    same_provider_a2_a3: bool | None = None
    model_called: bool = False


class RunPhases(BaseModel):
    run_id: str
    run_status: str
    phases: list[RunPhaseOut]
    technical: RunTechnicalSummary
