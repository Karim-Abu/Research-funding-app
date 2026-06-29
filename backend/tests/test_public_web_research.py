"""Milestone 9I-A — public web research foundation (fake provider only, no network).

Covers: web-research data policy, URL/SSRF safety, the fake/real provider boundary, the
ResearchTask lifecycle, importing a result as a normal SourceDocument (+ fragments, no
direct EvidenceAnchor), and the advisory, NON-BLOCKING A1 synthesis.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.config.settings import get_settings
from app.db.models import (
    EvidenceAnchor,
    ResearchResult,
    ResearchTask,
    SourceDocument,
    SourceFragment,
    SourceVersion,
)
from app.db.session import SessionLocal
from app.research.policy import evaluate_web_research
from app.research.providers.fake import FakeWebProvider, fake_dns_resolver
from app.research.url_safety import content_type_allowed, validate_public_url
from tests.conftest import (
    ANNA_EMAIL, ANNA_PASSWORD, TOBIAS_EMAIL, TOBIAS_PASSWORD,
    OUTSIDER_EMAIL, OUTSIDER_PASSWORD, login, unsafe_headers,
)

WEB_CLASSIFICATION = {
    "sensitivity": "public", "origin": "synthetic", "processing_mode": "cloud_assisted",
    "web_research_mode": "validated_public", "nda_applies": False,
}


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def web_enabled(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "web_research_enabled", True)
    monkeypatch.setattr(s, "web_research_fake_provider", True)
    monkeypatch.setattr(s, "firecrawl_api_key", None)
    return s


def _headers(csrf: str) -> dict[str, str]:
    h = unsafe_headers(csrf)
    h["Idempotency-Key"] = uuid.uuid4().hex
    return h


def _create_research_project(client, csrf: str, title="Web Research Project") -> str:
    res = client.post("/api/v1/projects", json={
        "title": title, "description": "Public web research test.",
        "funding_instrument_profile_id":
            "innosuisse_innovation_project_with_implementation_partner",
        "data_classification": WEB_CLASSIFICATION,
    }, headers=_headers(csrf))
    assert res.status_code == 201, res.text
    return res.json()["project_id"]


def _task_payload(**over) -> dict:
    base = {
        "purpose": "partner_role_suggestion", "subject_type": "organisation",
        "query_preview": "öffentliche Forschungskompetenz Photonik",
        "max_results": 3, "user_confirms_public_professional_purpose": True,
    }
    base.update(over)
    return base


def _run_task(client, csrf, project_id, **over):
    res = client.post(f"/api/v1/projects/{project_id}/research-tasks",
                      json=_task_payload(**over), headers=_headers(csrf))
    assert res.status_code == 202, res.text
    body = res.json()
    op = client.get(f"/api/v1/operations/{body['operation_id']}")
    assert op.status_code == 200
    return body, op.json()


# --- URL / SSRF safety ------------------------------------------------------

@pytest.mark.parametrize("url,reason", [
    ("https://localhost/x", "blocked_host"),
    ("http://example.org/x", "scheme_not_https"),
    ("file:///etc/passwd", "scheme_not_https"),
    ("https://u:p@example.org/x", "credentials_in_url"),
    ("https://127.0.0.1/x", "private_or_reserved_target"),
    ("https://10.0.0.5/x", "private_or_reserved_target"),
    ("https://169.254.169.254/latest/meta-data", "private_or_reserved_target"),
    ("https://[::1]/x", "private_or_reserved_target"),
    ("https://169.254.0.1/x", "private_or_reserved_target"),
])
def test_url_safety_blocks(url, reason):
    check = validate_public_url(url, resolver=fake_dns_resolver)
    assert not check.ok
    assert check.reason == reason


def test_url_safety_allows_public_resolved_host():
    check = validate_public_url("https://research.example.org/a", resolver=fake_dns_resolver)
    assert check.ok and check.ips


def test_url_safety_blocks_unknown_dns():
    # No resolver injection ⇒ real DNS; a non-resolving private alias is blocked.
    check = validate_public_url("https://this-host-does-not-exist.invalid/x")
    assert not check.ok


def test_content_type_allowlist():
    assert content_type_allowed("text/html; charset=utf-8")
    assert content_type_allowed("application/pdf")
    assert not content_type_allowed("application/zip")
    assert not content_type_allowed(None)


# --- data policy ------------------------------------------------------------

def _decide(**cls):
    base = dict(WEB_CLASSIFICATION)
    base.update(cls)
    return evaluate_web_research(
        classification=base, processing_mode=base["processing_mode"],
        settings=get_settings(),
    )


def test_policy_allows_public_synthetic():
    assert _decide().outcome == "allowed"


def test_policy_blocks_internal_confidential_nda_missing():
    assert _decide(sensitivity="internal").blocked
    assert _decide(sensitivity="confidential").blocked
    assert _decide(nda_applies=True).blocked
    assert evaluate_web_research(
        classification={}, processing_mode="", settings=get_settings()
    ).blocked


def test_policy_blocks_web_mode_off_and_local_only():
    assert _decide(web_research_mode="off").blocked
    assert _decide(processing_mode="local_only").blocked


def test_policy_blocks_non_public_origin():
    assert _decide(origin="real_project").blocked


# --- provider boundary ------------------------------------------------------

def test_fake_provider_search_and_fetch():
    p = FakeWebProvider(result_count=3)
    assert p.available()
    out = p.search(__import__("app.research.providers.base", fromlist=["SearchRequest"]).SearchRequest(
        query="x", max_results=2))
    assert len(out.candidates) == 2
    fetched = p.fetch(out.candidates[0].url, max_bytes=1_000_000)
    assert fetched.text and fetched.content_hash


def test_fake_provider_failure_modes():
    from app.research.providers.base import (
        CreditExceeded, ProviderError, ProviderTimeout, ProviderUnavailable, SearchRequest,
    )
    assert not FakeWebProvider(mode="unavailable").available()
    for mode, exc in [("timeout", ProviderTimeout), ("error", ProviderError),
                      ("credit", CreditExceeded), ("unavailable", ProviderUnavailable)]:
        with pytest.raises(exc):
            FakeWebProvider(mode=mode).search(SearchRequest(query="x", max_results=1))


def test_real_firecrawl_unavailable_without_key():
    from app.research.providers.firecrawl import FirecrawlProvider
    assert not FirecrawlProvider(api_key=None, timeout_seconds=5).available()


# --- research task lifecycle ------------------------------------------------

def test_create_task_member_allowed_and_succeeds(client, db, web_enabled):
    csrf = login(client, TOBIAS_EMAIL, TOBIAS_PASSWORD)  # member (corr 2 deviation)
    project_id = _create_research_project(client, csrf)
    body, op = _run_task(client, csrf, project_id)
    assert op["status"] == "succeeded"
    task = db.get(ResearchTask, body["resource_id"])
    assert task.status == "succeeded" and task.result_count == 3
    # Only the user-confirmed public query is stored.
    assert task.query_text == "öffentliche Forschungskompetenz Photonik"
    results = client.get(f"/api/v1/projects/{project_id}/research-results")
    assert results.status_code == 200
    rows = results.json()
    assert len(rows) == 3 and all(r["status"] == "candidate" for r in rows)


def test_create_task_idempotent(client, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_research_project(client, csrf)
    headers = _headers(csrf)
    payload = _task_payload()
    first = client.post(f"/api/v1/projects/{project_id}/research-tasks", json=payload, headers=headers)
    second = client.post(f"/api/v1/projects/{project_id}/research-tasks", json=payload, headers=headers)
    assert first.status_code == second.status_code == 202
    assert first.json()["resource_id"] == second.json()["resource_id"]


def test_blocked_when_web_research_disabled(client):
    # web_enabled fixture NOT used → feature unavailable → 503.
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_research_project(client, csrf)
    res = client.post(f"/api/v1/projects/{project_id}/research-tasks",
                      json=_task_payload(), headers=_headers(csrf))
    assert res.status_code == 503


def test_workspace_isolation(client, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_research_project(client, csrf)
    body, _ = _run_task(client, csrf, project_id)
    out_csrf = login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
    res = client.get(f"/api/v1/research-tasks/{body['resource_id']}")
    # Outsider session is now active; the task belongs to another workspace.
    assert res.status_code == 404


def test_blocked_classification_marks_task_failed(client, db, web_enabled):
    # An internal project is blocked by the web-research policy in the executor.
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    res = client.post("/api/v1/projects", json={
        "title": "Internal", "description": "internal",
        "funding_instrument_profile_id":
            "innosuisse_innovation_project_with_implementation_partner",
        "data_classification": {
            "sensitivity": "internal", "origin": "real_project",
            "processing_mode": "cloud_assisted", "web_research_mode": "validated_public",
            "nda_applies": False,
        },
    }, headers=_headers(csrf))
    project_id = res.json()["project_id"]
    body, op = _run_task(client, csrf, project_id)
    assert op["status"] == "failed"
    task = db.get(ResearchTask, body["resource_id"])
    assert task.status == "blocked"


# --- import → SourceDocument + A1 synthesis ---------------------------------

def _first_candidate(client, project_id):
    rows = client.get(f"/api/v1/projects/{project_id}/research-results").json()
    return rows[0]["result_id"]


def test_import_creates_source_with_fragments_and_no_anchor(client, db, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_research_project(client, csrf)
    _run_task(client, csrf, project_id)
    result_id = _first_candidate(client, project_id)

    res = client.post(f"/api/v1/research-results/{result_id}/import", headers=_headers(csrf))
    assert res.status_code == 201, res.text
    doc = res.json()
    assert doc["type"] == "url" and doc["status"] == "processed"
    assert doc["data_classification"]["origin"] == "public_source"
    assert doc["data_classification"]["sensitivity"] == "public"

    # Appears in listSources.
    listed = client.get(f"/api/v1/projects/{project_id}/sources").json()
    assert any(s["source_id"] == doc["source_id"] for s in listed)

    version = db.scalar(select(SourceVersion).where(
        SourceVersion.source_document_id == doc["source_id"]))
    assert version is not None and version.processing_status == "processed"
    frags = db.scalars(select(SourceFragment).where(
        SourceFragment.source_version_id == version.source_version_id)).all()
    assert len(frags) >= 1
    # No EvidenceAnchor is created directly from the import (corr 10).
    anchors = db.scalars(select(EvidenceAnchor).where(
        EvidenceAnchor.source_version_id == version.source_version_id)).all()
    assert anchors == []

    db.expire_all()
    rr = db.scalar(select(ResearchResult).where(ResearchResult.result_id == result_id))
    assert rr.status == "imported" and rr.source_document_id == doc["source_id"]


def test_import_runs_advisory_a1_synthesis(client, db, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_research_project(client, csrf)
    _run_task(client, csrf, project_id)
    result_id = _first_candidate(client, project_id)
    res = client.post(f"/api/v1/research-results/{result_id}/import", headers=_headers(csrf))
    assert res.status_code == 201

    db.expire_all()
    rr = db.scalar(select(ResearchResult).where(ResearchResult.result_id == result_id))
    task = db.get(ResearchTask, rr.research_task_id)
    assert task.a1_synthesis_status == "succeeded"
    assert len(rr.professional_evidence) >= 1
    assert len(rr.partner_role_suggestions) >= 1
    ev = rr.professional_evidence[0]
    assert ev["source_url"] and ev["source_id"] == rr.source_document_id
    assert rr.partner_role_suggestions[0]["human_review_required"] is True


def test_a1_failure_is_non_blocking(client, db, web_enabled, monkeypatch):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_research_project(client, csrf)
    _run_task(client, csrf, project_id)
    result_id = _first_candidate(client, project_id)

    from app.agents import public_competence_research
    monkeypatch.setattr(
        public_competence_research, "synthesize_after_import",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    res = client.post(f"/api/v1/research-results/{result_id}/import", headers=_headers(csrf))
    # Import still succeeds and the source is preserved (corr 6).
    assert res.status_code == 201
    doc = res.json()
    assert doc["status"] == "processed"
    db.expire_all()
    rr = db.scalar(select(ResearchResult).where(ResearchResult.result_id == result_id))
    assert rr.status == "imported"
    assert rr.professional_evidence == []


def test_import_idempotent(client, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_research_project(client, csrf)
    _run_task(client, csrf, project_id)
    result_id = _first_candidate(client, project_id)
    headers = _headers(csrf)
    first = client.post(f"/api/v1/research-results/{result_id}/import", headers=headers)
    second = client.post(f"/api/v1/research-results/{result_id}/import", headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json()["source_id"] == second.json()["source_id"]


def test_capabilities_reflect_web_research(client, web_enabled):
    login(client, ANNA_EMAIL, ANNA_PASSWORD)
    caps = client.get("/api/v1/capabilities").json()
    assert caps["features"]["web_research"] is True
    # url_import stays false — web import is internal only (corr 3).
    assert caps["features"]["url_import"] is False
