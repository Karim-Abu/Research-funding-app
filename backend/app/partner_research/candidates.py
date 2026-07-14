"""PartnerCandidate view over ResearchResult (RESEARCH.2).

A PartnerCandidate is a **potential fit**, never a confirmed evidence or an eligibility
guarantee: no Innosuisse contribution-eligibility is asserted, no contact is made, and no
``Partner`` DB row is created here. The view derives ``candidate_type``/
``potential_project_role`` deterministically from the originating query purpose, and
``expertise_keywords`` structurally from the input topic — never from parsing/inventing
snippet content. No new DB model — ``ResearchResult`` carries the persistent state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from app.db.models import ResearchResult
from app.partner_research.planner import PartnerTopic

CandidateType = Literal[
    "university_lab", "university", "university_of_applied_sciences",
    "competence_center", "research_institute", "company", "unknown",
]
Confidence = Literal["low", "medium", "high"]

# Fine query purpose (planner) → PartnerCandidate type.
_CANDIDATE_TYPE: dict[str, CandidateType] = {
    "university_lab": "university_lab",
    "research_group": "research_institute",
    "university_institute": "university",
    "competence_center": "competence_center",
    "applied_sciences": "university_of_applied_sciences",
}

_POTENTIAL_ROLE: dict[str, str] = {
    "university_lab":
        "Mögliche fachliche Passung als Forschungslabor-Partner (nicht geprüft).",
    "research_institute":
        "Mögliche fachliche Passung als Forschungspartner (nicht geprüft).",
    "university":
        "Mögliche fachliche Passung als akademischer Partner (nicht geprüft).",
    "competence_center":
        "Mögliches Kompetenzzentrum für fachlichen Austausch (nicht geprüft).",
    "university_of_applied_sciences":
        "Mögliche fachliche Passung als Umsetzungspartner, Fachhochschule (nicht geprüft).",
    "company": "Mögliche fachliche Passung (nicht geprüft).",
    "unknown": "Fachliche Passung nicht bestimmbar (nicht geprüft).",
}

# Fixed, always-present disclaimers — never a confirmed fact, never an invitation to
# contact the candidate automatically.
_LIMITATIONS = [
    "Kandidat basiert auf einer automatisierten Websuche, kein bestätigter Beleg.",
    "Keine Eignungsprüfung durchgeführt — nur eine mögliche fachliche Passung, kein "
    "\"bester Partner\".",
    "Keine Innosuisse-Förderfähigkeit oder Beitragsberechtigung bestätigt.",
    "Kein Kontakt aufgenommen; Standort-/Organisationsangaben nicht verifiziert.",
]


@dataclass(frozen=True)
class PartnerCandidate:
    result_id: str
    research_task_id: str
    candidate_name: str
    organization: str
    candidate_type: CandidateType
    country_or_region: str | None
    expertise_keywords: list[str]
    potential_project_role: str
    swiss_relevance: bool | None
    evidence_url: str
    evidence_snippet: str | None
    confidence: Confidence
    limitations: list[str]
    status: Literal["needs_human_review"]
    source_document_id: str | None


def _host(url: str) -> str:
    try:
        return urlparse(url).hostname or url
    except ValueError:
        return url


def _expertise_keywords(topic: PartnerTopic) -> list[str]:
    return [topic.technology_area, topic.application_domain, *topic.competence_areas]


def to_partner_candidates(
    purpose_by_task_id: dict[str, str],
    results: list[ResearchResult],
    *,
    topic: PartnerTopic,
) -> list[PartnerCandidate]:
    """Map ResearchResults to PartnerCandidates using each result's task→query purpose.

    ``confidence`` is deterministic and structural: rank-1 candidates are "medium"; if the
    SAME host also ranked #1 for a DIFFERENT query purpose, that corroboration bumps it to
    "high" (the only source of "high" — never a reading of snippet content). Everything
    else is "low".
    """
    keywords = _expertise_keywords(topic)
    rank1_hosts_by_purpose: dict[str, set[str]] = {}
    for r in results:
        if r.status == "candidate" and r.provider_rank == 1:
            purpose = purpose_by_task_id.get(r.research_task_id, "")
            rank1_hosts_by_purpose.setdefault(_host(r.source_url), set()).add(purpose)

    candidates: list[PartnerCandidate] = []
    for r in results:
        purpose = purpose_by_task_id.get(r.research_task_id, "")
        candidate_type = _CANDIDATE_TYPE.get(purpose, "unknown")
        if r.status == "candidate" and r.provider_rank == 1:
            corroborating_purposes = rank1_hosts_by_purpose.get(_host(r.source_url), set())
            confidence: Confidence = "high" if len(corroborating_purposes) > 1 else "medium"
        else:
            confidence = "low"
        candidates.append(
            PartnerCandidate(
                result_id=r.result_id,
                research_task_id=r.research_task_id,
                candidate_name=r.title,
                organization=r.title,
                candidate_type=candidate_type,
                # The research brief's region scopes the query; it is not evidence for
                # the candidate's actual location or Swiss nexus.
                country_or_region=None,
                expertise_keywords=keywords,
                potential_project_role=_POTENTIAL_ROLE.get(
                    candidate_type, _POTENTIAL_ROLE["unknown"]
                ),
                swiss_relevance=None,
                evidence_url=r.source_url,
                evidence_snippet=r.snippet,
                confidence=confidence,
                limitations=list(_LIMITATIONS),
                status="needs_human_review",
                source_document_id=r.source_document_id,
            )
        )
    return candidates
