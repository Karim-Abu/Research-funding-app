"""RESEARCH.2 — Partner Research MVP (Backend + Report), fake provider only.

No network: the FakeWebProvider drives everything (``web_research_fake_provider=True``).
Covers the deterministic partner-query planner (organisation/topic only, never a person),
the firewall-reuse policy (D0 allowed; D2 without approval and D3/UNKNOWN blocked),
ResearchResult + ToolInvocation creation, the PartnerCandidate view (candidate_type/
confidence/status, no Partner row auto-creation, no eligibility/contact claims), and the
no-raw/canary property.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.config.settings import get_settings
from app.db.models import (
    AuditEvent,
    Partner,
    Project,
    ResearchResult,
    ResearchTask,
    ToolInvocation,
    Workspace,
)
from app.db.session import SessionLocal
from app.partner_research.candidates import to_partner_candidates
from app.partner_research.planner import PartnerTopic, plan_partner_queries
from app.partner_research.report import render_report
from app.partner_research.runner import run_partner_research
from app.research import service
from app.research.executor import _SEARCH_TOOL, research_executor
from app.research.recording import record_tool
from app.research.service import ResearchBlocked

TOPIC = PartnerTopic(
    application_domain="manufacturing quality monitoring",
    technology_area="industrial AI anomaly detection",
    competence_areas=["explainable AI", "production analytics"],
    region="Switzerland",
)
CANARY = "PROJECT_SECRET_MARKER_R5_INJECTION"
# Dedicated workspace from the start (RESEARCH.1a taught us not to pollute ws-demo).
WS = "ws-partner-research"

_D0 = {"sensitivity": "public", "origin": "synthetic",
       "processing_mode": "cloud_assisted", "web_research_mode": "validated_public",
       "nda_applies": False}
_D2 = {"sensitivity": "confidential", "origin": "real_project",
       "processing_mode": "cloud_assisted", "web_research_mode": "validated_public",
       "nda_applies": False}
_D3 = {**_D0, "nda_applies": True}
_UNKNOWN = {**_D0, "origin": "real_project"}


@pytest.fixture
def db():
    s = SessionLocal()
    if s.get(Workspace, WS) is None:
        s.add(Workspace(id=WS, name="Partner Research Test WS"))
        s.commit()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def web_fake(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "web_research_enabled", True)
    monkeypatch.setattr(s, "web_research_fake_provider", True)
    monkeypatch.setattr(s, "firecrawl_api_key", None)
    return s


def _project(db, classification, *, description="Synthetischer F1-Partner-MVP.") -> Project:
    pid = "ptn-" + uuid.uuid4().hex[:8]
    p = Project(
        project_id=pid, workspace_id=WS, title="F1 Partner (synthetisch)",
        description=description,
        funding_instrument_profile_id=(
            "innosuisse_innovation_project_with_implementation_partner"
        ),
        data_classification=dict(classification), created_by="user-anna", status="draft",
    )
    db.add(p)
    db.commit()
    return db.get(Project, pid)


# --- Planner ------------------------------------------------------------------


def test_planner_produces_five_public_safe_queries():
    queries = plan_partner_queries(TOPIC)
    assert len(queries) == 5
    purposes = {q.purpose for q in queries}
    assert purposes == {
        "university_lab", "research_group", "university_institute",
        "competence_center", "applied_sciences",
    }
    for q in queries:
        assert q.source == "deterministic_planner"
        assert q.public_safe and q.blocked_reason is None
        assert q.approval_required is False


def test_planner_is_deterministic():
    assert plan_partner_queries(TOPIC) == plan_partner_queries(TOPIC)


def test_planner_never_emits_person_partner_budget_or_canary():
    # The planner only reads public MarketTopic-like descriptors — never a person's name,
    # a confidential real partner name, a budget figure, or a canary token.
    joined = " ".join(q.query_text for q in plan_partner_queries(TOPIC))
    assert CANARY not in joined
    assert "CHF" not in joined and "€" not in joined and "$" not in joined
    assert "@" not in joined  # no email-shaped person identifier


# --- Policy (firewall reuse) ----------------------------------------------------


def test_d0_synthetic_allowed(db, web_fake):
    project = _project(db, _D0)
    out = run_partner_research(db, project=project, actor_user_id="user-anna",
                                topic=TOPIC, case_id="F1", data_mode="fake_test")
    assert out.result_count > 0 and out.task_ids


def test_d2_real_project_without_approval_blocked(db, web_fake):
    project = _project(db, _D2)
    with pytest.raises(ResearchBlocked) as exc:
        service.create_partner_research_task(
            db, project=project, query_preview="Swiss applied AI lab manufacturing",
            actor_user_id="user-anna", max_results=3,
        )
    assert exc.value.code == "approval_required"


@pytest.mark.parametrize("classification", [_D3, _UNKNOWN])
def test_d3_and_unknown_blocked(db, web_fake, classification):
    project = _project(db, classification)
    with pytest.raises(ResearchBlocked) as exc:
        service.create_partner_research_task(
            db, project=project, query_preview="Swiss applied AI lab manufacturing",
            actor_user_id="user-anna", max_results=3,
        )
    assert exc.value.code == "web_research_class_blocked"


def test_partner_research_task_subject_type_is_never_person(db, web_fake):
    project = _project(db, _D0)
    task, _op = service.create_partner_research_task(
        db, project=project, query_preview="Swiss applied AI lab manufacturing",
        actor_user_id="user-anna", max_results=3,
    )
    assert task.subject_type == "topic"
    assert task.subject_type != "person"
    assert task.purpose == service.PARTNER_RESEARCH_PURPOSE
    assert task.purpose != "partner_role_suggestion"  # avoids the A1 synthesis collision


# --- Research execution: results + tool metering + cost guard -------------------


def test_fake_provider_creates_results_and_tool_invocations(db, web_fake):
    project = _project(db, _D0)
    out = run_partner_research(db, project=project, actor_user_id="user-anna",
                                topic=TOPIC, case_id="F1", data_mode="fake_test")
    assert out.provider == "fake"
    assert out.result_count == 15  # 5 queries × 3 fake results
    assert out.tool_invocation_count > 0
    persisted = db.scalar(
        select(func.count(ResearchResult.result_id)).where(
            ResearchResult.research_task_id.in_(out.task_ids)
        )
    )
    assert persisted == 15


def test_cost_guard_blocks_partner_task_at_limit(db, web_fake):
    project = _project(db, _D0)
    task_id, op_id = str(uuid.uuid4()), str(uuid.uuid4())
    service.create_partner_research_task(
        db, project=project, query_preview="Swiss applied AI lab manufacturing",
        actor_user_id="user-anna", max_results=3, task_id=task_id, operation_id=op_id,
    )
    for _ in range(5):  # _SEARCH_MAX_CALLS_PER_TASK
        record_tool(db, workspace_id=WS, research_task_id=task_id,
                    tool_id=_SEARCH_TOOL, caller="orchestrator", input_hash="h",
                    output_hash=None, status="succeeded")
    db.commit()
    research_executor(task_id, op_id)
    db.expire_all()
    task = db.get(ResearchTask, task_id)
    assert task.status == "failed" and task.error_code == "cost_guard_blocked"
    assert task.result_count == 0


# --- PartnerCandidate view -------------------------------------------------------


def test_candidate_view_types_and_status():
    results = [
        ResearchResult(result_id="r1", research_task_id="t1", workspace_id=WS,
                       source_url="https://x/1", title="A", snippet="s", provider_rank=1,
                       status="candidate"),
        ResearchResult(result_id="r2", research_task_id="t2", workspace_id=WS,
                       source_url="https://y/2", title="B", snippet="s", provider_rank=2,
                       status="candidate"),
    ]
    cands = to_partner_candidates(
        {"t1": "university_lab", "t2": "competence_center"}, results, topic=TOPIC
    )
    assert cands[0].candidate_type == "university_lab"
    assert cands[1].candidate_type == "competence_center"
    assert all(c.status == "needs_human_review" for c in cands)
    assert all(c.swiss_relevance is None for c in cands)
    assert all(c.country_or_region is None for c in cands)
    assert all(len(c.limitations) > 0 for c in cands)
    # rank-2 with no rank-1 corroborating host anywhere → "low"; a lone rank-1 (no other
    # purpose sharing its host) → "medium", never invented as "high" without corroboration.
    assert cands[0].confidence == "medium"
    assert cands[1].confidence == "low"


def test_candidate_view_high_confidence_requires_cross_purpose_host_corroboration():
    # Same host ranked #1 for two DIFFERENT purposes → "high" (the only path to "high").
    results = [
        ResearchResult(result_id="r1", research_task_id="t1", workspace_id=WS,
                       source_url="https://shared-host.example.org/a", title="A",
                       snippet="s", provider_rank=1, status="candidate"),
        ResearchResult(result_id="r2", research_task_id="t2", workspace_id=WS,
                       source_url="https://shared-host.example.org/b", title="B",
                       snippet="s", provider_rank=1, status="candidate"),
    ]
    cands = to_partner_candidates(
        {"t1": "university_lab", "t2": "research_group"}, results, topic=TOPIC
    )
    assert all(c.confidence == "high" for c in cands)


def test_candidate_expertise_keywords_come_from_topic_not_snippet():
    results = [
        ResearchResult(result_id="r1", research_task_id="t1", workspace_id=WS,
                       source_url="https://x/1", title="A", snippet="unrelated text",
                       provider_rank=1, status="candidate"),
    ]
    cands = to_partner_candidates({"t1": "university_lab"}, results, topic=TOPIC)
    assert cands[0].expertise_keywords == [
        TOPIC.technology_area, TOPIC.application_domain, *TOPIC.competence_areas,
    ]


# --- Invariants: no auto-contact, no auto Partner row, no eligibility claim ------


def test_no_partner_row_auto_created(db, web_fake):
    before = db.scalar(select(func.count(Partner.partner_id)))
    project = _project(db, _D0)
    run_partner_research(db, project=project, actor_user_id="user-anna",
                          topic=TOPIC, case_id="F1", data_mode="fake_test")
    after = db.scalar(select(func.count(Partner.partner_id)))
    assert after == before


def test_report_never_claims_eligibility_or_contact(db, web_fake):
    project = _project(db, _D0)
    out = run_partner_research(db, project=project, actor_user_id="user-anna",
                                topic=TOPIC, case_id="F1", data_mode="fake_test")
    report = render_report(out, generated_at="2026-07-09")
    lowered = report.lower()
    assert "beitragsberechtigt bestätigt" not in lowered
    assert "förderfähig bestätigt" not in lowered
    for forbidden in ("kontaktiert", "e-mail gesendet", "automatisch kontaktiert"):
        assert forbidden not in lowered
    assert all(c.status == "needs_human_review" for c in out.candidates)


# --- No-Raw / canary -------------------------------------------------------------


def test_canary_never_reaches_query_audit_or_report(db, web_fake):
    project = _project(db, _D0, description=f"Vertraulich: {CANARY} darf nie nach aussen.")
    out = run_partner_research(db, project=project, actor_user_id="user-anna",
                                topic=TOPIC, case_id="F1", data_mode="fake_test")
    for q in out.queries:
        assert CANARY not in q.query_text
    for t in out.task_ids:
        task = db.get(ResearchTask, t)
        assert CANARY not in task.query_text
    audits = db.scalars(
        select(AuditEvent).where(AuditEvent.target_id.in_(out.task_ids))
    )
    for a in audits:
        assert CANARY not in str(a.detail or {})
    report = render_report(out, generated_at="2026-07-09")
    assert CANARY not in report
