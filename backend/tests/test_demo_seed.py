"""Deterministic demo seed: guards, ownership, artifacts, reset, summaries."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

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
from app.db.session import SessionLocal
from app.demo.dataset import DEMO_CLASSIFICATION, DEMO_PROJECTS, PROJECT_A, PROJECT_B
from app.demo.reset import reset_demo_data
from app.demo.seed import _verify_project_presence, seed_demo_data
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


def test_isolated_test_db_requires_exactly_two_demo_projects(demo_seed_env):
    db = SessionLocal()
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
        for demo in (PROJECT_A, PROJECT_B):
            project = db.get(Project, demo.project_id)
            if project is not None:
                db.delete(project)
        extra = db.get(Project, "extra-project")
        if extra is not None:
            db.delete(extra)
        db.commit()
        db.close()


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
