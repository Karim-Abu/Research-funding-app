"""Central tool-access policy matrix (Milestone 9J).

ONE authoritative table mapping (data class × tool) → decision, used as the documented
single source of truth for *which external surface a data class may touch*. It is
**fail-closed**: any pair not explicitly allowed is ``BLOCKED``.

This wraps — it does NOT replace — the existing gates
(``app.research.policy.evaluate_web_research``, ``app.agents.data_policy.evaluate``,
``app.runs.cloud_policy``). The Search Query Firewall consults ``decide`` before any web
provider call; the existing web gate still runs, so D0 behaviour is unchanged.

Decisions:
  ALLOW                    — permitted (D0 web / local DB / cloud-confirmed LLM).
  ALLOW_IF_CLOUD_CONFIRMED — permitted only with an existing cloud confirmation (M9D.2).
  REQUIRE_SANITIZED_APPROVAL — permitted only with a firewall-sanitized + human-approved
                               query (D1/D2 web research).
  METADATA_ONLY            — only metadata/hashes may be written (logs).
  BLOCKED                  — never permitted in the beta.
"""
from __future__ import annotations

from enum import StrEnum

from app.security.data_class import DataClass


class Tool(StrEnum):
    AZURE_LLM_GATEWAY = "azure_llm_gateway"
    DIRECT_PROVIDER = "direct_provider"
    FIRECRAWL_WEBRESEARCH = "firecrawl_webresearch"
    MARKET_COMPARISON_LLM = "market_comparison_llm"
    A2_DRAFTING = "a2_drafting"
    A3_REVIEW = "a3_review"
    EXPORT = "export"
    LOGS = "logs"
    LOCAL_DB = "local_db"
    PROVIDER_VECTOR_STORE = "provider_vector_store"


class Decision(StrEnum):
    ALLOW = "allow"
    ALLOW_IF_CLOUD_CONFIRMED = "allow_if_cloud_confirmed"
    REQUIRE_SANITIZED_APPROVAL = "require_sanitized_approval"
    METADATA_ONLY = "metadata_only"
    BLOCKED = "blocked"


# Only ALLOWED/conditioned pairs are listed; every unlisted pair is BLOCKED (fail-closed).
_MATRIX: dict[tuple[DataClass, Tool], Decision] = {
    # ---- D0 public/synthetic: broad allow; logs metadata-only -------------------
    (DataClass.D0_PUBLIC, Tool.AZURE_LLM_GATEWAY): Decision.ALLOW_IF_CLOUD_CONFIRMED,
    (DataClass.D0_PUBLIC, Tool.DIRECT_PROVIDER): Decision.ALLOW_IF_CLOUD_CONFIRMED,
    (DataClass.D0_PUBLIC, Tool.FIRECRAWL_WEBRESEARCH): Decision.ALLOW,
    (DataClass.D0_PUBLIC, Tool.MARKET_COMPARISON_LLM): Decision.ALLOW_IF_CLOUD_CONFIRMED,
    (DataClass.D0_PUBLIC, Tool.A2_DRAFTING): Decision.ALLOW_IF_CLOUD_CONFIRMED,
    (DataClass.D0_PUBLIC, Tool.A3_REVIEW): Decision.ALLOW_IF_CLOUD_CONFIRMED,
    (DataClass.D0_PUBLIC, Tool.EXPORT): Decision.ALLOW,
    (DataClass.D0_PUBLIC, Tool.LOGS): Decision.METADATA_ONLY,
    (DataClass.D0_PUBLIC, Tool.LOCAL_DB): Decision.ALLOW,
    # provider vector store stays blocked even for D0 (no stateful provider features).
    # ---- D1 internal: external LLM blocked unless approved; web sanitized+approved
    (DataClass.D1_INTERNAL, Tool.AZURE_LLM_GATEWAY): Decision.ALLOW_IF_CLOUD_CONFIRMED,
    (DataClass.D1_INTERNAL, Tool.FIRECRAWL_WEBRESEARCH): Decision.REQUIRE_SANITIZED_APPROVAL,
    (DataClass.D1_INTERNAL, Tool.EXPORT): Decision.ALLOW,
    (DataClass.D1_INTERNAL, Tool.LOGS): Decision.METADATA_ONLY,
    (DataClass.D1_INTERNAL, Tool.LOCAL_DB): Decision.ALLOW,
    # ---- D2 confidential idea: no raw external; web only via firewall+approval ---
    (DataClass.D2_CONFIDENTIAL_IDEA, Tool.AZURE_LLM_GATEWAY): Decision.ALLOW_IF_CLOUD_CONFIRMED,
    (DataClass.D2_CONFIDENTIAL_IDEA, Tool.FIRECRAWL_WEBRESEARCH): Decision.REQUIRE_SANITIZED_APPROVAL,
    (DataClass.D2_CONFIDENTIAL_IDEA, Tool.EXPORT): Decision.ALLOW,
    (DataClass.D2_CONFIDENTIAL_IDEA, Tool.LOGS): Decision.METADATA_ONLY,
    (DataClass.D2_CONFIDENTIAL_IDEA, Tool.LOCAL_DB): Decision.ALLOW,
    # ---- D3 NDA: all external AI/web blocked; only local metadata ----------------
    (DataClass.D3_NDA_BLOCKED, Tool.LOGS): Decision.METADATA_ONLY,
    (DataClass.D3_NDA_BLOCKED, Tool.LOCAL_DB): Decision.ALLOW,
    # ---- UNKNOWN: blocked everywhere (only local metadata logging) ---------------
    (DataClass.UNKNOWN, Tool.LOGS): Decision.METADATA_ONLY,
}


def decide(data_class: DataClass, tool: Tool) -> Decision:
    """Return the policy decision for a (data class, tool) pair. Fail-closed:
    any pair not explicitly permitted is ``BLOCKED``."""
    return _MATRIX.get((data_class, tool), Decision.BLOCKED)


def web_research_decision(data_class: DataClass) -> Decision:
    """Convenience accessor for the Firecrawl/web-research column."""
    return decide(data_class, Tool.FIRECRAWL_WEBRESEARCH)
