"""Cloud-processing gate (Milestone 9D.2).

Decides whether a `cloud_assisted` run may be created. Allowed ONLY for
public/synthetic projects with a valid one-run processing confirmation; internal/
confidential/NDA/missing-classification stay blocked. Every allow/block records a
ControlResult + AuditEvent. Never silently up/down-grades the processing mode.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.agents.registry import get_agent_registry
from app.api.errors import ProblemException
from app.contracts.run import RunSettings
from app.db.models import ProcessingConfirmation, Project
from app.repositories import audit, controls
from app.repositories import processing_confirmations as confirmations_repo

CONFIRMATION_TEXT_VERSION = "cloud-confirm-v1"
A2_PROFILE_ID = "A2.solution_innovation"
_ALLOWED_ORIGINS = ("synthetic", "public_source")
_NO_EXTERNAL_CALL_MODES = ("deterministic_only", "local_only")


@dataclass(frozen=True)
class CloudDecision:
    confirmation: ProcessingConfirmation | None = None
    provider_route_class: str | None = None


def provider_route_class() -> str:
    """The active provider route class for the A2 primary model (public beta)."""
    registry = get_agent_registry()
    profile = registry.profile(A2_PROFILE_ID)
    return registry.route(profile.primary_model).provider


def classification_eligible(classification: dict) -> tuple[bool, str]:
    """Public/synthetic eligibility for cloud processing in the beta."""
    cls = classification or {}
    if cls.get("sensitivity") != "public":
        return False, "sensitivity_not_public"
    if cls.get("origin") not in _ALLOWED_ORIGINS:
        return False, "origin_not_public_or_synthetic"
    if bool(cls.get("nda_applies")):
        return False, "nda_applies"
    return True, "eligible"


def _control(db, project, status: str, reason: str) -> None:
    controls.record(
        db, workspace_id=project.workspace_id, project_id=project.project_id,
        control_id="CTRL.DATA_POLICY", status=status, detail=reason[:200],
    )


def _audit(db, project, actor_user_id, action: str, detail: dict) -> None:
    audit.record(
        db, workspace_id=project.workspace_id, actor_user_id=actor_user_id,
        action=action, target_type="project", target_id=project.project_id, detail=detail,
    )


def _block(db, project, actor_user_id, *, status, code, detail) -> ProblemException:
    _control(db, project, "blocked", code)
    _audit(db, project, actor_user_id, "cloud_run.blocked", {"reason": code})
    # The block fails the request (rollback), so commit the decision record itself
    # — every allow/block must be audited. Safe: the gate runs before any run state
    # is created, so only these control/audit rows are pending.
    db.commit()
    return ProblemException(status=status, code=code, title="Cloud processing blocked",
                            detail=detail)


def validate_cloud_run(
    db: Session,
    project: Project,
    settings: RunSettings,
    *,
    actor_user_id: str,
    requested_source_version_ids: list[str],
    policy_version: str,
    effective_classification: dict | None = None,
) -> CloudDecision:
    """Gate run creation. Non-cloud modes pass through. cloud_assisted is allowed
    only for eligible classification + a valid confirmation; otherwise raises a safe
    Problem. Returns the confirmation + route class to freeze (caller marks it used)."""
    mode = settings.processing_mode
    if mode in _NO_EXTERNAL_CALL_MODES:
        return CloudDecision()
    if mode != "cloud_assisted":  # defensive; the contract enum has only these three
        raise _block(db, project, actor_user_id, status=400,
                     code="invalid_processing_mode", detail="Unknown processing mode.")

    effective_for_gate = effective_classification or project.data_classification
    project_eligible, project_reason = classification_eligible(project.data_classification)
    effective_eligible, effective_reason = classification_eligible(effective_for_gate)
    if not project_eligible or not effective_eligible:
        raise _block(
            db, project, actor_user_id, status=403,
            code="cloud_not_eligible_for_classification",
            detail=("Cloud-KI ist in dieser Beta nur für öffentliche oder synthetische "
                    "Daten verfügbar; interne, vertrauliche oder NDA-Inhalte sind blockiert."),
        )

    confirmation_id = settings.internal_cloud_confirmation_id
    if not confirmation_id:
        raise _block(
            db, project, actor_user_id, status=422, code="cloud_confirmation_required",
            detail=("Für Cloud-KI ist eine ausdrückliche Freigabe für diesen Durchlauf "
                    "erforderlich."),
        )
    confirmation = confirmations_repo.get_scoped(db, confirmation_id, project.workspace_id)
    requested = set(requested_source_version_ids or [])
    invalid = (
        confirmation is None
        or confirmation.project_id != project.project_id
        or confirmation.status != confirmations_repo.VALID
        or confirmation.processing_mode != "cloud_assisted"
        or confirmation.accepted_policy_version != policy_version
        or not requested.issubset(set(confirmation.source_version_ids or []))
    )
    if invalid:
        raise _block(
            db, project, actor_user_id, status=422, code="cloud_confirmation_invalid",
            detail="Die Cloud-Freigabe ist ungültig oder passt nicht zu diesem Durchlauf.",
        )

    route_class = provider_route_class()
    _control(db, project, "passed", "public_cloud_confirmed")
    _audit(
        db, project, actor_user_id, "cloud_run.allowed",
        {"confirmation_id": confirmation.confirmation_id, "provider_route_class": route_class,
         "policy_version": policy_version,
         "effective_sensitivity": (project.data_classification or {}).get("sensitivity"),
            "origin": (project.data_classification or {}).get("origin"),
            "merged_effective_sensitivity": (effective_for_gate or {}).get("sensitivity"),
            "merged_origin": (effective_for_gate or {}).get("origin")},
    )
    return CloudDecision(confirmation=confirmation, provider_route_class=route_class)
