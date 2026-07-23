"""R8 — Freigabepflicht für Planner-Queries (Markt-/Webrecherche).

Jede ausgehende Planner-Query braucht eine explizite menschliche Freigabe
(``SearchQueryApproval``, single-use): der Plan-Endpoint legt pending Freigaben an,
der Run-Endpoint führt NUR freigegebene Queries aus, ein realer Provider ohne
Freigabe wird strukturell abgelehnt («ohne Freigabe kein Firecrawl-Aufruf»), und
Bearbeiten erzeugt eine neue Firewall-Prüfung + neue Freigabe (Projekt-Lexikon
greift dabei auch für D0). Plus: Guard gegen eine zweite Planner-Implementierung.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config.settings import get_settings
from app.db.models import AuditEvent, ResearchTask, SearchQueryApproval
from app.db.session import SessionLocal
from app.market_research.planner import MarketTopic
from app.market_research.runner import run_market_research
from app.research.service import ResearchBlocked
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, login, unsafe_headers
from tests.research_brief_helpers import approve_research_brief

_D0 = {
    "sensitivity": "public", "origin": "synthetic", "processing_mode": "cloud_assisted",
    "web_research_mode": "validated_public", "nda_applies": False,
}
TOPIC_PAYLOAD = {
    "application_domain": "manufacturing quality assurance",
    "technology_area": "industrial AI anomaly detection",
    "target_customers": "manufacturing SMEs",
    "region": "Switzerland",
}


@pytest.fixture
def web_fake(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "web_research_enabled", True)
    monkeypatch.setattr(s, "web_research_fake_provider", True)
    monkeypatch.setattr(s, "firecrawl_api_key", None)
    return s


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _headers(csrf: str) -> dict[str, str]:
    h = unsafe_headers(csrf)
    h["Idempotency-Key"] = uuid.uuid4().hex
    return h


def _project(client, csrf, *, title="Market Approval Project") -> str:
    res = client.post("/api/v1/projects", json={
        "title": title,
        "description": "R8-Freigabepflicht-Testprojekt.",
        "innovation_field": "ICT / Industrial AI",
        "funding_instrument_profile_id":
            "innosuisse_innovation_project_with_implementation_partner",
        "data_classification": _D0,
    }, headers=_headers(csrf))
    assert res.status_code == 201, res.text
    return res.json()["project_id"]


def _plan(client, csrf, project_id) -> dict:
    workspace = client.get(f"/api/v1/projects/{project_id}/research-workspace")
    assert workspace.status_code == 200, workspace.text
    if workspace.json()["brief"]["active_approved"] is None:
        approve_research_brief(client, csrf, project_id)
    res = client.post(f"/api/v1/projects/{project_id}/market-research/plan",
                      json={}, headers=unsafe_headers(csrf))
    assert res.status_code == 200, res.text
    return res.json()


def _approve(client, csrf, approval_id, *, reject=False):
    verb = "reject" if reject else "approve"
    return client.post(
        f"/api/v1/search-query-approvals/{approval_id}/{verb}",
        headers=unsafe_headers(csrf),
    )


def _run(client, csrf, project_id, approval_ids):
    workspace = client.get(f"/api/v1/projects/{project_id}/research-workspace")
    assert workspace.status_code == 200, workspace.text
    if workspace.json()["brief"]["active_approved"] is None:
        approve_research_brief(client, csrf, project_id)
    return client.post(
        f"/api/v1/projects/{project_id}/market-research/run",
        json={**TOPIC_PAYLOAD, "approval_ids": approval_ids},
        headers=_headers(csrf),
    )


# --- Plan legt pending Freigaben an ------------------------------------------


def test_plan_creates_pending_approvals_per_query(client, db, web_fake):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf)
    body = _plan(client, csrf, pid)
    assert 3 <= len(body["queries"]) <= 5
    for q in body["queries"]:
        assert q["approval_required"] is True
        assert q["approval_id"], q
        appr = db.get(SearchQueryApproval, q["approval_id"])
        assert appr is not None and appr.status == "pending"
        assert appr.project_id == pid
        # Feingranularer Planner-Zweck bleibt auf der Freigabe erhalten.
        assert appr.purpose == f"research:{appr.research_module}:{q['purpose']}"
        assert appr.research_brief_id
        assert appr.planner_purpose == q["purpose"]
        # Es wird exakt der angezeigte Text freigegeben.
        assert appr.sanitized_query == q["query_text"]


# --- Freigabepflicht ----------------------------------------------------------


def test_run_without_approvals_rejected(client, web_fake):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf)
    res = _run(client, csrf, pid, [])
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "approval_required"


def test_runner_refuses_unapproved_live_provider(db, monkeypatch):
    """Ohne Freigabe kein Firecrawl-Aufruf: der freigabelose Auto-Pfad ist auf den
    Fake-Provider (CI/Eval) begrenzt und lehnt einen realen Provider strukturell ab —
    bevor irgendein Provider-Code läuft."""
    s = get_settings()
    monkeypatch.setattr(s, "web_research_enabled", True)
    monkeypatch.setattr(s, "web_research_fake_provider", False)
    monkeypatch.setattr(s, "firecrawl_api_key", "test-key-never-used")
    from app.db.models import Project, Workspace
    ws = "ws-market-approval"
    if db.get(Workspace, ws) is None:
        db.add(Workspace(id=ws, name="Market Approval WS"))
        db.commit()
    project = Project(
        project_id="mkt-appr-" + uuid.uuid4().hex[:8], workspace_id=ws,
        title="Live ohne Freigabe", description="d",
        funding_instrument_profile_id=(
            "innosuisse_innovation_project_with_implementation_partner"
        ),
        data_classification=dict(_D0), created_by="user-anna", status="draft",
    )
    db.add(project)
    db.commit()
    with pytest.raises(ResearchBlocked) as exc:
        run_market_research(
            db, project=project, actor_user_id="user-anna",
            topic=MarketTopic(**{k: v for k, v in TOPIC_PAYLOAD.items()}),
            case_id="R8", data_mode="synthetic_eval",
        )
    assert exc.value.code == "approval_required"
    assert db.scalar(
        select(ResearchTask).where(ResearchTask.project_id == project.project_id)
    ) is None


def test_only_approved_queries_execute_and_are_consumed(client, db, web_fake):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf)
    queries = _plan(client, csrf, pid)["queries"]
    approval_ids = [q["approval_id"] for q in queries]
    # Nur 2 von 5 freigeben; der Rest bleibt pending.
    for approval_id in approval_ids[:2]:
        assert _approve(client, csrf, approval_id).status_code == 200

    # Ein gemischter Batch wird fail-closed abgelehnt; pending Queries werden
    # weder still uebersprungen noch als teilweise ausgefuehrt dargestellt.
    mixed_res = _run(client, csrf, pid, approval_ids)
    assert mixed_res.status_code == 422, mixed_res.text
    assert mixed_res.json()["code"] == "approval_required"

    res = _run(client, csrf, pid, approval_ids[:2])
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["task_ids"]) == 2
    assert body["blocked_queries"] == 0

    db.expire_all()
    approved_texts = {q["query_text"] for q in queries[:2]}
    for task_id in body["task_ids"]:
        task = db.get(ResearchTask, task_id)
        # Ausgeführt wird exakt der freigegebene Text; die Task trägt die Provenienz.
        assert task.query_text in approved_texts
        assert task.firewall_approval_id in approval_ids[:2]
    for approval_id in approval_ids[:2]:
        assert db.get(SearchQueryApproval, approval_id).status == "used"
    for approval_id in approval_ids[2:]:
        assert db.get(SearchQueryApproval, approval_id).status == "pending"


def test_rejected_approvals_never_execute(client, db, web_fake):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf)
    queries = _plan(client, csrf, pid)["queries"]
    approval_ids = [q["approval_id"] for q in queries]
    for approval_id in approval_ids:
        assert _approve(client, csrf, approval_id, reject=True).status_code == 200

    res = _run(client, csrf, pid, approval_ids)
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "approval_required"
    db.expire_all()
    assert db.scalar(
        select(ResearchTask).where(ResearchTask.project_id == pid)
    ) is None
    for approval_id in approval_ids:
        assert db.get(SearchQueryApproval, approval_id).status == "rejected"


# --- Re-Plan & Idempotenz: bereits entschiedene Freigaben ----------------------


def test_replan_exposes_status_of_decided_approvals(client, db, web_fake):
    """Regression (Freigabe-Bug 2026-07-23): der Dialog re-plant bei jedem Öffnen.
    Bereits entschiedene Freigaben müssen ihren Status im Plan-DTO tragen — sonst
    rendert die UI sie als offen und ein erneutes Freigeben endet im 409."""
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf)
    first = _plan(client, csrf, pid)["queries"]
    assert all(q["status"] == "pending" for q in first)
    approved_id = first[0]["approval_id"]
    assert _approve(client, csrf, approved_id).status_code == 200

    second = _plan(client, csrf, pid)["queries"]
    by_id = {q["approval_id"]: q for q in second}
    assert by_id[approved_id]["status"] == "approved"
    assert all(
        q["status"] == "pending"
        for q in second if q["approval_id"] != approved_id
    )


def test_repeated_identical_decision_is_idempotent(client, db, web_fake):
    """Gleiche Entscheidung wiederholen ist idempotent (200, Zustand unverändert,
    genau EIN Audit-Event); eine ANDERE Entscheidung auf einer entschiedenen
    Freigabe bleibt fail-closed 409."""
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf)
    approval_id = _plan(client, csrf, pid)["queries"][0]["approval_id"]

    assert _approve(client, csrf, approval_id).status_code == 200
    res = _approve(client, csrf, approval_id)
    assert res.status_code == 200, res.text
    db.expire_all()
    assert db.get(SearchQueryApproval, approval_id).status == "approved"
    events = db.scalars(
        select(AuditEvent).where(
            AuditEvent.action == "search_query.approval_decided",
            AuditEvent.target_id == approval_id,
        )
    ).all()
    assert len(events) == 1

    conflict = _approve(client, csrf, approval_id, reject=True)
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["code"] == "approval_not_pending"
    db.expire_all()
    assert db.get(SearchQueryApproval, approval_id).status == "approved"


# --- Bearbeiten: neue Prüfung + neue Freigabe; Lexikon auch für D0 -------------


def test_edited_query_is_bound_to_brief_and_invalidates_old_approval(client, db, web_fake):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf, title="QuantumFoam")
    res = client.post(
        f"/api/v1/projects/{pid}/partners",
        json={"name": "Acme Robotics AG", "partner_type": "implementation_partner"},
        headers=_headers(csrf),
    )
    assert res.status_code == 201, res.text

    old = _plan(client, csrf, pid)["queries"][0]
    workspace = client.get(f"/api/v1/projects/{pid}/research-workspace").json()
    brief_id = workspace["brief"]["active_approved"]["research_brief_id"]
    blocked = client.post(
        f"/api/v1/research-briefs/{brief_id}/queries/preview",
        json={"query_text": "QuantumFoam Acme-Robotics market size Switzerland",
              "module": "market_growth", "planner_purpose": "market_size",
              "supersedes_approval_id": old["approval_id"]},
        headers=unsafe_headers(csrf),
    )
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["code"] == "query_not_derived_from_brief"
    db.expire_all()
    assert db.get(SearchQueryApproval, old["approval_id"]).status == "expired"

    res = client.post(
        f"/api/v1/research-briefs/{brief_id}/queries/preview",
        json={"query_text": "manufacturing quality assurance market growth Switzerland",
              "module": "market_growth", "planner_purpose": "market_size",
              "supersedes_approval_id": None},
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["approval_id"] != old["approval_id"]
    assert db.get(SearchQueryApproval, body["approval_id"]).status == "pending"
    db.expire_all()
    assert db.get(SearchQueryApproval, old["approval_id"]).status == "expired"


def test_legacy_market_preview_success_returns_new_pending_approval(client, db, web_fake):
    """Regression (RUN 2A Slice 0): der projektbezogene Preview-Endpoint
    ``/projects/{id}/market-research/queries/preview`` — der Erfolgspfad des
    Bearbeitens im Analyse-Dialog — crashte mit AttributeError, weil
    ``preview_query`` eine ``ResearchQueryView`` liefert (Feld ``query_text``,
    nicht ``sanitized_query``). Pinnt den Erfolgspfad des Legacy-Adapters."""
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    pid = _project(client, csrf)
    old = _plan(client, csrf, pid)["queries"][0]
    res = client.post(
        f"/api/v1/projects/{pid}/market-research/queries/preview",
        json={
            "query_text": "manufacturing quality assurance market growth Switzerland",
            "purpose": "market_size",
        },
        headers=unsafe_headers(csrf),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["public_safe"] is True
    assert body["approval_id"] and body["approval_id"] != old["approval_id"]
    assert body["query_text"]
    db.expire_all()
    assert db.get(SearchQueryApproval, body["approval_id"]).status == "pending"


# --- Guard: keine zweite Planner-/Runner-Implementierung -----------------------


def test_single_planner_implementation_guard():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    assert not (app_dir / "market" / "query_planner.py").exists(), (
        "Kein zweiter Planner: backend/app/market/query_planner.py darf nicht existieren."
    )
    definition = re.compile(r"^\s*def plan_market_queries\(", re.MULTILINE)
    hits = [
        p for p in app_dir.rglob("*.py")
        if definition.search(p.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert [p.name for p in hits] == ["planner.py"], hits
