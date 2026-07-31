"""Deterministic demo seed: guards, ownership, artifacts, reset, summaries."""
from __future__ import annotations

import socket
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import app.demo.seed as seed_mod
from app.config.settings import get_settings
from app.db.models import (
    AnalysisRun,
    DemoSeedManifest,
    DraftVersion,
    EvidenceLink,
    OpenIssue,
    PortalFieldDraft,
    Project,
    RequirementAssessment,
    RuleResult,
    SourceDocument,
)
from app.db.base import Base
from app.db.session import SessionLocal
from app.demo.dataset import DEMO_CLASSIFICATION, DEMO_PROJECTS, PROJECT_A, PROJECT_B
from app.demo.reset import reset_demo_data
from app.demo.seed import _verify_project_presence, seed_demo_data
from app.registry import get_registry
from app.repositories import drafts as drafts_repo
from app.workflow_summary import WORKFLOW_SUMMARY_VERSION
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, create_project, login


@pytest.fixture
def demo_seed_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DEMO_DATA_ENABLED", "true")
    get_settings.cache_clear()
    db = SessionLocal()
    try:
        reset_demo_data(db)
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        reset_demo_data(db)
        db.commit()
    finally:
        db.close()
        get_settings.cache_clear()


def _seeded_projects(db):
    return {
        project.project_id: project
        for project in db.scalars(
            select(Project).where(
                Project.project_id.in_([demo.project_id for demo in DEMO_PROJECTS])
            )
        )
    }


def test_demo_seed_fails_closed_without_enablement(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_DATA_ENABLED", "true")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="Demo seed is disabled"):
        seed_demo_data()
    get_settings.cache_clear()


def test_production_guard_creates_nothing(monkeypatch):
    """The production guard must abort before any DB row, manifest entry or file."""
    db = SessionLocal()
    try:
        reset_demo_data(db)
        db.commit()
        before_projects = db.scalar(select(func.count(Project.project_id)))
        before_manifest = db.scalar(select(func.count(DemoSeedManifest.manifest_id)))
    finally:
        db.close()

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_DATA_ENABLED", "true")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="disabled"):
        seed_demo_data()
    get_settings.cache_clear()

    db = SessionLocal()
    try:
        assert db.scalar(select(func.count(Project.project_id))) == before_projects
        assert db.scalar(select(func.count(DemoSeedManifest.manifest_id))) == before_manifest
        for demo in DEMO_PROJECTS:
            assert db.get(Project, demo.project_id) is None
    finally:
        db.close()


def test_no_network_during_seed(demo_seed_env, monkeypatch):
    """A full seed must succeed with all sockets blocked — proving no provider,
    OpenAI, Anthropic, Firecrawl or arbitrary HTTP call occurs."""
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network access attempted during demo seed")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)

    seed_demo_data(reset=True)

    db = SessionLocal()
    try:
        for demo in DEMO_PROJECTS:
            run = db.get(AnalysisRun, demo.run_id)
            assert run is not None and run.status == "completed"
    finally:
        db.close()


def test_partial_failure_leaves_no_ready_dashboard(client, demo_seed_env, monkeypatch):
    """If a run fails mid-seed, the aborted project must not appear ready."""
    real_executor = seed_mod.run_executor
    calls = {"n": 0}

    def _flaky(run_id: str, operation_id: str) -> None:
        calls["n"] += 1
        if calls["n"] >= 2:  # project A completes, project B's run fails
            raise RuntimeError("forced demo run failure")
        return real_executor(run_id, operation_id)

    monkeypatch.setattr(seed_mod, "run_executor", _flaky)
    with pytest.raises(Exception):
        seed_demo_data(reset=True)

    db = SessionLocal()
    try:
        run_a = db.get(AnalysisRun, PROJECT_A.run_id)
        run_b = db.get(AnalysisRun, PROJECT_B.run_id)
        assert run_a is not None and run_a.status == "completed"
        assert run_b is None or run_b.status != "completed"
    finally:
        db.close()

    # The aborted project never surfaces a draft-ready dashboard state.
    login(client, ANNA_EMAIL, ANNA_PASSWORD)
    items = {p["project_id"]: p for p in client.get("/api/v1/projects").json()["items"]}
    if PROJECT_B.project_id in items:
        assert items[PROJECT_B.project_id]["workflow_summary"]["next_action"] != "continue_draft"


def test_capabilities_unchanged_after_seed(client, demo_seed_env):
    seed_demo_data(reset=True)
    login(client, ANNA_EMAIL, ANNA_PASSWORD)
    features = client.get("/api/v1/capabilities").json()["features"]
    assert features["review"] is True  # Milestone 7 enables deterministic review
    assert features["export"] is True  # Milestone 8 enables deterministic export
    assert features["web_research"] is False
    # No AI/cloud capability is advertised; deterministic slices stay on.
    assert "cloud_assisted" not in features
    assert features.get("drafts") is True


def test_seeded_edits_satisfy_user_action_invariants(demo_seed_env):
    """Seeded edits/links go through the same service path as user actions."""
    seed_demo_data(reset=True)
    registry = get_registry()
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, PROJECT_A.run_id)
        assert run.recheck_required is True  # edits/links set the recheck flag

        for draft in db.scalars(
            select(PortalFieldDraft).where(PortalFieldDraft.run_id == PROJECT_A.run_id)
        ):
            current = db.get(DraftVersion, draft.current_version_id)
            assert current.created_by in ("template", "user")  # never agent
            limit = registry.portal_fields[draft.field_id].character_limit
            if limit is not None:
                assert len(current.text) <= limit  # char-limit respected

        for field_id in PROJECT_A.draft_edits:
            draft = drafts_repo.get_draft(db, run.run_id, field_id)
            versions = list(
                db.scalars(
                    select(DraftVersion)
                    .where(DraftVersion.draft_id == draft.draft_id)
                    .order_by(DraftVersion.created_at.asc())
                )
            )
            assert versions[0].created_by == "template"  # immutable initial version
            assert versions[-1].created_by == "user"
            assert versions[-1].base_version_id is not None  # base chaining
    finally:
        db.close()


def test_isolated_test_db_requires_exactly_two_demo_projects(tmp_path):
    # 2026-07-26: _verify_project_presence zaehlt unter APP_ENV=test ALLE
    # Project-Zeilen. conftest bindet aber EINE sessionweite SQLite-DB, in der
    # vorher laufende Tests eigene Projekte committen (z. B. test_costs_api).
    # reset_demo_data raeumt nur manifest-eigene Zeilen ab, nie fremde — der
    # Test bestand deshalb nur, wenn er frueh genug lief.
    # Die Produktregel «genau zwei» bleibt unveraendert scharf; isoliert wird
    # die Umgebung, so wie der Testname es ohnehin behauptet.
    engine = create_engine(f"sqlite:///{tmp_path / 'isolated.db'}")
    Base.metadata.create_all(engine)
    db = Session(engine)
    try:
        for demo in DEMO_PROJECTS:
            db.add(
                Project(
                    project_id=demo.project_id,
                    workspace_id="ws-demo",
                    title=demo.title,
                    description="Demo",
                    funding_instrument_profile_id=(
                        "innosuisse_innovation_project_with_implementation_partner"
                    ),
                    data_classification=DEMO_CLASSIFICATION.model_dump(),
                    created_by="user-anna",
                    status="draft",
                )
            )
        db.commit()
        _verify_project_presence(db, SimpleNamespace(app_env="test"))
        db.add(
            Project(
                project_id="extra-project",
                workspace_id="ws-demo",
                title="Extra",
                description="Extra",
                funding_instrument_profile_id=(
                    "innosuisse_innovation_project_with_implementation_partner"
                ),
                data_classification=DEMO_CLASSIFICATION.model_dump(),
                created_by="user-anna",
                status="draft",
            )
        )
        db.commit()
        with pytest.raises(RuntimeError, match="exactly two projects"):
            _verify_project_presence(db, SimpleNamespace(app_env="test"))
    finally:
        db.rollback()
        db.close()
        engine.dispose()


def test_seed_generates_real_artifacts_and_reset_preserves_dev_projects(
    client, demo_seed_env
):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    non_demo_id = create_project(client, csrf, "Bestehendes Dev-Projekt")

    seed_demo_data(reset=True)
    db = SessionLocal()
    try:
        first_manifest_count = db.scalar(
            select(func.count(DemoSeedManifest.manifest_id))
        )
    finally:
        db.close()
    seed_demo_data(reset=False)

    db = SessionLocal()
    try:
        projects = _seeded_projects(db)
        assert set(projects) == {PROJECT_A.project_id, PROJECT_B.project_id}
        assert db.get(Project, non_demo_id) is not None

        manifest_count = db.scalar(select(func.count(DemoSeedManifest.manifest_id)))
        assert manifest_count and manifest_count > 0
        assert manifest_count == first_manifest_count

        for project in projects.values():
            assert project.data_classification == DEMO_CLASSIFICATION.model_dump()
            sources = list(
                db.scalars(
                    select(SourceDocument).where(
                        SourceDocument.project_id == project.project_id
                    )
                )
            )
            assert sources
            assert {source.status for source in sources} == {"processed"}

        for demo in DEMO_PROJECTS:
            run = db.get(AnalysisRun, demo.run_id)
            assert run is not None
            assert run.status == "completed"
            assert db.scalar(
                select(func.count(RuleResult.rule_result_id)).where(
                    RuleResult.run_id == demo.run_id
                )
            ) == 12
            assert db.scalar(
                select(func.count(RequirementAssessment.assessment_id)).where(
                    RequirementAssessment.run_id == demo.run_id
                )
            )

        user_versions = list(
            db.scalars(
                select(DraftVersion)
                .join(PortalFieldDraft, DraftVersion.draft_id == PortalFieldDraft.draft_id)
                .where(
                    PortalFieldDraft.run_id == PROJECT_A.run_id,
                    DraftVersion.created_by == "user",
                )
            )
        )
        assert len(user_versions) >= 2
        current_user_version_ids = {version.draft_version_id for version in user_versions}
        active_links = list(
            db.scalars(
                select(EvidenceLink).where(
                    EvidenceLink.run_id == PROJECT_A.run_id,
                    EvidenceLink.status == "active",
                    EvidenceLink.target_id.in_(current_user_version_ids),
                )
            )
        )
        assert len(active_links) >= 2

        project_b_blockers = list(
            db.scalars(
                select(OpenIssue).where(
                    OpenIssue.run_id == PROJECT_B.run_id,
                    OpenIssue.status == "open",
                    OpenIssue.severity == "blocker",
                )
            )
        )
        assert any(
            issue.target_id == "REQ.INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE"
            for issue in project_b_blockers
        )
    finally:
        db.close()

    listing = client.get("/api/v1/projects")
    assert listing.status_code == 200, listing.text
    items = {item["project_id"]: item for item in listing.json()["items"]}
    assert items[PROJECT_A.project_id]["workflow_summary"]["next_action"] == "continue_draft"
    assert items[PROJECT_A.project_id]["workflow_summary"]["current_step"] == 5
    assert items[PROJECT_B.project_id]["workflow_summary"]["next_action"] == "review_analysis"
    assert items[PROJECT_B.project_id]["workflow_summary"]["current_step"] == 3
    assert WORKFLOW_SUMMARY_VERSION == "workflow-summary-v1"

    db = SessionLocal()
    try:
        reset_demo_data(db)
        db.commit()
        assert db.get(Project, PROJECT_A.project_id) is None
        assert db.get(Project, PROJECT_B.project_id) is None
        assert db.get(Project, non_demo_id) is not None
    finally:
        db.close()
