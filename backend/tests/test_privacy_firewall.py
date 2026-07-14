"""Milestone 9J — Search Query Firewall: approval flow, D0/D1/D2/D3 web-research
integration, no-raw leakage, workspace isolation, provider boundary, D2 live gate.

Fake provider only (no network). The RAW query never reaches the provider, the DB or the
logs for a confidential class — only the firewall-sanitized query does.
"""
from __future__ import annotations

import json
import logging
import uuid

import pytest
from sqlalchemy import select

from app.config.settings import get_settings
from app.config.logging import RedactingFilter
from app.db.models import (
    AuditEvent,
    ControlResult,
    Project,
    ResearchBrief,
    ResearchResult,
    ResearchTask,
    SearchQueryApproval,
    SourceDocument,
    ToolInvocation,
)
from app.db.session import SessionLocal
from app.research.providers.fake import FakeWebProvider, fake_dns_resolver
from app.research.providers.resolver import set_override
from tests.conftest import (
    ANNA_EMAIL, ANNA_PASSWORD, OUTSIDER_EMAIL, OUTSIDER_PASSWORD,
    login, unsafe_headers,
)

PROFILE = "innosuisse_innovation_project_with_implementation_partner"
PARTNER = "Acme Robotics AG"
BUDGET = 500000
# A search-like D2 query carrying a partner name + a budget figure (Flow B).
D2_QUERY = "Wettbewerber für Acme Robotics AG mit Budget CHF 500'000"


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
    monkeypatch.setattr(s, "d2_web_research_enabled", False)
    return s


class _SpyProvider(FakeWebProvider):
    """Records every query the executor hands to the provider (to prove no raw leak)."""

    seen: list[str] = []

    def search(self, request):
        _SpyProvider.seen.append(request.query)
        return super().search(request)


@pytest.fixture
def spy_provider():
    _SpyProvider.seen = []
    set_override((_SpyProvider(), fake_dns_resolver))
    try:
        yield _SpyProvider
    finally:
        set_override(None)


def _headers(csrf: str) -> dict[str, str]:
    h = unsafe_headers(csrf)
    h["Idempotency-Key"] = uuid.uuid4().hex
    return h


def _project(client, csrf, *, sensitivity, origin, nda=False, budget=None, title="P"):
    body = {
        "title": title, "description": "d", "funding_instrument_profile_id": PROFILE,
        "data_classification": {
            "sensitivity": sensitivity, "origin": origin,
            "processing_mode": "cloud_assisted", "web_research_mode": "validated_public",
            "nda_applies": nda,
        },
    }
    if budget is not None:
        body["budget_framework_chf"] = budget
    res = client.post("/api/v1/projects", json=body, headers=_headers(csrf))
    assert res.status_code == 201, res.text
    return res.json()["project_id"]


def _partner(client, csrf, project_id, name=PARTNER):
    res = client.post(
        f"/api/v1/projects/{project_id}/partners",
        json={"name": name, "partner_type": "implementation_partner"},
        headers=_headers(csrf),
    )
    assert res.status_code == 201, res.text


def _preview(client, csrf, project_id, raw_query):
    return client.post(
        f"/api/v1/projects/{project_id}/search-query-firewall/preview",
        json={"raw_query": raw_query}, headers=unsafe_headers(csrf),
    )


def _approve(client, csrf, approval_id, *, reject=False):
    verb = "reject" if reject else "approve"
    return client.post(
        f"/api/v1/search-query-approvals/{approval_id}/{verb}", headers=unsafe_headers(csrf)
    )


def _create_task(client, csrf, project_id, query, approval_id=None):
    if approval_id:
        _bind_approval_to_brief(project_id, approval_id)
    payload = {
        "purpose": "partner_role_suggestion", "subject_type": "topic",
        "query_preview": query, "max_results": 3,
        "user_confirms_public_professional_purpose": True,
    }
    if approval_id:
        payload["approval_id"] = approval_id
    return client.post(
        f"/api/v1/projects/{project_id}/research-tasks", json=payload, headers=_headers(csrf)
    )


def _bind_approval_to_brief(project_id: str, approval_id: str) -> None:
    """Make a legacy firewall fixture satisfy mandatory brief provenance."""
    session = SessionLocal()
    try:
        project = session.get(Project, project_id)
        approval = session.get(SearchQueryApproval, approval_id)
        brief = session.scalar(select(ResearchBrief).where(
            ResearchBrief.project_id == project_id,
            ResearchBrief.status == "approved",
        ))
        if brief is None:
            brief = ResearchBrief(
                research_brief_id=str(uuid.uuid4()),
                project_id=project_id,
                workspace_id=project.workspace_id,
                version=1,
                status="approved",
                application_domain="public industrial research",
                technology_class="robotics",
                target_customer_segments=["industrial organisations"],
                region="Switzerland",
                competence_needs=[],
                modules=["market_growth"],
                content_hash=uuid.uuid4().hex,
                created_by="test-user",
                approved_by="test-user",
            )
            session.add(brief)
            session.flush()
        approval.research_brief_id = brief.research_brief_id
        approval.research_module = "market_growth"
        approval.planner_purpose = "market_size"
        session.commit()
    finally:
        session.close()


def _poll(client, operation_id):
    op = client.get(f"/api/v1/operations/{operation_id}").json()
    return op["status"]


# --- D0 unchanged -----------------------------------------------------------

def test_d0_direct_task_without_brief_is_rejected(client, web_enabled, spy_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf, sensitivity="public", origin="synthetic")
    res = _create_task(client, csrf, pid, "öffentliche Wettbewerbsanalyse Robotik")
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "research_brief_approval_required"
    assert spy_provider.seen == []


# --- D2 requires a sanitized + approved query -------------------------------

def test_d2_requires_approval(client, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf, sensitivity="confidential", origin="real_project")
    res = _create_task(client, csrf, pid, "Wettbewerber für unser Projekt")
    assert res.status_code == 422
    assert res.json()["code"] == "research_brief_approval_required"


def test_d2_full_sanitized_flow(client, db, web_enabled, spy_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf, sensitivity="confidential", origin="real_project",
                   budget=BUDGET, title="Geheimprojekt")
    _partner(client, csrf, pid)

    prev = _preview(client, csrf, pid, D2_QUERY).json()
    assert prev["decision"] == "require_human_approval"
    assert prev["approval_id"]
    # The sanitized query carries neither the partner name nor the budget figure.
    assert "Acme" not in prev["sanitized_query"] and "Robotics" not in prev["sanitized_query"]
    assert "500" not in prev["sanitized_query"]
    cats = {c["category"] for c in prev["redaction_summary"]}
    assert "partner_name" in cats and "budget_amount" in cats

    approved = _approve(client, csrf, prev["approval_id"])
    assert approved.status_code == 200 and approved.json()["status"] == "approved"

    created = _create_task(client, csrf, pid, D2_QUERY, approval_id=prev["approval_id"])
    assert created.status_code == 202, created.text
    assert _poll(client, created.json()["operation_id"]) == "succeeded"

    task = db.get(ResearchTask, created.json()["resource_id"])
    # Only the sanitized query is stored + sent to the provider.
    assert "Acme" not in task.query_text and "500" not in task.query_text
    assert task.firewall_data_class == "D2_CONFIDENTIAL_IDEA"
    assert task.firewall_approval_id == prev["approval_id"]
    assert _SpyProvider.seen, "provider was never called"
    for sent in _SpyProvider.seen:
        assert "Acme" not in sent and "Robotics" not in sent and "500" not in sent

    # The approval is single-use → now 'used'; raw query never stored.
    appr = db.get(SearchQueryApproval, prev["approval_id"])
    assert appr.status == "used" and appr.used_by_research_task_id == task.research_task_id
    assert "Acme" not in appr.sanitized_query and "500" not in appr.sanitized_query


def test_d2_hyphenated_partner_and_word_budget_sanitized(client, web_enabled):
    """R8-Leakage: zusammengesetzte/Bindestrich-Partnernamen und Beträge in Zahlwörtern
    werden auch dann entfernt, wenn sie nicht exakt der erfassten Schreibweise entsprechen."""
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf, sensitivity="confidential", origin="real_project")
    _partner(client, csrf, pid)  # "Acme Robotics AG"

    prev = _preview(
        client, csrf, pid, "Marktübersicht Acme-Robotics halbe Million Franken Automatisierung"
    ).json()
    assert prev["decision"] == "require_human_approval"
    low = prev["sanitized_query"].lower()
    assert "acme" not in low and "robotics" not in low
    assert "million" not in low and "franken" not in low
    cats = {c["category"] for c in prev["redaction_summary"]}
    assert "partner_name" in cats and "budget_amount" in cats


def test_d2_project_codename_sanitized(client, web_enabled):
    # Der Projektcodename (Titel) steht im D2-Lexikon (project_name) und wird entfernt.
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf, sensitivity="confidential", origin="real_project",
                   title="QuantumFoam")
    prev = _preview(client, csrf, pid, "Wettbewerber QuantumFoam Anomalieerkennung").json()
    assert prev["decision"] == "require_human_approval"
    assert "quantumfoam" not in prev["sanitized_query"].lower()
    assert "project_name" in {c["category"] for c in prev["redaction_summary"]}


def test_d2_full_idea_blocked(client, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf, sensitivity="confidential", origin="real_project")
    idea = (
        "Wir entwickeln eine neuartige vertrauliche Plattform die mit Hilfe von "
        "maschinellem Lernen die Logistikprozesse unserer Partner grundlegend optimiert "
        "und dabei ein einzigartiges Geschäftsmodell verfolgt"
    )
    prev = _preview(client, csrf, pid, idea).json()
    assert prev["decision"] == "block"
    assert prev["approval_id"] is None
    assert prev["sanitized_query"] == ""


# --- D3 / UNKNOWN blocked ---------------------------------------------------

def test_d3_blocked_at_creation(client, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf, sensitivity="confidential", origin="real_project", nda=True)
    res = _create_task(client, csrf, pid, "irgendeine Anfrage")
    assert res.status_code == 403
    assert res.json()["code"] == "web_research_class_blocked"


def test_unknown_blocked_at_creation(client, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    # public sensitivity + real_project origin → UNKNOWN (deny-by-default).
    pid = _project(client, csrf, sensitivity="public", origin="real_project")
    res = _create_task(client, csrf, pid, "irgendeine Anfrage")
    assert res.status_code == 403


# --- approval lifecycle -----------------------------------------------------

def test_approval_single_use(client, web_enabled, spy_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf, sensitivity="confidential", origin="real_project", budget=BUDGET)
    _partner(client, csrf, pid)
    approval_id = _preview(client, csrf, pid, D2_QUERY).json()["approval_id"]
    _approve(client, csrf, approval_id)
    first = _create_task(client, csrf, pid, D2_QUERY, approval_id=approval_id)
    assert first.status_code == 202
    second = _create_task(client, csrf, pid, D2_QUERY, approval_id=approval_id)
    assert second.status_code == 409
    assert second.json()["code"] == "approval_already_used"


def test_client_query_change_cannot_replace_server_approved_query(
    client, db, web_enabled, spy_provider
):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf, sensitivity="confidential", origin="real_project", budget=BUDGET)
    _partner(client, csrf, pid)
    approval_id = _preview(client, csrf, pid, D2_QUERY).json()["approval_id"]
    _approve(client, csrf, approval_id)
    changed = _create_task(client, csrf, pid, D2_QUERY + " zusätzlich", approval_id=approval_id)
    assert changed.status_code == 202, changed.text
    assert _poll(client, changed.json()["operation_id"]) == "succeeded"
    task = db.get(ResearchTask, changed.json()["resource_id"])
    approval = db.get(SearchQueryApproval, approval_id)
    assert task.query_text == approval.sanitized_query
    assert "zusätzlich" not in task.query_text


def test_rejected_approval_blocks(client, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf, sensitivity="confidential", origin="real_project", budget=BUDGET)
    _partner(client, csrf, pid)
    approval_id = _preview(client, csrf, pid, D2_QUERY).json()["approval_id"]
    assert _approve(client, csrf, approval_id, reject=True).json()["status"] == "rejected"
    res = _create_task(client, csrf, pid, D2_QUERY, approval_id=approval_id)
    assert res.status_code == 422
    assert res.json()["code"] == "approval_not_approved"


# --- workspace isolation ----------------------------------------------------

def test_approval_workspace_isolation(client, web_enabled):
    anna = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, anna, sensitivity="confidential", origin="real_project", budget=BUDGET)
    _partner(client, anna, pid)
    approval_id = _preview(client, anna, pid, D2_QUERY).json()["approval_id"]
    # An outsider in another workspace cannot see or approve it.
    outsider = login(client, OUTSIDER_EMAIL, OUTSIDER_PASSWORD)
    res = _approve(client, outsider, approval_id)
    assert res.status_code == 404


# --- D2 live-provider gate (correction 1) -----------------------------------

def test_d2_live_provider_gate_blocks_without_flag(client, db, monkeypatch):
    # Web research 'available' via a (never-called) key, but fake OFF and the D2 live flag
    # OFF → an approved D2 query must NOT reach a live provider; the executor blocks first.
    s = get_settings()
    monkeypatch.setattr(s, "web_research_enabled", True)
    monkeypatch.setattr(s, "web_research_fake_provider", False)
    monkeypatch.setattr(s, "firecrawl_api_key", "unused-key")
    monkeypatch.setattr(s, "d2_web_research_enabled", False)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf, sensitivity="confidential", origin="real_project", budget=BUDGET)
    _partner(client, csrf, pid)
    approval_id = _preview(client, csrf, pid, D2_QUERY).json()["approval_id"]
    _approve(client, csrf, approval_id)
    created = _create_task(client, csrf, pid, D2_QUERY, approval_id=approval_id)
    assert created.status_code == 202
    assert _poll(client, created.json()["operation_id"]) == "failed"
    task = db.get(ResearchTask, created.json()["resource_id"])
    assert task.status == "blocked" and task.error_code == "d2_live_web_research_disabled"


# --- no-raw leakage ---------------------------------------------------------

def test_no_raw_query_in_persisted_records(client, db, web_enabled, spy_provider):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf, sensitivity="confidential", origin="real_project", budget=BUDGET)
    _partner(client, csrf, pid)
    approval_id = _preview(client, csrf, pid, D2_QUERY).json()["approval_id"]
    _approve(client, csrf, approval_id)
    created = _create_task(client, csrf, pid, D2_QUERY, approval_id=approval_id)
    assert _poll(client, created.json()["operation_id"]) == "succeeded"

    forbidden = ("Acme", "Robotics", "500'000", "500000")

    def _clean(rows_text: str) -> None:
        for term in forbidden:
            assert term not in rows_text, f"leaked {term!r}"

    audits = db.scalars(select(AuditEvent).where(AuditEvent.workspace_id != "")).all()
    _clean(json.dumps([a.detail for a in audits], ensure_ascii=False, default=str))
    controls = db.scalars(select(ControlResult).where(ControlResult.project_id == pid)).all()
    _clean(json.dumps([c.detail for c in controls], ensure_ascii=False, default=str))
    tools = db.scalars(
        select(ToolInvocation).where(ToolInvocation.workspace_id != "")
    ).all()
    _clean(json.dumps([t.input_hash for t in tools], ensure_ascii=False, default=str))
    # The public research-results contract also must not surface the raw query.
    results = client.get(f"/api/v1/projects/{pid}/research-results").text
    _clean(results)


def test_log_redaction_scrubs_query_but_keeps_hash():
    f = RedactingFilter()
    rec = logging.LogRecord(
        "x", logging.INFO, __file__, 1,
        'query="Acme Robotics geheim" raw_query_hash=deadbeef', (), None,
    )
    assert f.filter(rec)
    msg = rec.getMessage()
    assert "Acme" not in msg and "geheim" not in msg
    assert "deadbeef" in msg  # the hash is preserved


# --- provider boundary (correction 4) ---------------------------------------

def test_provider_boundary_only_reached_via_research_modules():
    """No agent/tool module may import the web provider resolver directly: the only
    path to the provider is Agent → service → executor/import_service → provider."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    allowed = {
        ("research", "executor.py"),
        ("research", "import_service.py"),
        ("research", "providers", "resolver.py"),
    }
    offenders = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).parts
        if rel[:2] in {a[:2] for a in allowed} and rel[-1] in {a[-1] for a in allowed}:
            continue
        text = path.read_text(encoding="utf-8")
        if "get_web_provider(" in text or "provider.search(" in text:
            offenders.append("/".join(rel))
    assert not offenders, f"web provider reached outside the research boundary: {offenders}"


def test_import_from_d2_task_creates_public_source(
    client, db, web_enabled, spy_provider, monkeypatch
):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf, sensitivity="confidential", origin="real_project", budget=BUDGET)
    _partner(client, csrf, pid)
    approval_id = _preview(client, csrf, pid, D2_QUERY).json()["approval_id"]
    _approve(client, csrf, approval_id)
    created = _create_task(client, csrf, pid, D2_QUERY, approval_id=approval_id)
    assert _poll(client, created.json()["operation_id"]) == "succeeded"
    result_id = client.get(f"/api/v1/projects/{pid}/research-results").json()[0]["result_id"]
    # Exercise the live import contract with the deterministic fake transport as a
    # test double. The persisted provenance remains live and the D2 feature flag is on.
    from app.research import import_service

    result = db.get(ResearchResult, result_id)
    task = db.get(ResearchTask, result.research_task_id)
    task.provider = "firecrawl"
    task.execution_mode = "live"
    web_enabled.d2_web_research_enabled = True
    db.commit()
    monkeypatch.setattr(
        import_service,
        "get_web_provider",
        lambda settings: (FakeWebProvider(result_count=1), fake_dns_resolver),
    )
    imported = client.post(
        f"/api/v1/research-results/{result_id}/import", headers=_headers(csrf)
    )
    assert imported.status_code == 201, imported.text
    doc = db.get(SourceDocument, imported.json()["source_id"])
    assert doc.data_classification["origin"] == "public_source"
    assert doc.data_classification["sensitivity"] == "public"
