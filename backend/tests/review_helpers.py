"""Shared setup for Milestone 7 review tests."""
from __future__ import annotations

import uuid

from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    VALID_CLASSIFICATION,
    create_project,
    login,
    unsafe_headers,
)

SOURCE_TEXT = (
    "Der Umsetzungspartner ist in der Schweiz wertschöpfend tätig. "
    "Ein beitragsberechtigter Schweizer Forschungspartner ist eingebunden."
)
ABSTRACT = "INTRO.APP.ABSTRACT"
NAME = "INTRO.APP.NAME"

_IMPL_PARTNER = {
    "name": "Industrie AG",
    "partner_type": "implementation_partner",
    "country": "CH",
    "swiss_value_creation": True,
}
_RESEARCH_PARTNER = {
    "name": "ETH",
    "partner_type": "research_partner",
    "country": "CH",
    "research_partner_eligibility_status": "eligible",
}


def mut(csrf: str) -> dict[str, str]:
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = uuid.uuid4().hex
    return headers


def setup_completed_run(
    client, *, with_research_partner: bool = True, title: str = "Review Project"
):
    """Create a project + source + partners and a synchronously completed run."""
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf, title)
    client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={
            "name": "Quelle",
            "text": SOURCE_TEXT,
            "data_classification": VALID_CLASSIFICATION,
        },
        headers=mut(csrf),
    )
    partners = [_IMPL_PARTNER]
    if with_research_partner:
        partners.append(_RESEARCH_PARTNER)
    for partner in partners:
        client.post(
            f"/api/v1/projects/{project_id}/partners", json=partner, headers=mut(csrf)
        )
    run = client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={
            "settings": {
                "processing_mode": "deterministic_only",
                "max_cost_chf": 0,
                "max_llm_calls": 0,
                "max_web_calls": 0,
            }
        },
        headers=mut(csrf),
    ).json()
    run_id = run["resource_id"]
    assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "completed"
    return csrf, project_id, run_id


def get_review(client, run_id) -> dict:
    res = client.get(f"/api/v1/runs/{run_id}/review")
    assert res.status_code == 200, res.text
    return res.json()


def clean_field(client, csrf, run_id, field_id, text) -> dict:
    draft = client.get(f"/api/v1/runs/{run_id}/fields/{field_id}").json()
    base = draft["current_version"]["draft_version_id"]
    res = client.patch(
        f"/api/v1/runs/{run_id}/fields/{field_id}",
        json={"base_version_id": base, "text": text},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200, res.text
    return res.json()


def run_recheck(client, csrf, run_id):
    pkg = get_review(client, run_id)
    return client.post(
        f"/api/v1/runs/{run_id}/rechecks",
        json={
            "expected_review_package_version": pkg["review_package_version"],
            "changed_target_refs": [],
        },
        headers=mut(csrf),
    )


def approve(client, csrf, run_id, *, scope, scope_id):
    pkg = get_review(client, run_id)
    return client.post(
        f"/api/v1/runs/{run_id}/approvals",
        json={
            "scope": scope,
            "scope_id": scope_id,
            "expected_approval_scope_hash": pkg["current_approval_scope_hash"],
            "expected_review_package_version": pkg["review_package_version"],
            "confirm_not_submission_approval": True,
        },
        headers=mut(csrf),
    )
