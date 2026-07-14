"""Test helpers for the mandatory public-safe research-brief workflow."""
from __future__ import annotations

from tests.conftest import unsafe_headers


def approve_research_brief(
    client,
    csrf: str,
    project_id: str,
    *,
    modules: list[str] | None = None,
    application_domain: str = "manufacturing quality assurance",
    technology_class: str = "industrial AI anomaly detection",
    target_customer_segments: list[str] | None = None,
    region: str = "Switzerland",
    competence_needs: list[str] | None = None,
) -> dict:
    payload = {
        "application_domain": application_domain,
        "technology_class": technology_class,
        "target_customer_segments": target_customer_segments or ["manufacturing SMEs"],
        "region": region,
        "competence_needs": competence_needs or ["applied machine learning"],
        "modules": modules or [
            "market_growth",
            "competition_alternatives",
            "customer_problem",
        ],
    }
    saved = client.put(
        f"/api/v1/projects/{project_id}/research-brief",
        json=payload,
        headers=unsafe_headers(csrf),
    )
    assert saved.status_code == 200, saved.text
    brief = saved.json()
    approved = client.post(
        f"/api/v1/research-briefs/{brief['research_brief_id']}/approve",
        headers=unsafe_headers(csrf),
    )
    assert approved.status_code == 200, approved.text
    return approved.json()

