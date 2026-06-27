"""Project CRUD, idempotency, workspace isolation, both-roles-accepted."""
from __future__ import annotations

import uuid

from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    ORIGIN,
    OUTSIDER_EMAIL,
    OUTSIDER_PASSWORD,
    TOBIAS_EMAIL,
    TOBIAS_PASSWORD,
    login,
    project_payload,
    unsafe_headers,
)


def _create(client, csrf, payload=None, key=None):
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = key or uuid.uuid4().hex
    return client.post(
        "/api/v1/projects", json=payload or project_payload(), headers=headers
    )


def test_create_list_get_update(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)

    created = _create(client, csrf, project_payload("Alpha"))
    assert created.status_code == 201, created.text
    project = created.json()
    pid = project["project_id"]
    assert project["status"] == "draft"
    assert project["workspace_id"] == "ws-demo"
    assert project["data_classification"]["sensitivity"] == "public"

    listing = client.get("/api/v1/projects")
    assert listing.status_code == 200
    assert any(p["project_id"] == pid for p in listing.json()["items"])

    got = client.get(f"/api/v1/projects/{pid}")
    assert got.status_code == 200
    assert got.json()["title"] == "Alpha"

    patched = client.patch(
        f"/api/v1/projects/{pid}",
        json={"title": "Alpha v2"},
        headers=unsafe_headers(csrf),
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Alpha v2"


def test_create_requires_csrf(client):
    login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = client.post(
        "/api/v1/projects",
        json=project_payload(),
        headers={"Origin": ORIGIN, "Idempotency-Key": uuid.uuid4().hex},
    )
    assert res.status_code == 403
    assert res.json()["code"] == "csrf_failed"


def test_idempotent_replay_returns_original(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    key = uuid.uuid4().hex
    first = _create(client, csrf, project_payload("Idem"), key=key)
    second = _create(client, csrf, project_payload("Idem"), key=key)
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["project_id"] == second.json()["project_id"]


def test_idempotency_conflict_on_different_body(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    key = uuid.uuid4().hex
    _create(client, csrf, project_payload("First"), key=key)
    conflict = _create(client, csrf, project_payload("Different"), key=key)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"


def test_workspace_isolation(client):
    # Anna (ws-demo) creates a project.
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _create(client, csrf).json()["project_id"]

    # Outsider (ws-test) must not see or fetch it.
    outsider = login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
    assert outsider  # csrf token returned
    listing = client.get("/api/v1/projects")
    assert all(p["project_id"] != pid for p in listing.json()["items"])
    assert client.get(f"/api/v1/projects/{pid}").status_code == 404


def test_member_role_accepted(client):
    # No M1 endpoint restricts roles (both lead_admin and member allowed).
    csrf = login(client, TOBIAS_EMAIL, TOBIAS_PASSWORD)
    res = _create(client, csrf, project_payload("Member Project"))
    assert res.status_code == 201


def test_get_missing_project_problem_shape(client):
    login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = client.get("/api/v1/projects/does-not-exist")
    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/problem+json")
    body = res.json()
    assert body["code"] == "not_found"
    assert body["correlation_id"]
    assert body["instance"] == "/api/v1/projects/does-not-exist"
