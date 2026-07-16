"""Structured transfer is exclusively based on the immutable RunProjectSnapshot."""
from __future__ import annotations

import io

import docx

from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, VALID_CLASSIFICATION, create_project, login
from tests.export_helpers import download, make_export
from tests.review_helpers import SOURCE_TEXT, mut


def _text(data: bytes) -> str:
    document = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs) + "\n" + "\n".join(
        cell.text for table in document.tables for row in table.rows for cell in row.cells
    )


def test_transfer_snapshot_and_working_doc_keep_frozen_partner_budget_and_duration(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = create_project(client, csrf, "Frozen Export Project")
    before_run = {
        "direct_total_project_costs_excluding_overhead": 100000,
        "implementation_own_contribution": 45000,
        "cash_contribution": 5000,
        "total_requested_funding": 50000,
        "total_requested_funding_including_overhead": 55000,
        "duration_months": 24,
    }
    assert client.patch(f"/api/v1/projects/{project_id}", json=before_run, headers=mut(csrf)).status_code == 200
    assert client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={"name": "Quelle", "text": SOURCE_TEXT, "data_classification": VALID_CLASSIFICATION},
        headers=mut(csrf),
    ).status_code == 201
    partner = client.post(
        f"/api/v1/projects/{project_id}/partners",
        json={"name": "Frozen Partner AG", "partner_type": "implementation_partner", "country": "CH", "swiss_value_creation": True},
        headers=mut(csrf),
    ).json()
    run = client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"settings": {"processing_mode": "deterministic_only", "max_cost_chf": 0, "max_llm_calls": 0, "max_web_calls": 0}},
        headers=mut(csrf),
    ).json()
    run_id = run["resource_id"]
    assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "completed"

    # Later project/partner edits must become stale, never leak into this run.
    changed = {**before_run, "direct_total_project_costs_excluding_overhead": 999999, "duration_months": 36}
    assert client.patch(f"/api/v1/projects/{project_id}", json=changed, headers=mut(csrf)).status_code == 200
    assert client.patch(
        f"/api/v1/partners/{partner['partner_id']}",
        json={"name": "Changed Partner AG", "partner_type": "implementation_partner", "country": "CH", "swiss_value_creation": True},
        headers=mut(csrf),
    ).status_code == 200

    transfer = client.get(f"/api/v1/runs/{run_id}/transfer-snapshot")
    assert transfer.status_code == 200, transfer.text
    body = transfer.json()
    assert body["stale"] is True
    assert body["project"]["duration_months"] == 24
    assert body["partners"][0]["name"] == "Frozen Partner AG"
    direct = next(v for v in body["budget"]["values"] if v["key"] == "direct_total_project_costs_excluding_overhead")
    assert direct["value"] == 100000

    artifact = make_export(client, csrf, run_id, "docx")
    text = _text(download(client, artifact["export_id"]).content)
    assert "Frozen Partner AG" in text and "Changed Partner AG" not in text
    assert "24 Monate" in text and "36 Monate" not in text
    assert "CHF 100’000.00" in text and "999’999" not in text
    assert "eingefrorenen Run-Snapshot" in text
