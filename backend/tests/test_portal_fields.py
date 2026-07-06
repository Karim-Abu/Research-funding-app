"""Slice 4 (E4-A): read-only portal-field catalog — GET /runs/{id}/portal-fields.

Contract: exactly the registry set (161 fields), deterministic display_mode,
draft_available only for the M6 draft fields, SUM section included. The
existing /fields M6 contract stays untouched (covered by its own tests).
"""
from __future__ import annotations

import uuid

from app.registry import get_registry
from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    OUTSIDER_EMAIL,
    OUTSIDER_PASSWORD,
    VALID_CLASSIFICATION,
    create_project,
    login,
    unsafe_headers,
)

VALID_DISPLAY_MODES = {"draft", "checklist", "upload", "external_only"}

# Owner-confirmed derivation (Slice 4 step 0a).
EXPECTED_MODE_BY_SUPPORT = {
    "draft_text": "draft",
    "upload_validate": "upload",
    "structured_input": "checklist",
    "user_input_or_suggestion": "checklist",
    "structured_input_or_readonly": "checklist",
    "needs_verification": "checklist",
    "action_only": "external_only",
    "information_only": "external_only",
}


def _mut(csrf):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = uuid.uuid4().hex
    return headers


def _run_with_source(client, csrf):
    project_id = create_project(client, csrf)
    res = client.post(
        f"/api/v1/projects/{project_id}/sources/text",
        json={"name": "Src", "text": "Portal field catalog source.",
              "data_classification": VALID_CLASSIFICATION},
        headers=_mut(csrf),
    )
    assert res.status_code == 201, res.text
    res = client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={"settings": {"processing_mode": "deterministic_only",
                           "max_cost_chf": 0, "max_llm_calls": 0, "max_web_calls": 0}},
        headers=_mut(csrf),
    )
    assert res.status_code == 202, res.text
    return res.json()["resource_id"]


def _portal_fields(client, run_id):
    res = client.get(f"/api/v1/runs/{run_id}/portal-fields")
    assert res.status_code == 200, res.text
    return res.json()


def test_catalog_matches_registry_exactly(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    run_id = _run_with_source(client, csrf)
    items = _portal_fields(client, run_id)
    registry = get_registry()

    assert len(items) == len(registry.portal_fields)
    ids = [i["field_id"] for i in items]
    assert len(ids) == len(set(ids))  # each field_id exactly once
    assert set(ids) == set(registry.portal_fields)
    # Canonical registry order.
    expected_order = [
        f.field_id
        for f in sorted(registry.portal_fields.values(), key=lambda f: f.registry_index)
    ]
    assert ids == expected_order


def test_m6_fields_are_draft_and_available(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    run_id = _run_with_source(client, csrf)
    items = {i["field_id"]: i for i in _portal_fields(client, run_id)}
    m6_ids = {f.field_id for f in get_registry().m6_draft_fields()}

    assert m6_ids  # the supported draft set exists (8 fields today)
    for field_id in m6_ids:
        assert items[field_id]["display_mode"] == "draft"
        assert items[field_id]["draft_available"] is True
    # draft_available is EXACTLY the M6 set — the other draft_text fields
    # (display_mode=draft) are not active copy/draft fields.
    available = {fid for fid, i in items.items() if i["draft_available"]}
    assert available == m6_ids
    unsupported_draft = [
        i for i in items.values()
        if i["display_mode"] == "draft" and not i["draft_available"]
    ]
    assert unsupported_draft  # the 10 deferred draft_text fields stay visible


def test_sum_section_included(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    run_id = _run_with_source(client, csrf)
    items = _portal_fields(client, run_id)
    sum_items = [i for i in items if i["section"] == "SUM"]
    assert sum_items
    assert all(i["field_id"].startswith("SUM.") for i in sum_items)


def test_display_mode_derivation(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    run_id = _run_with_source(client, csrf)
    items = _portal_fields(client, run_id)
    for item in items:
        assert item["display_mode"] in VALID_DISPLAY_MODES
        assert item["display_mode"] == EXPECTED_MODE_BY_SUPPORT[item["support_mode"]]
        # required only where the registry is unambiguous.
        if item["mandatory_status"] == "required":
            assert item["required"] is True
        elif item["mandatory_status"] in {"optional", "not_applicable"}:
            assert item["required"] is False
        else:
            assert item["required"] is None


def test_requires_session(client):
    res = client.get(f"/api/v1/runs/{uuid.uuid4()}/portal-fields")
    assert res.status_code == 401


def test_run_ownership_is_workspace_scoped(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    run_id = _run_with_source(client, csrf)

    login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
    res = client.get(f"/api/v1/runs/{run_id}/portal-fields")
    assert res.status_code == 404
