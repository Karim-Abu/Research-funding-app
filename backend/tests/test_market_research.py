"""RESEARCH.1a — Market Research MVP (Backend + Report), fake provider only.

No network: the FakeWebProvider drives everything (``web_research_fake_provider=True``).
Covers the deterministic planner, the firewall-reuse policy (D0 allowed; D2 without
approval and D3/UNKNOWN blocked), ResearchResult + ToolInvocation creation, the CostGuard
limit, the MarketCandidate view (candidate_type/confidence, HITL, snippet ≠ evidence), and
the no-raw/canary property (a confidential marker never reaches query/audit/report).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.config.settings import get_settings
from app.db.models import (
    AuditEvent,
    EvidenceAnchor,
    Project,
    ResearchResult,
    ResearchTask,
    ToolInvocation,
    Workspace,
)
from app.db.session import SessionLocal
from app.market_research.candidates import to_market_candidates
from app.market_research.planner import MarketTopic, plan_market_queries
from app.market_research.report import render_report
from app.market_research.runner import run_market_research
from app.research import service
from app.research.executor import _SEARCH_TOOL, research_executor
from app.research.recording import record_tool
from app.research.service import ResearchBlocked

TOPIC = MarketTopic(
    application_domain="manufacturing quality assurance",
    technology_area="industrial AI anomaly detection",
    target_customers="manufacturing SMEs",
    region="Switzerland",
)
CANARY = "PROJECT_SECRET_MARKER_R5_INJECTION"
# Dedicated workspace so committed synthetic projects (incl. D2/D3/UNKNOWN classes) never
# pollute ws-demo listings that other suites validate against the public contract.
WS = "ws-market-research"

_D0 = {"sensitivity": "public", "origin": "synthetic",
       "processing_mode": "cloud_assisted", "web_research_mode": "validated_public",
       "nda_applies": False}
_D2 = {"sensitivity": "confidential", "origin": "real_project",
       "processing_mode": "cloud_assisted", "web_research_mode": "validated_public",
       "nda_applies": False}
_D3 = {**_D0, "nda_applies": True}
_UNKNOWN = {**_D0, "sensitivity": "restricted"}


@pytest.fixture
def db():
    s = SessionLocal()
    if s.get(Workspace, WS) is None:
        s.add(Workspace(id=WS, name="Market Research Test WS"))
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


def _project(db, classification, *, description="Synthetischer F1-MVP.") -> Project:
    pid = "mkt-" + uuid.uuid4().hex[:8]
    p = Project(
        project_id=pid, workspace_id=WS, title="F1 Market (synthetisch)",
        description=description,
        funding_instrument_profile_id=(
            "innosuisse_innovation_project_with_implementation_partner"
        ),
        data_classification=dict(classification), created_by="user-anna", status="draft",
    )
    db.add(p)
    db.commit()
    return db.get(Project, pid)


# --- Planner ----------------------------------------------------------------


def test_planner_produces_three_precise_public_safe_queries():
    queries = plan_market_queries(TOPIC)
    assert len(queries) == 3
    purposes = {q.purpose for q in queries}
    assert purposes == {
        "market_size", "competitors_alternatives", "regulatory_demand_drivers",
    }
    for q in queries:
        assert q.source == "deterministic_planner"
        assert q.public_safe and q.blocked_reason is None
        # R8 Freigabepflicht: jede Planner-Query braucht eine menschliche Freigabe.
        assert q.approval_required is True


def test_planner_queries_do_not_repeat_terms():
    repeated = MarketTopic(
        application_domain="Medizintechnik",
        technology_area="Medizintechnik Audit",
        target_customers="Medizintechnik Labore",
        region="Schweiz",
    )
    for query in plan_market_queries(repeated, include_state_of_the_art=True):
        words = [
            word.strip(".,;:!?()[]{}\"'").casefold()
            for word in query.query_text.split()
        ]
        assert len(words) == len(set(words)), query.query_text


def test_planner_is_deterministic():
    assert plan_market_queries(TOPIC) == plan_market_queries(TOPIC)


def test_planner_never_emits_partner_budget_or_canary():
    # A canary / partner / budget in a *non-topic* field must never surface: the planner
    # only reads the public MarketTopic descriptors, never confidential project text.
    joined = " ".join(q.query_text for q in plan_market_queries(TOPIC))
    assert CANARY not in joined
    assert "CHF" not in joined and "€" not in joined and "$" not in joined


# --- Policy (firewall reuse) ------------------------------------------------


def test_d0_synthetic_allowed(db, web_fake):
    project = _project(db, _D0)
    out = run_market_research(db, project=project, actor_user_id="user-anna",
                              topic=TOPIC, case_id="F1", data_mode="fake_test")
    assert out.result_count > 0 and out.task_ids


def test_d2_real_project_without_approval_blocked(db, web_fake):
    project = _project(db, _D2)
    with pytest.raises(ResearchBlocked) as exc:
        service.create_market_research_task(
            db, project=project, query_preview="manufacturing market size",
            actor_user_id="user-anna", max_results=3,
        )
    assert exc.value.code == "approval_required"


@pytest.mark.parametrize("classification", [_D3, _UNKNOWN])
def test_d3_and_unknown_blocked(db, web_fake, classification):
    project = _project(db, classification)
    with pytest.raises(ResearchBlocked) as exc:
        service.create_market_research_task(
            db, project=project, query_preview="manufacturing market size",
            actor_user_id="user-anna", max_results=3,
        )
    assert exc.value.code == "web_research_class_blocked"


# --- Research execution: results + tool metering + cost guard ---------------


def test_fake_provider_creates_results_and_tool_invocations(db, web_fake):
    project = _project(db, _D0)
    out = run_market_research(db, project=project, actor_user_id="user-anna",
                              topic=TOPIC, case_id="F1", data_mode="fake_test")
    assert out.provider == "fake"
    assert out.result_count == 9  # 3 queries × 3 fake results
    assert out.tool_invocation_count > 0
    persisted = db.scalar(
        select(func.count(ResearchResult.result_id)).where(
            ResearchResult.research_task_id.in_(out.task_ids)
        )
    )
    assert persisted == 9


def test_cost_guard_blocks_market_task_at_limit(db, web_fake):
    project = _project(db, _D0)
    task_id, op_id = str(uuid.uuid4()), str(uuid.uuid4())
    service.create_market_research_task(
        db, project=project, query_preview="manufacturing market size",
        actor_user_id="user-anna", max_results=3, task_id=task_id, operation_id=op_id,
    )
    # Pre-seed the per-task search-tool budget so the guard blocks before any provider call.
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


# --- MarketCandidate view ---------------------------------------------------


def test_candidate_view_types_confidence_and_hitl():
    results = [
        ResearchResult(result_id="r1", research_task_id="t1", workspace_id=WS,
                       source_url="https://x/1", title="A", snippet="s", provider_rank=1,
                       status="candidate"),
        ResearchResult(result_id="r2", research_task_id="t1", workspace_id=WS,
                       source_url="https://x/2", title="B", snippet="s", provider_rank=2,
                       status="candidate"),
    ]
    cands = to_market_candidates({"t1": "market_size"}, results)
    assert cands[0].candidate_type == "market_size_candidate"
    assert cands[0].confidence == "medium" and cands[1].confidence == "low"
    assert all(c.confidence in ("low", "medium") for c in cands)  # never "high" in MVP
    assert all(c.human_review_required is True for c in cands)


def test_snippet_creates_no_evidence_anchor(db, web_fake):
    project = _project(db, _D0)
    run_market_research(db, project=project, actor_user_id="user-anna",
                        topic=TOPIC, case_id="F1", data_mode="fake_test")
    db.expire_all()
    # Scope to this suite's workspace — other suites legitimately create anchors.
    assert db.scalar(
        select(func.count(EvidenceAnchor.anchor_id)).where(
            EvidenceAnchor.workspace_id == WS
        )
    ) == 0


# --- No-Raw / canary --------------------------------------------------------


def test_canary_never_reaches_query_audit_or_report(db, web_fake):
    # R8-Leakage: Rohidee-Satz, Canary, projektspezifischer Technikbegriff,
    # zusammengesetzter Partnername und Budget (Zahlwörter) leben NUR in der
    # Beschreibung; Planner/Runner dürfen nichts davon in Query, Task-Text,
    # Audit-Event oder Report ziehen (der Planner liest strukturell nur den Topic).
    markers = [CANARY, "QuantumFoam", "Acme-Robotics", "halbe Million Franken"]
    raw_idea = (
        f"Rohidee: {CANARY}. Unser QuantumFoam-Aktuator mit Acme-Robotics kostet "
        "eine halbe Million Franken und darf nie nach aussen."
    )
    project = _project(db, _D0, description=raw_idea)
    out = run_market_research(db, project=project, actor_user_id="user-anna",
                              topic=TOPIC, case_id="F1", data_mode="fake_test")
    for q in out.queries:
        for m in markers:
            assert m not in q.query_text
    for t in out.task_ids:
        task = db.get(ResearchTask, t)
        for m in markers:
            assert m not in task.query_text
    audits = db.scalars(
        select(AuditEvent).where(AuditEvent.target_id.in_(out.task_ids))
    )
    for a in audits:
        blob = str(a.detail or {})
        for m in markers:
            assert m not in blob
    report = render_report(out, generated_at="2026-07-09")
    for m in markers:
        assert m not in report
