"""Explicit deterministic demo seed.

Run from backend/: python -m app.demo.seed [--reset]
"""
from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.contracts.run import RunCreate, RunSettings
from app.db.models import (
    AnalysisRun,
    AsyncOperation,
    DemoSeedManifest,
    DraftVersion,
    EvidenceAnchor,
    EvidenceLink,
    Partner,
    PortalFieldDraft,
    Project,
    SourceDocument,
    SourceVersion,
)
from app.db.session import SessionLocal
from app.demo.dataset import (
    DEMO_PROJECTS,
    SEED_VERSION,
    DemoPartner,
    DemoProject,
    DemoSource,
    stable_id,
)
from app.demo.reset import reset_demo_data
from app.fields import service as fields_service
from app.ingestion.pipeline import process_source_version
from app.repositories import audit
from app.repositories import drafts as drafts_repo
from app.repositories import evidence as evidence_repo
from app.repositories import partners as partners_repo
from app.repositories import projects as projects_repo
from app.runs import service as run_service
from app.runs.executor import run_executor
from app.seed import seed as seed_base
from app.sources import service as source_service

logger = logging.getLogger("app.demo.seed")


def _guard(settings) -> None:
    if settings.app_env == "production" or not settings.demo_data_enabled:
        raise RuntimeError(
            "Demo seed is disabled. Set APP_ENV=development|test and "
            "DEMO_DATA_ENABLED=true."
        )


def _manifest(
    db: Session,
    *,
    object_type: str,
    object_id: str,
    workspace_id: str,
    project_id: str | None = None,
    storage_ref: str | None = None,
    label: str | None = None,
) -> None:
    existing = db.scalar(
        select(DemoSeedManifest).where(
            DemoSeedManifest.seed_version == SEED_VERSION,
            DemoSeedManifest.object_type == object_type,
            DemoSeedManifest.object_id == object_id,
        )
    )
    if existing is not None:
        existing.storage_ref = storage_ref or existing.storage_ref
        existing.label = label or existing.label
        db.flush()
        return
    db.add(
        DemoSeedManifest(
            manifest_id=stable_id("manifest", f"{object_type}:{object_id}"),
            seed_version=SEED_VERSION,
            object_type=object_type,
            object_id=object_id,
            workspace_id=workspace_id,
            project_id=project_id,
            storage_ref=storage_ref,
            label=label,
        )
    )
    db.flush()


def _ensure_project(db: Session, demo: DemoProject, settings) -> Project:
    existing = db.get(Project, demo.project_id)
    if existing is not None:
        if existing.title != demo.title:
            raise RuntimeError(f"Demo project id collision: {demo.project_id}")
        _manifest(
            db,
            object_type="project",
            object_id=existing.project_id,
            workspace_id=existing.workspace_id,
            project_id=existing.project_id,
            label=demo.title,
        )
        return existing

    project = projects_repo.create(
        db,
        workspace_id=settings.seed_workspace_id,
        created_by="user-anna",
        data=demo.payload(settings.seed_funding_profile_id),
        project_id=demo.project_id,
    )
    audit.record(
        db,
        workspace_id=project.workspace_id,
        actor_user_id="user-anna",
        action="project.create",
        target_type="project",
        target_id=project.project_id,
        detail={"demo_seed_version": SEED_VERSION},
    )
    _manifest(
        db,
        object_type="project",
        object_id=project.project_id,
        workspace_id=project.workspace_id,
        project_id=project.project_id,
        label=demo.title,
    )
    return project


def _ensure_partner(
    db: Session, project: Project, demo_partner: DemoPartner
) -> Partner:
    existing = db.get(Partner, demo_partner.partner_id)
    if existing is not None:
        _manifest(
            db,
            object_type="partner",
            object_id=existing.partner_id,
            workspace_id=existing.workspace_id,
            project_id=existing.project_id,
            label=existing.name,
        )
        return existing

    partner = partners_repo.create(
        db,
        project_id=project.project_id,
        workspace_id=project.workspace_id,
        created_by="user-anna",
        data=demo_partner.payload,
        partner_id=demo_partner.partner_id,
    )
    audit.record(
        db,
        workspace_id=project.workspace_id,
        actor_user_id="user-anna",
        action="partner.create",
        target_type="partner",
        target_id=partner.partner_id,
        detail={"demo_seed_version": SEED_VERSION},
    )
    _manifest(
        db,
        object_type="partner",
        object_id=partner.partner_id,
        workspace_id=partner.workspace_id,
        project_id=partner.project_id,
        label=partner.name,
    )
    return partner


def _ensure_source(
    db: Session, project: Project, demo_source: DemoSource
) -> SourceDocument:
    existing = db.get(SourceDocument, demo_source.source_id)
    if existing is not None:
        version = db.get(SourceVersion, existing.current_source_version_id)
        if version is not None and version.processing_status != "processed":
            db.commit()
            process_source_version(version.source_version_id)
            db.expire_all()
            existing = db.get(SourceDocument, demo_source.source_id)
            version = db.get(SourceVersion, existing.current_source_version_id)
        _manifest(
            db,
            object_type="source",
            object_id=existing.source_id,
            workspace_id=existing.workspace_id,
            project_id=existing.project_id,
            label=existing.name,
        )
        if version is not None:
            _manifest(
                db,
                object_type="source_version",
                object_id=version.source_version_id,
                workspace_id=existing.workspace_id,
                project_id=existing.project_id,
                storage_ref=version.storage_ref,
                label=existing.name,
            )
        return existing

    doc, version = source_service.prepare_text_source(
        db,
        project=project,
        payload=demo_source.payload(),
        actor_user_id="user-anna",
        source_id=demo_source.source_id,
        source_version_id=demo_source.source_version_id,
    )
    _manifest(
        db,
        object_type="source",
        object_id=doc.source_id,
        workspace_id=doc.workspace_id,
        project_id=doc.project_id,
        label=doc.name,
    )
    _manifest(
        db,
        object_type="source_version",
        object_id=version.source_version_id,
        workspace_id=doc.workspace_id,
        project_id=doc.project_id,
        storage_ref=version.storage_ref,
        label=doc.name,
    )
    db.commit()
    process_source_version(version.source_version_id)
    db.expire_all()
    return db.get(SourceDocument, doc.source_id)


def _ensure_run(db: Session, project: Project, demo: DemoProject, settings) -> AnalysisRun:
    existing = db.get(AnalysisRun, demo.run_id)
    if existing is not None:
        if existing.status != "completed":
            operation = db.get(AsyncOperation, demo.operation_id)
            if operation is not None and operation.status in {"queued", "running"}:
                db.commit()
                run_executor(existing.run_id, operation.operation_id)
                db.expire_all()
                existing = db.get(AnalysisRun, demo.run_id)
        if existing.status != "completed":
            raise RuntimeError(
                f"Demo run {demo.run_id} is {existing.status}; use --reset."
            )
        _manifest(
            db,
            object_type="run",
            object_id=existing.run_id,
            workspace_id=existing.workspace_id,
            project_id=existing.project_id,
            label=demo.title,
        )
        _manifest(
            db,
            object_type="operation",
            object_id=demo.operation_id,
            workspace_id=existing.workspace_id,
            project_id=existing.project_id,
            label=demo.title,
        )
        return existing

    payload = RunCreate(
        settings=RunSettings(
            processing_mode="deterministic_only",
            max_cost_chf=0,
            max_llm_calls=0,
            max_web_calls=0,
            source_version_ids=None,
            internal_cloud_confirmation_id=None,
        )
    )
    _run, _op, accepted = run_service.prepare_run(
        db,
        project=project,
        payload=payload,
        actor_user_id="user-anna",
        settings=settings,
        idempotency_key=stable_id("idempotency", f"run:{demo.key}"),
        correlation_id=stable_id("correlation", f"run:{demo.key}"),
        run_id=demo.run_id,
        operation_id=demo.operation_id,
    )
    _manifest(
        db,
        object_type="run",
        object_id=accepted.resource_id,
        workspace_id=project.workspace_id,
        project_id=project.project_id,
        label=demo.title,
    )
    _manifest(
        db,
        object_type="operation",
        object_id=accepted.operation_id,
        workspace_id=project.workspace_id,
        project_id=project.project_id,
        label=demo.title,
    )
    db.commit()
    run_executor(accepted.resource_id, accepted.operation_id)
    db.expire_all()
    run = db.get(AnalysisRun, accepted.resource_id)
    if run is None or run.status != "completed":
        raise RuntimeError(f"Demo run did not complete: {accepted.resource_id}")
    return run


def _current_version(db: Session, draft: PortalFieldDraft) -> DraftVersion:
    version = db.get(DraftVersion, draft.current_version_id)
    if version is None:
        raise RuntimeError(f"Draft has no current version: {draft.field_id}")
    return version


def _apply_draft_edits(db: Session, run: AnalysisRun, demo: DemoProject) -> None:
    for field_id, text in demo.draft_edits.items():
        draft = drafts_repo.get_draft(db, run.run_id, field_id)
        if draft is None:
            raise RuntimeError(f"Missing draft field {field_id}.")
        current = _current_version(db, draft)
        if current.text == text and current.created_by == "user":
            continue
        drafts_repo.apply_update(
            db,
            run,
            draft,
            base_version_id=current.draft_version_id,
            text=text,
            source_operation_id=None,
            actor_user_id="user-anna",
        )
    db.commit()


def _apply_evidence_links(db: Session, run: AnalysisRun, demo: DemoProject) -> None:
    if not demo.link_fields:
        return
    anchors = list(
        db.scalars(
            select(EvidenceAnchor)
            .where(
                EvidenceAnchor.run_id == run.run_id,
                EvidenceAnchor.verification_status == "exact_verified",
            )
            .order_by(EvidenceAnchor.created_at.asc(), EvidenceAnchor.anchor_id.asc())
        )
    )
    if not anchors:
        raise RuntimeError(f"No verified evidence anchors for {demo.title}.")
    for index, field_id in enumerate(demo.link_fields):
        draft = drafts_repo.get_draft(db, run.run_id, field_id)
        if draft is None:
            raise RuntimeError(f"Missing draft field {field_id}.")
        current = _current_version(db, draft)
        existing = db.scalar(
            select(EvidenceLink).where(
                EvidenceLink.run_id == run.run_id,
                EvidenceLink.target_type == "draft_version",
                EvidenceLink.target_id == current.draft_version_id,
                EvidenceLink.status == "active",
            )
        )
        if existing is not None:
            continue
        fields_service.create_draft_evidence_link(
            db,
            run=run,
            draft=draft,
            anchor_id=anchors[index % len(anchors)].anchor_id,
            base_version_id=current.draft_version_id,
            actor_user_id="user-anna",
        )
    db.commit()


def _verify_project_presence(db: Session, settings) -> None:
    demo_project_ids = [demo.project_id for demo in DEMO_PROJECTS]
    demo_count = db.scalar(
        select(func.count(Project.project_id)).where(
            Project.project_id.in_(demo_project_ids)
        )
    ) or 0
    if demo_count != len(DEMO_PROJECTS):
        raise RuntimeError("Demo seed incomplete: expected both demo projects.")
    if settings.app_env == "test":
        total_count = db.scalar(select(func.count(Project.project_id))) or 0
        if total_count != len(DEMO_PROJECTS):
            raise RuntimeError(
                "Isolated test demo seed expected exactly two projects."
            )


def seed_demo_data(*, reset: bool = False) -> None:
    settings = get_settings()
    _guard(settings)
    seed_base()

    db = SessionLocal()
    try:
        if reset:
            reset_demo_data(db)
            db.commit()
        for demo in DEMO_PROJECTS:
            project = _ensure_project(db, demo, settings)
            for partner in demo.partners:
                _ensure_partner(db, project, partner)
            db.commit()
            for source in demo.sources:
                _ensure_source(db, project, source)
            run = _ensure_run(db, project, demo, settings)
            if demo.draft_edits:
                _apply_draft_edits(db, run, demo)
                db.expire_all()
                run = db.get(AnalysisRun, demo.run_id)
                _apply_evidence_links(db, run, demo)
        _verify_project_presence(db, settings)
        db.commit()
        logger.info("demo seed complete version=%s projects=%d", SEED_VERSION, len(DEMO_PROJECTS))
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args(argv)
    configure_logging(get_settings().log_level)
    try:
        seed_demo_data(reset=args.reset)
    except Exception as exc:  # noqa: BLE001
        logger.error("demo seed failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
