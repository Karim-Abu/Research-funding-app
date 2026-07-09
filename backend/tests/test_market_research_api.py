"""RESEARCH.1b — Market Research API (plan/run), fake provider only, no network.

Covers: /market-research/plan (pure preview, topic suggestion + override, provider_mode),
/market-research/run (D0 success incl. MarketCandidate shape + human_review_required,
D2-without-approval / D3 / UNKNOWN firewall refusal mapped to the right HTTP problem,
Idempotency-Key reuse).
"""
from __future__ import annotations

import uuid

import pytest

from app.config.settings import get_settings
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, login, unsafe_headers

_D0 = {
    "sensitivity": "public", "origin": "synthetic", "processing_mode": "cloud_assisted",
    "web_research_mode": "validated_public", "nda_applies": False,
}
_D2 = {
    "sensitivity": "confidential", "origin": "real_project", "processing_mode": "cloud_assisted",
    "web_research_mode": "validated_public", "nda_applies": False,
}
_D3 = {**_D0, "nda_applies": True}
# public sensitivity + a non-public origin is ambiguous → derive_data_class() = UNKNOWN.
_UNKNOWN = {**_D0, "origin": "real_project"}


@pytest.fixture
def web_fake(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "web_research_enabled", True)
    monkeypatch.setattr(s, "web_research_fake_provider", True)
    monkeypatch.setattr(s, "firecrawl_api_key", None)
    return s


def _headers(csrf: str) -> dict[str, str]:
    h = unsafe_headers(csrf)
    h["Idempotency-Key"] = uuid.uuid4().hex
    return h


def _create_project(client, csrf, classification, *, innovation_field="ICT / Industrial AI") -> str:
    res = client.post("/api/v1/projects", json={
        "title": "Market Research API Project",
        "description": "Test project for RESEARCH.1b.",
        "innovation_field": innovation_field,
        "funding_instrument_profile_id":
            "innosuisse_innovation_project_with_implementation_partner",
        "data_classification": classification,
    }, headers=_headers(csrf))
    assert res.status_code == 201, res.text
    return res.json()["project_id"]


def _login(client) -> str:
    return login(client, ANNA_EMAIL, ANNA_PASSWORD)


# --- /plan -------------------------------------------------------------------


def test_plan_suggests_topic_from_innovation_field_and_returns_queries(client, web_fake):
    csrf = _login(client)
    pid = _create_project(client, csrf, _D0, innovation_field="ICT / Industrial AI")
    res = client.post(f"/api/v1/projects/{pid}/market-research/plan", json={},
                       headers=unsafe_headers(csrf))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["topic"]["application_domain"] == "ICT"
    assert body["topic"]["technology_area"] == "Industrial AI"
    assert 3 <= len(body["queries"]) <= 5
    assert body["provider_mode"] == "fake"


def test_plan_no_db_writes(client, web_fake):
    csrf = _login(client)
    pid = _create_project(client, csrf, _D0)
    from app.db.models import ResearchTask
    from app.db.session import SessionLocal

    client.post(f"/api/v1/projects/{pid}/market-research/plan", json={},
                headers=unsafe_headers(csrf))
    db = SessionLocal()
    try:
        count = db.query(ResearchTask).filter(ResearchTask.project_id == pid).count()
    finally:
        db.close()
    assert count == 0


def test_plan_applies_topic_override(client, web_fake):
    csrf = _login(client)
    pid = _create_project(client, csrf, _D0)
    res = client.post(
        f"/api/v1/projects/{pid}/market-research/plan",
        json={"application_domain": "Photonik", "technology_area": "Sensorik"},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["topic"]["application_domain"] == "Photonik"
    assert body["topic"]["technology_area"] == "Sensorik"
    assert any("Photonik" in q["query_text"] for q in body["queries"])


def test_plan_unavailable_when_web_research_disabled(client):
    csrf = _login(client)
    pid = _create_project(client, csrf, _D0)
    res = client.post(f"/api/v1/projects/{pid}/market-research/plan", json={},
                       headers=unsafe_headers(csrf))
    assert res.status_code == 200, res.text
    assert res.json()["provider_mode"] == "unavailable"


# --- /run ----------------------------------------------------------------


def _topic_payload(**over) -> dict:
    base = {
        "application_domain": "manufacturing quality assurance",
        "technology_area": "industrial AI anomaly detection",
        "target_customers": "manufacturing SMEs",
        "region": "Switzerland",
    }
    base.update(over)
    return base


def test_run_d0_persists_and_returns_candidates(client, web_fake):
    csrf = _login(client)
    pid = _create_project(client, csrf, _D0)
    res = client.post(f"/api/v1/projects/{pid}/market-research/run",
                       json=_topic_payload(), headers=_headers(csrf))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["result_count"] == 15  # 5 queries × 3 fake results
    assert len(body["candidates"]) == 15
    assert all(c["human_review_required"] is True for c in body["candidates"])
    assert all(c["confidence"] in ("low", "medium") for c in body["candidates"])
    assert body["provider"] == "fake"


def test_run_d2_without_approval_blocked(client, web_fake):
    csrf = _login(client)
    pid = _create_project(client, csrf, _D2)
    res = client.post(f"/api/v1/projects/{pid}/market-research/run",
                       json=_topic_payload(), headers=_headers(csrf))
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "approval_required"


@pytest.mark.parametrize("classification", [_D3, _UNKNOWN])
def test_run_d3_and_unknown_blocked(client, web_fake, classification):
    csrf = _login(client)
    pid = _create_project(client, csrf, classification)
    res = client.post(f"/api/v1/projects/{pid}/market-research/run",
                       json=_topic_payload(), headers=_headers(csrf))
    assert res.status_code == 403, res.text
    assert res.json()["code"] == "web_research_class_blocked"


def test_run_unavailable_when_web_research_disabled(client):
    csrf = _login(client)
    pid = _create_project(client, csrf, _D0)
    res = client.post(f"/api/v1/projects/{pid}/market-research/run",
                       json=_topic_payload(), headers=_headers(csrf))
    assert res.status_code == 503, res.text
    assert res.json()["code"] == "web_research_unavailable"


def test_run_idempotency_key_reuse_returns_same_response(client, web_fake):
    csrf = _login(client)
    pid = _create_project(client, csrf, _D0)
    headers = _headers(csrf)
    first = client.post(f"/api/v1/projects/{pid}/market-research/run",
                         json=_topic_payload(), headers=headers)
    assert first.status_code == 200, first.text
    second = client.post(f"/api/v1/projects/{pid}/market-research/run",
                          json=_topic_payload(), headers=headers)
    assert second.status_code == 200, second.text
    assert second.json() == first.json()
