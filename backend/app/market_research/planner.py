"""Deterministic market-query planner (RESEARCH.1a).

Pure, no LLM, no network. Turns a small set of **D0/public** topic fields into 3–5
public-safe market-research query candidates. It NEVER reads confidential/real-project
text (raw idea, partner names, budget figures, personal data, canary tokens): the input
``MarketTopic`` only carries public, synthetic-safe topic descriptors. The real Search
Query Firewall re-validates every query at execution — this planner is advisory.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# The fine-grained market query purposes (planner-level; distinct from the coarse
# internal ResearchTask.purpose = "market_comparison").
QUERY_PURPOSES = (
    "market_size",
    "competitors_alternatives",
    "customer_pain",
    "go_to_market_channels",
    "pricing_willingness_to_pay",
)

# Defensive public-safety detectors. The planner input is D0-only by construction, so
# these should never fire; if they do, the candidate is marked not public_safe with a
# reason and the runner skips it (the firewall would block it anyway).
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\+?\d[\d\s()/-]{6,}\d")
_MONEY_RE = re.compile(r"(?:chf|eur|usd|\$|€|£)\s?\d", re.IGNORECASE)


@dataclass(frozen=True)
class MarketTopic:
    """Public, synthetic-safe topic descriptors — the ONLY planner input.

    None of these fields may contain confidential/real-project data. ``region`` is
    optional (public geography only, e.g. "Switzerland")."""

    application_domain: str
    technology_area: str
    target_customers: str
    region: str | None = None


@dataclass(frozen=True)
class QueryCandidate:
    query_text: str
    purpose: str
    source: str
    data_mode: str
    approval_required: bool
    public_safe: bool
    blocked_reason: str | None = None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _public_safe(query: str) -> str | None:
    """Return a blocked_reason if the query looks non-public, else None."""
    if _EMAIL_RE.search(query):
        return "contains_email"
    if _MONEY_RE.search(query):
        return "contains_budget_amount"
    if _PHONE_RE.search(query):
        return "contains_phone"
    return None


def _templates(topic: MarketTopic) -> dict[str, str]:
    domain = _clean(topic.application_domain)
    tech = _clean(topic.technology_area)
    customers = _clean(topic.target_customers)
    region = _clean(topic.region or "")
    reg = f" {region}" if region else ""
    return {
        "market_size": f"{domain} {tech} market size{reg}",
        "competitors_alternatives": f"{tech} {domain} competitors alternatives",
        "customer_pain": f"{domain} {customers} quality challenges pain points",
        "go_to_market_channels": f"{domain} {tech} go to market sales channels{reg}",
        "pricing_willingness_to_pay": f"{tech} {domain} pricing willingness to pay",
    }


def plan_market_queries(
    topic: MarketTopic, *, data_mode: str = "synthetic_eval"
) -> list[QueryCandidate]:
    """Deterministically plan 3–5 public-safe market-research queries (D0-only).

    ``data_mode`` is descriptive (``synthetic_eval`` | ``fake_test``). R8: JEDE
    planner-generierte Query braucht eine explizite menschliche Freigabe, bevor sie
    ausgeführt werden darf — ``approval_required`` ist daher immer True (die Firewall
    erzwingt zusätzlich weiterhin die Datenklasse).
    """
    candidates: list[QueryCandidate] = []
    for purpose, query in _templates(topic).items():
        query = _clean(query)
        if not query:
            continue
        reason = _public_safe(query)
        candidates.append(
            QueryCandidate(
                query_text=query,
                purpose=purpose,
                source="deterministic_planner",
                data_mode=data_mode,
                approval_required=True,
                public_safe=reason is None,
                blocked_reason=reason,
            )
        )
    return candidates
