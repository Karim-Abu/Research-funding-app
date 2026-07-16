"""Deterministic partner-research query planner (RESEARCH.2).

Pure, no LLM, no network. Turns a small set of **D0/public** topic fields into 5
public-safe organisation/topic query candidates aimed at research labs, universities,
universities of applied sciences, and competence centers — never a person. It NEVER
reads confidential/real-project text (raw idea, partner names, budget figures, personal
data, canary tokens): the input ``PartnerTopic`` only carries public, synthetic-safe topic
descriptors. The real Search Query Firewall re-validates every query at execution — this
planner is advisory.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# The fine-grained partner query purposes (planner-level; distinct from the coarse
# internal ResearchTask.purpose = "partner_research_org_topic").
QUERY_PURPOSES = (
    "university_lab",
    "research_group",
    "university_institute",
    "competence_center",
    "applied_sciences",
)

# Defensive public-safety detectors. The planner input is D0-only by construction, so
# these should never fire; if they do, the candidate is marked not public_safe with a
# reason and the runner skips it (the firewall would block it anyway).
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\+?\d[\d\s()/-]{6,}\d")
_MONEY_RE = re.compile(r"(?:chf|eur|usd|\$|€|£)\s?\d", re.IGNORECASE)


@dataclass(frozen=True)
class PartnerTopic:
    """Public, synthetic-safe topic descriptors — the ONLY planner input.

    None of these fields may contain confidential/real-project data or a person's name.
    ``region`` is optional (public geography only, e.g. "Switzerland")."""

    application_domain: str
    technology_area: str
    competence_areas: list[str] = field(default_factory=list)
    region: str | None = "Switzerland"


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


def _templates(topic: PartnerTopic) -> dict[str, str]:
    domain = _clean(topic.application_domain)
    tech = _clean(topic.technology_area)
    region = _clean(topic.region or "")
    competence = _clean(", ".join(topic.competence_areas)) if topic.competence_areas else domain
    reg = f" {region}" if region else ""
    return {
        "university_lab": f"Swiss applied {tech} lab {domain}",
        "research_group": f"{domain} {tech} research group publications track record{reg}",
        "university_institute": f"{tech} {domain} university{reg}",
        "competence_center": f"{domain} {competence} competence center{reg}",
        "applied_sciences": f"applied sciences {tech} {domain} research{reg}",
    }


def plan_partner_queries(
    topic: PartnerTopic, *, data_mode: str = "synthetic_eval"
) -> list[QueryCandidate]:
    """Deterministically plan 5 public-safe partner/competence query candidates (D0-only).

    ``data_mode`` is descriptive (``synthetic_eval`` | ``fake_test``); the MVP is D0-only
    Every candidate is marked approval-required; the canonical brief workflow creates
    the actual single-use approval after the deterministic firewall preview.
    Organisation/topic only — never a person's name.
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
