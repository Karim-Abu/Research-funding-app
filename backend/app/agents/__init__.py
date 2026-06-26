"""Agent infrastructure (Milestone 9A).

Backend-only foundation for future A1/A2/A3 model calls: AgentProfile registry,
ModelGateway, deterministic fake provider, dormant real-provider adapters, Data
Policy enforcement and CostGuard. A1/A2/A3 are NOT wired into the run graph in
M9A and no normal workflow depends on a real LLM.
"""
from __future__ import annotations

AGENT_PROMPT_DIR = "prompts"
