"""Lead-admin live status: role/CSRF guards and redacted metadata contract."""
from __future__ import annotations

from tests.conftest import (
    ANNA_EMAIL, ANNA_PASSWORD, TOBIAS_EMAIL, TOBIAS_PASSWORD,
    login, unsafe_headers,
)


def test_live_status_requires_lead_admin(client):
    login(client, TOBIAS_EMAIL, TOBIAS_PASSWORD)
    response = client.get("/api/v1/admin/live-system-status")
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden_role"


def test_live_status_is_metadata_only(client):
    login(client, ANNA_EMAIL, ANNA_PASSWORD)
    response = client.get("/api/v1/admin/live-system-status")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["registry_version"]
    assert body["routes"]
    encoded = response.text.lower()
    assert "preflight connectivity check" not in encoded
    assert "api_key" not in encoded
    assert all("requested_model_id" in route for route in body["routes"])


def test_preflight_requires_csrf_and_never_calls_without_keys(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    rejected = client.post("/api/v1/admin/live-system-status/preflight")
    assert rejected.status_code == 403
    response = client.post(
        "/api/v1/admin/live-system-status/preflight",
        headers=unsafe_headers(csrf),
    )
    assert response.status_code == 200, response.text
    routes = response.json()["status"]["routes"]
    assert all(route["preflight_status"] != "pass" for route in routes)
    assert "preflight connectivity check" not in response.text.lower()
