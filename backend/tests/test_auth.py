"""Auth, session, CSRF/Origin, capabilities, health + Problem-shape tests."""
from __future__ import annotations

from tests.conftest import (
    ANNA_EMAIL,
    ANNA_PASSWORD,
    ORIGIN,
    login,
    unsafe_headers,
)

PROBLEM_KEYS = {"type", "title", "status", "detail", "code", "correlation_id"}


def test_health_ok(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["api_version"] == "1.1.0"
    assert body["policy_version"] and body["agent_registry_version"]


def test_login_success_sets_cookie(client):
    res = client.post(
        "/api/v1/session", json={"email": ANNA_EMAIL, "password": ANNA_PASSWORD}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["email"] == ANNA_EMAIL
    assert body["user"]["effective_role"] == "lead_admin"
    assert body["csrf_token"]
    assert "rf_session" in res.cookies


def test_login_invalid_credentials_problem(client):
    res = client.post(
        "/api/v1/session", json={"email": ANNA_EMAIL, "password": "wrong"}
    )
    assert res.status_code == 401
    assert res.headers["content-type"].startswith("application/problem+json")
    body = res.json()
    assert PROBLEM_KEYS.issubset(body)
    assert body["code"] == "invalid_credentials"


def test_session_bootstrap(client):
    login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = client.get("/api/v1/session")
    assert res.status_code == 200
    assert res.json()["user"]["email"] == ANNA_EMAIL


def test_me_requires_auth(client):
    res = client.get("/api/v1/me")
    assert res.status_code == 401
    assert res.json()["code"] == "unauthenticated"


def test_me_authenticated(client):
    login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = client.get("/api/v1/me")
    assert res.status_code == 200
    assert res.json()["user_id"] == "user-anna"


def test_logout_revokes_session(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = client.delete("/api/v1/session", headers=unsafe_headers(csrf))
    assert res.status_code == 204
    # Session is now revoked.
    assert client.get("/api/v1/session").status_code == 401


def test_logout_csrf_rejected(client):
    login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = client.delete("/api/v1/session", headers={"Origin": ORIGIN})
    assert res.status_code == 403
    assert res.json()["code"] == "csrf_failed"


def test_logout_origin_rejected(client):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = client.delete(
        "/api/v1/session",
        headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"},
    )
    assert res.status_code == 403
    assert res.json()["code"] == "origin_forbidden"


def test_capabilities(client):
    login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = client.get("/api/v1/capabilities")
    assert res.status_code == 200
    body = res.json()
    assert body["api_version"] == "1.1.0"
    assert 1 <= body["polling_interval_seconds"] <= 10
    assert body["features"]["projects"] is True
