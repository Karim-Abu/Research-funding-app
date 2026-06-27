"""Reset only manifest-owned deterministic demo objects."""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisRun,
    AsyncOperation,
    AuditEvent,
    ControlResult,
    DemoSeedManifest,
    DraftVersion,
    EvidenceAnchor,
    EvidenceCandidate,
    EvidenceLink,
    OpenIssue,
    Partner,
    PortalFieldDraft,
    Project,
    RequirementAssessment,
    RuleResult,
    RunPolicySnapshot,
    RunProjectSnapshot,
    RunSourceSnapshot,
    SourceDocument,
    SourceFragment,
    SourceVersion,
    UsageRecord,
)
from app.demo.dataset import SEED_VERSION
from app.storage import get_storage


def _ids(rows, object_type: str) -> list[str]:
    return [r.object_id for r in rows if r.object_type == object_type]


def reset_demo_data(db: Session, *, seed_version: str = SEED_VERSION) -> int:
    rows = list(
        db.scalars(
            select(DemoSeedManifest).where(
                DemoSeedManifest.seed_version == seed_version
            )
        )
    )
    if not rows:
        return 0

    project_ids = _ids(rows, "project")
    partner_ids = _ids(rows, "partner")
    source_ids = _ids(rows, "source")
    source_version_ids = _ids(rows, "source_version")
    run_ids = _ids(rows, "run")
    operation_ids = _ids(rows, "operation")

    if project_ids:
        source_ids = sorted(
            set(source_ids)
            | set(
                db.scalars(
                    select(SourceDocument.source_id).where(
                        SourceDocument.project_id.in_(project_ids)
                    )
                )
            )
        )
        run_ids = sorted(
            set(run_ids)
            | set(
                db.scalars(
                    select(AnalysisRun.run_id).where(
                        AnalysisRun.project_id.in_(project_ids)
                    )
                )
            )
        )
    if source_ids:
        source_version_ids = sorted(
            set(source_version_ids)
            | set(
                db.scalars(
                    select(SourceVersion.source_version_id).where(
                        SourceVersion.source_document_id.in_(source_ids)
                    )
                )
            )
        )
    if run_ids:
        operation_ids = sorted(
            set(operation_ids)
            | set(
                db.scalars(
                    select(AsyncOperation.operation_id).where(
                        AsyncOperation.resource_type == "run",
                        AsyncOperation.resource_id.in_(run_ids),
                    )
                )
            )
        )

    draft_ids = (
        list(
            db.scalars(
                select(PortalFieldDraft.draft_id).where(
                    PortalFieldDraft.run_id.in_(run_ids)
                )
            )
        )
        if run_ids
        else []
    )
    derived_ids = set(project_ids) | set(partner_ids) | set(source_ids) | set(source_version_ids)
    derived_ids |= set(run_ids) | set(operation_ids) | set(draft_ids)

    if run_ids:
        db.execute(delete(EvidenceLink).where(EvidenceLink.run_id.in_(run_ids)))
        db.execute(delete(EvidenceAnchor).where(EvidenceAnchor.run_id.in_(run_ids)))
        db.execute(delete(EvidenceCandidate).where(EvidenceCandidate.run_id.in_(run_ids)))
        db.execute(delete(OpenIssue).where(OpenIssue.run_id.in_(run_ids)))
        db.execute(
            delete(RequirementAssessment).where(
                RequirementAssessment.run_id.in_(run_ids)
            )
        )
        db.execute(delete(RuleResult).where(RuleResult.run_id.in_(run_ids)))
        if draft_ids:
            db.execute(delete(DraftVersion).where(DraftVersion.draft_id.in_(draft_ids)))
        db.execute(delete(PortalFieldDraft).where(PortalFieldDraft.run_id.in_(run_ids)))
        db.execute(delete(RunProjectSnapshot).where(RunProjectSnapshot.run_id.in_(run_ids)))
        db.execute(delete(RunPolicySnapshot).where(RunPolicySnapshot.run_id.in_(run_ids)))
        db.execute(delete(RunSourceSnapshot).where(RunSourceSnapshot.run_id.in_(run_ids)))
        db.execute(delete(UsageRecord).where(UsageRecord.run_id.in_(run_ids)))
        db.execute(delete(AnalysisRun).where(AnalysisRun.run_id.in_(run_ids)))

    if operation_ids:
        db.execute(delete(AsyncOperation).where(AsyncOperation.operation_id.in_(operation_ids)))

    if source_version_ids:
        db.execute(
            delete(SourceFragment).where(
                SourceFragment.source_version_id.in_(source_version_ids)
            )
        )
        db.execute(
            delete(SourceVersion).where(
                SourceVersion.source_version_id.in_(source_version_ids)
            )
        )

    if source_ids:
        db.execute(delete(SourceDocument).where(SourceDocument.source_id.in_(source_ids)))

    if project_ids:
        db.execute(delete(Partner).where(Partner.project_id.in_(project_ids)))
        db.execute(delete(ControlResult).where(ControlResult.project_id.in_(project_ids)))
        db.execute(delete(Project).where(Project.project_id.in_(project_ids)))

    if derived_ids:
        db.execute(
            delete(AuditEvent).where(
                AuditEvent.workspace_id.in_({r.workspace_id for r in rows}),
                AuditEvent.target_id.in_(derived_ids),
            )
        )

    storage = get_storage()
    for row in rows:
        if row.storage_ref:
            storage.delete(row.storage_ref)

    db.execute(
        delete(DemoSeedManifest).where(DemoSeedManifest.seed_version == seed_version)
    )
    db.flush()
    return len(rows)
