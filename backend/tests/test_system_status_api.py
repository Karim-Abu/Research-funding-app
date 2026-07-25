"""The simplified system status is member-readable and test execution is gated."""
from __future__ import annotations

from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    TOBIAS_EMAIL,
    TOBIAS_PASSWORD,
    login,
    unsafe_headers,
)


def test_member_can_read_compact_status_without_provider_table(client):
    login(client, TOBIAS_EMAIL, TOBIAS_PASSWORD)
    response = client.get("/api/v1/system-status")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["can_run_connection_check"] is False
    assert {service["id"] for service in body["services"]} == {"ai", "web"}
    assert all("provider" not in service and "model" not in service for service in body["services"])
    assert all(service["next_step"] for service in body["services"])


def test_only_lead_admin_can_run_connection_check(client):
    member_csrf = login(client, TOBIAS_EMAIL, TOBIAS_PASSWORD)
    denied = client.post(
        "/api/v1/system-status/connection-check",
        headers=unsafe_headers(member_csrf),
    )
    assert denied.status_code == 403

    admin_csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    accepted = client.post(
        "/api/v1/system-status/connection-check",
        headers=unsafe_headers(admin_csrf),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["can_run_connection_check"] is True


def test_retired_evaluation_endpoints_are_not_product_routes(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    assert client.get("/api/v1/admin/live-system-status").status_code == 404
    assert client.post(
        "/api/v1/demo/integrated-draft", headers=unsafe_headers(csrf)
    ).status_code == 404
