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
from tests.research_brief_helpers import approve_research_brief

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
    approve_research_brief(
        client, csrf, pid, application_domain="ICT", technology_class="Industrial AI"
    )
    res = client.post(f"/api/v1/projects/{pid}/market-research/plan", json={},
                       headers=unsafe_headers(csrf))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["topic"]["application_domain"] == "ICT"
    assert body["topic"]["technology_area"] == "Industrial AI"
    assert 3 <= len(body["queries"]) <= 5
    # R8 Freigabepflicht: jede public_safe Query bringt eine pending Freigabe mit.
    assert all(q["approval_id"] for q in body["queries"] if q["public_safe"])
    assert body["provider_mode"] == "fake"


def test_plan_creates_no_research_tasks_only_pending_approvals(client, web_fake):
    # R8: der Plan-Endpoint legt pending Freigaben an (kein reiner Preview mehr),
    # aber weiterhin keine ResearchTasks und keinen Provider-Call.
    csrf = _login(client)
    pid = _create_project(client, csrf, _D0)
    approve_research_brief(client, csrf, pid)
    from app.db.models import ResearchTask, SearchQueryApproval
    from app.db.session import SessionLocal

    client.post(f"/api/v1/projects/{pid}/market-research/plan", json={},
                headers=unsafe_headers(csrf))
    db = SessionLocal()
    try:
        tasks = db.query(ResearchTask).filter(ResearchTask.project_id == pid).count()
        approvals = (
            db.query(SearchQueryApproval)
            .filter(SearchQueryApproval.project_id == pid)
            .all()
        )
    finally:
        db.close()
    assert tasks == 0
    assert approvals and all(a.status == "pending" for a in approvals)


def _plan_and_approve_all(client, csrf, pid) -> list[str]:
    approve_research_brief(client, csrf, pid)
    res = client.post(f"/api/v1/projects/{pid}/market-research/plan", json={},
                      headers=unsafe_headers(csrf))
    assert res.status_code == 200, res.text
    approval_ids = [q["approval_id"] for q in res.json()["queries"] if q["approval_id"]]
    for approval_id in approval_ids:
        ok = client.post(f"/api/v1/search-query-approvals/{approval_id}/approve",
                         headers=unsafe_headers(csrf))
        assert ok.status_code == 200, ok.text
    return approval_ids


def test_plan_uses_only_the_approved_brief(client, web_fake):
    csrf = _login(client)
    pid = _create_project(client, csrf, _D0)
    approve_research_brief(
        client, csrf, pid, application_domain="Photonik", technology_class="Sensorik"
    )
    res = client.post(
        f"/api/v1/projects/{pid}/market-research/plan",
        json={"application_domain": "Andere Domäne", "technology_area": "Andere Technik"},
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
    approve_research_brief(client, csrf, pid)
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
    # R8 Freigabepflicht: der Lauf braucht freigegebene Queries (plan → approve → run).
    csrf = _login(client)
    pid = _create_project(client, csrf, _D0)
    approval_ids = _plan_and_approve_all(client, csrf, pid)
    res = client.post(f"/api/v1/projects/{pid}/market-research/run",
                       json=_topic_payload(approval_ids=approval_ids),
                       headers=_headers(csrf))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["result_count"] == 9  # 3 Briefmodule × 3 Demo-Treffer
    assert len(body["candidates"]) == 9
    assert all(c["human_review_required"] is True for c in body["candidates"])
    assert all(c["confidence"] in ("low", "medium") for c in body["candidates"])
    assert body["provider"] == "fake"


def test_run_d2_without_approval_blocked(client, web_fake):
    csrf = _login(client)
    pid = _create_project(client, csrf, _D2)
    approve_research_brief(client, csrf, pid)
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
    approval_ids = _plan_and_approve_all(client, csrf, pid)
    headers = _headers(csrf)
    payload = _topic_payload(approval_ids=approval_ids)
    first = client.post(f"/api/v1/projects/{pid}/market-research/run",
                         json=payload, headers=headers)
    assert first.status_code == 200, first.text
    second = client.post(f"/api/v1/projects/{pid}/market-research/run",
                          json=payload, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json() == first.json()
