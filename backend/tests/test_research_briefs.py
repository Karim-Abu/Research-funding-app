"""Public-safe research brief, approval provenance and D1/D2 executor policy."""
from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from app.config.settings import get_settings
from app.db.models import AuditEvent, Project, ResearchBrief, ResearchTask, SearchQueryApproval
from app.db.session import SessionLocal
from app.research import brief_service
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, login, unsafe_headers
from tests.research_brief_helpers import approve_research_brief


D0 = {
    "sensitivity": "public", "origin": "synthetic",
    "processing_mode": "cloud_assisted", "web_research_mode": "validated_public",
    "nda_applies": False,
}
D2 = {
    "sensitivity": "confidential", "origin": "real_project",
    "processing_mode": "cloud_assisted", "web_research_mode": "validated_public",
    "nda_applies": False,
}
D3 = {**D2, "nda_applies": True}


def _headers(csrf: str) -> dict[str, str]:
    headers = unsafe_headers(csrf)
    headers["Idempotency-Key"] = uuid.uuid4().hex
    return headers


def _project(client, csrf: str, classification=D0, *, title="Public Brief Test") -> str:
    response = client.post(
        "/api/v1/projects",
        json={
            "title": title,
            "description": "A synthetic test project.",
            "innovation_field": "Industrial quality / anomaly detection",
            "funding_instrument_profile_id":
                "innosuisse_innovation_project_with_implementation_partner",
            "data_classification": classification,
        },
        headers=_headers(csrf),
    )
    assert response.status_code == 201, response.text
    return response.json()["project_id"]


def _plan(client, csrf: str, brief_id: str) -> list[dict]:
    response = client.post(
        f"/api/v1/research-briefs/{brief_id}/queries/plan",
        headers=unsafe_headers(csrf),
    )
    assert response.status_code == 200, response.text
    return response.json()["queries"]


def _approve_query(client, csrf: str, approval_id: str) -> None:
    response = client.post(
        f"/api/v1/search-query-approvals/{approval_id}/approve",
        headers=unsafe_headers(csrf),
    )
    assert response.status_code == 200, response.text


@pytest.fixture
def web_fake(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "web_research_enabled", True)
    monkeypatch.setattr(settings, "web_research_fake_provider", True)
    monkeypatch.setattr(settings, "firecrawl_api_key", None)
    monkeypatch.setattr(settings, "d2_web_research_enabled", False)
    return settings


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_all_four_active_modules_plan_bound_queries_and_reload_state(client, db, web_fake):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _project(client, csrf)
    brief = approve_research_brief(
        client, csrf, project_id,
        modules=[
            "market_growth", "competition_alternatives", "state_of_the_art",
            "swiss_research_partners",
        ],
        competence_needs=["applied machine learning", "industrial sensing"],
    )
    queries = _plan(client, csrf, brief["research_brief_id"])

    assert {q["module"] for q in queries} == set(brief["modules"])
    assert all(q["status"] == "pending" for q in queries)
    assert all(q["research_brief_id"] == brief["research_brief_id"] for q in queries)
    persisted = list(db.scalars(select(SearchQueryApproval).where(
        SearchQueryApproval.research_brief_id == brief["research_brief_id"]
    )))
    assert len(persisted) == len(queries)
    assert all(row.raw_query_hash and row.sanitized_query for row in persisted)

    workspace = client.get(
        f"/api/v1/projects/{project_id}/research-workspace"
    )
    assert workspace.status_code == 200, workspace.text
    assert workspace.json()["brief"]["active_approved"]["version"] == 1
    assert len(workspace.json()["queries"]) == len(queries)
    assert workspace.json()["provider_mode"] == "fake_demo"


def test_new_brief_version_expires_unconsumed_query_approvals(client, db, web_fake):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _project(client, csrf)
    first = approve_research_brief(client, csrf, project_id)
    queries = _plan(client, csrf, first["research_brief_id"])
    _approve_query(client, csrf, queries[0]["approval_id"])

    saved = client.put(
        f"/api/v1/projects/{project_id}/research-brief",
        json={
            "application_domain": "manufacturing quality assurance",
            "technology_class": "industrial AI anomaly detection",
            "target_customer_segments": ["manufacturing SMEs"],
            "region": "Europe",
            "competence_needs": ["applied machine learning"],
            "modules": ["market_growth", "competition_alternatives"],
        },
        headers=unsafe_headers(csrf),
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 2 and saved.json()["status"] == "draft"
    approved = client.post(
        f"/api/v1/research-briefs/{saved.json()['research_brief_id']}/approve",
        headers=unsafe_headers(csrf),
    )
    assert approved.status_code == 200, approved.text

    db.expire_all()
    assert db.get(ResearchBrief, first["research_brief_id"]).status == "superseded"
    assert {
        db.get(SearchQueryApproval, query["approval_id"]).status for query in queries
    } == {"expired"}
    workspace = client.get(f"/api/v1/projects/{project_id}/research-workspace")
    assert workspace.status_code == 200, workspace.text
    assert {row["approval_id"] for row in workspace.json()["queries"]}.issuperset(
        {query["approval_id"] for query in queries}
    )


def test_partner_result_is_advisory_and_location_is_not_inferred(client, web_fake):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _project(client, csrf)
    brief = approve_research_brief(
        client,
        csrf,
        project_id,
        modules=["swiss_research_partners"],
        competence_needs=["applied machine learning"],
    )
    query = _plan(client, csrf, brief["research_brief_id"])[0]
    _approve_query(client, csrf, query["approval_id"])
    run = client.post(
        f"/api/v1/research-briefs/{brief['research_brief_id']}/run",
        json={"approval_ids": [query["approval_id"]]},
        headers=unsafe_headers(csrf),
    )
    assert run.status_code == 200, run.text

    workspace = client.get(f"/api/v1/projects/{project_id}/research-workspace")
    assert workspace.status_code == 200, workspace.text
    candidates = [
        result["partner_candidate"] for result in workspace.json()["results"]
        if result["partner_candidate"] is not None
    ]
    assert candidates
    assert all(candidate["location"] is None for candidate in candidates)
    assert all(candidate["location_status"] == "unverified" for candidate in candidates)
    assert all(
        candidate["status"] == "needs_human_check"
        for candidate in candidates
    )


def test_query_edit_cannot_change_module_purpose(client, web_fake):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _project(client, csrf)
    brief = approve_research_brief(client, csrf, project_id, modules=["market_growth"])
    query = _plan(client, csrf, brief["research_brief_id"])[0]
    response = client.post(
        f"/api/v1/research-briefs/{brief['research_brief_id']}/queries/preview",
        json={
            "module": "market_growth",
            "planner_purpose": "state_of_the_art",
            "query_text": query["query_text"],
            "supersedes_approval_id": query["approval_id"],
        },
        headers=unsafe_headers(csrf),
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "planner_purpose_module_mismatch"


def test_run_prevalidates_complete_approval_batch(client, web_fake, monkeypatch):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _project(client, csrf)
    brief = approve_research_brief(
        client, csrf, project_id,
        modules=["market_growth", "competition_alternatives"],
    )
    queries = _plan(client, csrf, brief["research_brief_id"])
    _approve_query(client, csrf, queries[0]["approval_id"])
    calls: list[str] = []
    monkeypatch.setattr(
        brief_service, "research_executor",
        lambda task_id, operation_id: calls.append(task_id),
    )
    response = client.post(
        f"/api/v1/research-briefs/{brief['research_brief_id']}/run",
        json={"approval_ids": [queries[0]["approval_id"], queries[1]["approval_id"]]},
        headers=unsafe_headers(csrf),
    )
    assert response.status_code == 422, response.text
    assert calls == []


def test_run_blocks_if_project_becomes_d3_after_approval(
    client, db, web_fake, monkeypatch
):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _project(client, csrf)
    brief = approve_research_brief(client, csrf, project_id, modules=["market_growth"])
    query = _plan(client, csrf, brief["research_brief_id"])[0]
    _approve_query(client, csrf, query["approval_id"])
    project = db.get(Project, project_id)
    project.data_classification = dict(D3)
    db.commit()
    calls: list[str] = []
    monkeypatch.setattr(
        brief_service, "research_executor",
        lambda task_id, operation_id: calls.append(task_id),
    )
    response = client.post(
        f"/api/v1/research-briefs/{brief['research_brief_id']}/run",
        json={"approval_ids": [query["approval_id"]]},
        headers=unsafe_headers(csrf),
    )
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "web_research_class_blocked"
    assert calls == []


def test_legacy_task_endpoint_cannot_bypass_brief_and_uses_server_query(
    client, db, web_fake
):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _project(client, csrf)
    payload = {
        "purpose": "partner_role_suggestion",
        "subject_type": "topic",
        "query_preview": "CLIENT-CANARY-NOT-A-QUERY",
        "max_results": 3,
        "user_confirms_public_professional_purpose": True,
    }
    blocked = client.post(
        f"/api/v1/projects/{project_id}/research-tasks",
        json=payload,
        headers=_headers(csrf),
    )
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["code"] == "research_brief_approval_required"

    brief = approve_research_brief(client, csrf, project_id, modules=["market_growth"])
    query = _plan(client, csrf, brief["research_brief_id"])[0]
    _approve_query(client, csrf, query["approval_id"])
    accepted = client.post(
        f"/api/v1/projects/{project_id}/research-tasks",
        json={**payload, "approval_id": query["approval_id"]},
        headers=_headers(csrf),
    )
    assert accepted.status_code == 202, accepted.text
    task = db.get(ResearchTask, accepted.json()["resource_id"])
    assert task.query_text == query["query_text"]
    assert "CLIENT-CANARY" not in task.query_text
    assert task.research_brief_id == brief["research_brief_id"]


def test_leakage_canaries_are_not_persisted_or_audited(client, db, web_fake, caplog):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    canary = "C0DENAME-ZETA-PRIVATE"
    project_id = _project(client, csrf, title=canary)
    partner = client.post(
        f"/api/v1/projects/{project_id}/partners",
        json={"name": "Secret Partner AG", "partner_type": "implementation_partner"},
        headers=_headers(csrf),
    )
    assert partner.status_code == 201, partner.text

    response = client.put(
        f"/api/v1/projects/{project_id}/research-brief",
        json={
            "application_domain":
                f"{canary} Secret Partner AG 147054 owner@example.test proprietary sentence",
            "technology_class": "industrial sensing",
            "target_customer_segments": ["manufacturing SMEs"],
            "region": "Switzerland",
            "competence_needs": [],
            "modules": ["market_growth"],
        },
        headers=unsafe_headers(csrf),
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "research_brief_not_public_safe"
    assert db.scalar(select(ResearchBrief).where(
        ResearchBrief.project_id == project_id
    )) is None
    audit_blob = json.dumps(
        [event.detail for event in db.scalars(select(AuditEvent))], default=str
    )
    log_blob = " ".join(record.getMessage() for record in caplog.records)
    for marker in (canary, "Secret Partner", "147054", "owner@example.test", "proprietary sentence"):
        assert marker not in audit_blob
        assert marker not in log_blob


def test_d2_fake_demo_runs_only_after_brief_and_query_approval(client, db, web_fake):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _project(client, csrf, D2)
    brief = approve_research_brief(client, csrf, project_id, modules=["market_growth"])
    queries = _plan(client, csrf, brief["research_brief_id"])
    _approve_query(client, csrf, queries[0]["approval_id"])

    response = client.post(
        f"/api/v1/research-briefs/{brief['research_brief_id']}/run",
        json={"approval_ids": [queries[0]["approval_id"]]},
        headers=unsafe_headers(csrf),
    )
    assert response.status_code == 200, response.text
    assert response.json()["execution_mode"] == "fake_demo"
    task = db.get(ResearchTask, response.json()["task_ids"][0])
    assert task.execution_mode == "fake_demo"
    assert task.firewall_approval_id == queries[0]["approval_id"]


def test_d2_live_requires_feature_flag_before_executor_call(
    client, db, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "web_research_enabled", True)
    monkeypatch.setattr(settings, "web_research_fake_provider", False)
    monkeypatch.setattr(settings, "firecrawl_api_key", "unit-test-key")
    monkeypatch.setattr(settings, "d2_web_research_enabled", False)
    calls: list[str] = []
    monkeypatch.setattr(
        brief_service, "research_executor",
        lambda task_id, operation_id: calls.append(task_id),
    )
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _project(client, csrf, D2)
    brief = approve_research_brief(client, csrf, project_id, modules=["market_growth"])
    query = _plan(client, csrf, brief["research_brief_id"])[0]
    _approve_query(client, csrf, query["approval_id"])

    blocked = client.post(
        f"/api/v1/research-briefs/{brief['research_brief_id']}/run",
        json={"approval_ids": [query["approval_id"]]},
        headers=unsafe_headers(csrf),
    )
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["code"] == "d2_live_web_research_disabled"
    assert calls == []

    monkeypatch.setattr(settings, "d2_web_research_enabled", True)
    allowed = client.post(
        f"/api/v1/research-briefs/{brief['research_brief_id']}/run",
        json={"approval_ids": [query["approval_id"]]},
        headers=unsafe_headers(csrf),
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["execution_mode"] == "live"
    assert len(calls) == 1


def test_d3_brief_is_blocked_before_query_or_provider(client, db, web_fake):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _project(client, csrf, D3)
    response = client.put(
        f"/api/v1/projects/{project_id}/research-brief",
        json={
            "application_domain": "manufacturing quality assurance",
            "technology_class": "industrial sensing",
            "target_customer_segments": ["manufacturing SMEs"],
            "region": "Switzerland", "competence_needs": [],
            "modules": ["market_growth"],
        },
        headers=unsafe_headers(csrf),
    )
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "web_research_class_blocked"
    assert db.scalar(select(ResearchTask).where(
        ResearchTask.project_id == project_id
    )) is None
