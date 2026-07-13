"""Gemeinsame Helfer für die Graph-Anbindungstests (A2/A3 im normalen Lauf):
öffentliches Cloud-Projekt + Quelle + bestätigter Cloud-Run über die echte API.
"""
from __future__ import annotations

import uuid

from tests.conftest import project_payload, unsafe_headers

POLICY = "1.1.0"
PUBLIC_CLOUD = {
    "sensitivity": "public", "origin": "synthetic",
    "processing_mode": "cloud_assisted", "web_research_mode": "off",
    "nda_applies": False,
}


def mut_headers(csrf):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = uuid.uuid4().hex
    return headers


def cloud_project_with_source(client, csrf, title="Cloud Graph Project"):
    payload = project_payload(title)
    payload["data_classification"] = PUBLIC_CLOUD
    res = client.post("/api/v1/projects", json=payload, headers=mut_headers(csrf))
    assert res.status_code == 201, res.text
    project_id = res.json()["project_id"]
    res = client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={
            "name": "Src",
            "text": "The consortium includes a Swiss implementation partner.",
            "data_classification": PUBLIC_CLOUD,
        },
        headers=mut_headers(csrf),
    )
    assert res.status_code == 201, res.text
    return project_id, res.json()["current_source_version_id"]


def cloud_run(client, csrf, project_id, svid, *, max_llm_calls=25):
    res = client.post(
        f"/api/v1/projects/{project_id}/processing-confirmations",
        json={
            "processing_mode": "cloud_assisted", "source_version_ids": [svid],
            "accepted_policy_version": POLICY,
            "purpose": "Textentwürfe vorbereiten", "expires_after_one_run": True,
        },
        headers=mut_headers(csrf),
    )
    assert res.status_code == 201, res.text
    confirmation_id = res.json()["confirmation_id"]
    res = client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={
            "settings": {
                "processing_mode": "cloud_assisted", "max_cost_chf": 5,
                "max_llm_calls": max_llm_calls, "max_web_calls": 0,
                "source_version_ids": [svid],
                "internal_cloud_confirmation_id": confirmation_id,
            }
        },
        headers=mut_headers(csrf),
    )
    assert res.status_code == 202, res.text
    run_id = res.json()["resource_id"]
    run = client.get(f"/api/v1/runs/{run_id}").json()
    assert run["status"] == "completed", run
    return run_id
