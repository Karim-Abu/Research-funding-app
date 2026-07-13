"""Run creation service shared by HTTP API and explicit demo seeds."""
from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.config.settings import Settings
from app.contracts.run import AsyncAccepted, RunCreate
from app.db.models import AnalysisRun, AsyncOperation, UsageRecord
from app.db.models import SourceVersion
from app.policy.classification import resolve_effective_classification
from app.registry import get_registry
from app.repositories import audit, controls
from app.repositories import processing_confirmations as confirmations_repo
from app.repositories import runs as runs_repo
from app.runs import cloud_policy, project_snapshot
from app.runs import snapshot as snapshot_service
from app.runs.constants import SNAPSHOT_VERSIONS
from app.runs.policy import POLICY_VERSION, build_policy_snapshot

RUN_CONTROLS = (
    "run.authorization",
    "run.source_snapshot",
    "run.classification",
    "run.policy",
    "run.one_active_run",
    "run.operation_state",
)


def _assert_non_relaxing_classification(
    *, project_classification: dict, source_classifications: list[dict | None], effective: dict
) -> None:
    """Fail closed if the existing resolver ever relaxes sensitivity or NDA."""
    for classification in [project_classification, *source_classifications]:
        checked, _ = resolve_effective_classification(
            classification or {}, effective)
        if (
            checked.get("sensitivity") != effective.get("sensitivity")
            or bool(checked.get("nda_applies")) != bool(effective.get("nda_applies"))
        ):
            raise ProblemException(
                status=500,
                code="classification_merge_invariant",
                title="Classification merge invariant failed",
                detail="The run classification could not be resolved safely.",
            )


def _effective_run_classification(project_classification: dict, versions: list[SourceVersion]) -> dict:
    effective = dict(project_classification or {})
    for version in versions:
        effective, _ = resolve_effective_classification(
            effective, version.data_classification or None
        )
    _assert_non_relaxing_classification(
        project_classification=project_classification,
        source_classifications=[
            version.data_classification for version in versions],
        effective=effective,
    )
    return effective


def prepare_run(
    db: Session,
    *,
    project,
    payload: RunCreate,
    actor_user_id: str,
    settings: Settings,
    idempotency_key: str | None = None,
    correlation_id: str | None = None,
    run_id: str | None = None,
    operation_id: str | None = None,
) -> tuple[AnalysisRun, AsyncOperation, AsyncAccepted]:
    """Create a queued run and operation using the canonical run path.

    Caller owns idempotency records, commit, and execution/background dispatch.
    """

    # Intake-only-Läufe sind zulässig, wenn eine strukturierte
    # Projektbeschreibung existiert — sie ist der versionierte Input
    # (eingefroren im RunProjectSnapshot). Ohne Beschreibung UND ohne
    # verarbeitete Quelle bleibt der Lauf fail-closed (422 no_valid_sources).
    allow_intake_only = bool((project.description or "").strip())

    versions: list[SourceVersion] | None = None
    effective_classification = project.data_classification
    if settings.run_classification_source_merge_enabled:
        versions = snapshot_service.build_source_snapshot(
            db,
            project_id=project.project_id,
            workspace_id=project.workspace_id,
            requested_version_ids=payload.settings.source_version_ids,
            allow_empty=allow_intake_only,
        )
        effective_classification = _effective_run_classification(
            project.data_classification, versions
        )

    # M9D.2 cloud-processing gate: non-cloud modes pass through; cloud_assisted is
    # allowed only for eligible (public/synthetic) projects with a valid one-run
    # confirmation. Blocks persist their own ControlResult + AuditEvent.
    cloud_decision = cloud_policy.validate_cloud_run(
        db, project, payload.settings, actor_user_id=actor_user_id,
        requested_source_version_ids=payload.settings.source_version_ids or [],
        policy_version=POLICY_VERSION,
        effective_classification=(
            effective_classification if settings.run_classification_source_merge_enabled else None
        ),
    )
    registry = get_registry()

    if runs_repo.active_run(db, project.project_id) is not None:
        raise ProblemException(
            status=409,
            code="active_run_exists",
            title="Conflict",
            detail="A run is already active for this project.",
        )

    if versions is None:
        versions = snapshot_service.build_source_snapshot(
            db,
            project_id=project.project_id,
            workspace_id=project.workspace_id,
            requested_version_ids=payload.settings.source_version_ids,
            allow_empty=allow_intake_only,
        )

    actual_run_id = run_id or str(uuid.uuid4())
    run = AnalysisRun(
        run_id=actual_run_id,
        project_id=project.project_id,
        workspace_id=project.workspace_id,
        created_by=actor_user_id,
        status="created",
        current_stage="initialize",
        progress_percent=0,
        processing_mode=payload.settings.processing_mode,
        effective_data_classification=effective_classification,
        snapshot_versions={
            **SNAPSHOT_VERSIONS,
            "source_version_ids": [v.source_version_id for v in versions],
            "requirement_registry_version": registry.requirement_registry_version,
            "rule_registry_version": registry.rule_registry_version,
        },
        recheck_required=False,
        semantic_findings_stale=False,
    )
    db.add(run)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ProblemException(
            status=409,
            code="active_run_exists",
            title="Conflict",
            detail="A run is already active for this project.",
        ) from exc

    snapshot_service.persist_snapshot(db, actual_run_id, versions)
    project_snapshot.build_and_persist(
        db, run_id=actual_run_id, project=project, registry=registry
    )
    db.add(build_policy_snapshot(actual_run_id,
           payload.settings, settings, cloud_decision))
    if cloud_decision.confirmation is not None:
        # Consume the one-run confirmation now that the cloud run is committed.
        confirmations_repo.mark_used(
            db, cloud_decision.confirmation, actual_run_id)
    db.add(
        UsageRecord(
            usage_record_id=str(uuid.uuid4()),
            run_id=actual_run_id,
            workspace_id=project.workspace_id,
            # Technischer Seed-Row ohne externen Call (EVAL.1): explizit
            # not_applicable, damit Runs nicht dauerhaft "unknown cost" tragen.
            cost_status="not_applicable",
        )
    )

    actual_operation_id = operation_id or str(uuid.uuid4())
    operation = AsyncOperation(
        operation_id=actual_operation_id,
        workspace_id=project.workspace_id,
        project_id=project.project_id,
        resource_type="run",
        resource_id=actual_run_id,
        status="queued",
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )
    db.add(operation)

    for control_id in RUN_CONTROLS:
        controls.record(
            db,
            workspace_id=project.workspace_id,
            project_id=project.project_id,
            source_id=None,
            control_id=control_id,
            status="passed",
        )
    for action in ("run.requested", "source_snapshot.frozen", "operation.queued"):
        audit.record(
            db,
            workspace_id=project.workspace_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type="run",
            target_id=actual_run_id,
        )

    accepted = AsyncAccepted(
        operation_id=actual_operation_id,
        resource_type="run",
        resource_id=actual_run_id,
        status="queued",
        poll_url=f"/api/v1/operations/{actual_operation_id}",
    )
    return run, operation, accepted
