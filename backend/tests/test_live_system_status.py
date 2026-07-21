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
    assert body["generation_mode"] in {
        "unavailable", "fake_demo", "real_eval", "live_unavailable",
    }
    assert body["firecrawl"]["mode"] in {
        "disabled", "fake", "live", "not_configured",
    }
    encoded = response.text.lower()
    assert "preflight connectivity check" not in encoded
    assert "api_key" not in encoded
    assert all("requested_model_id" in route for route in body["routes"])
    assert all(
        route["readiness_status"] in {
            "disabled", "fake", "not_configured", "configured_unverified",
            "ready", "degraded", "error",
        }
        for route in body["routes"]
    )
    assert "reason_code" in body["firecrawl"]
    assert "retryable" in body["firecrawl"]


def test_run_3a_openapi_contract_is_additive(client):
    schema = client.app.openapi()
    capabilities = schema["components"]["schemas"]["Capabilities"]
    assert "feature_readiness" in capabilities["properties"]
    feature = schema["components"]["schemas"]["FeatureReadiness"]
    assert set(feature["properties"]["status"]["enum"]) == {
        "disabled", "fake", "not_configured", "configured_unverified",
        "ready", "degraded", "error",
    }
    brief = schema["components"]["schemas"]["ResearchBriefInput"]
    assert {"research_goal", "search_tags"} <= set(brief["properties"])


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
    assert response.json()["status"]["generation_mode"] != "real_eval"
    assert response.json()["status"]["firecrawl"]["preflight_status"] != "pass"
    assert "preflight connectivity check" not in response.text.lower()
