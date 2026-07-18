"""Cloud-processing gate (Milestone 9D.2).

Decides whether a `cloud_assisted` (or explicit `live`) run may be created.
Allowed ONLY for public/synthetic projects with a valid one-run processing
confirmation that matches the requested mode exactly; internal/confidential/NDA/
missing-classification stay blocked. `live` additionally requires
AI_EVAL_MODE=real and binds the confirmation text version `live-run-v1`. Every
allow/block records a ControlResult + AuditEvent. Never silently up/down-grades
the processing mode.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.registry import get_agent_registry
from app.api.errors import ProblemException
from app.contracts.run import RunSettings
from app.config.settings import get_settings
from app.db.models import ProcessingConfirmation, Project
from app.repositories import audit, controls
from app.repositories import processing_confirmations as confirmations_repo
from app.security.data_class import DataClass, derive_data_class

CONFIRMATION_TEXT_VERSION = "cloud-confirm-v1"
REAL_AI_EVAL_CONFIRMATION_TEXT_VERSION = "real-ai-eval-v1"
LIVE_RUN_CONFIRMATION_TEXT_VERSION = "live-run-v1"
A2_PROFILE_ID = "A2.solution_innovation"
_ALLOWED_ORIGINS = ("synthetic", "public_source")
_REAL_EVAL_ORIGINS = ("synthetic", "anonymized")
_LIVE_RUN_ORIGINS = ("synthetic", "anonymized", "public_source")
_NO_EXTERNAL_CALL_MODES = ("deterministic_only", "local_only")


@dataclass(frozen=True)
class CloudDecision:
    confirmation: ProcessingConfirmation | None = None
    provider_route_class: str | None = None


def provider_route_class() -> str:
    """The active provider route class for the A2 primary model (public beta).

    Im Live-Routing (AI_EVAL_MODE=real) gilt die Rollenroute — die Bestätigung
    friert dann wahrheitsgemäss den Provider der Live-Primärroute ein."""
    registry = get_agent_registry()
    if get_settings().ai_eval_mode == "real" and registry.role_routes:
        role_route = registry.role_routes.get("A2_INNOSUISSE_PROPOSAL_WRITER")
        if (
            role_route is not None
            and role_route.execution_kind == "model_gateway"
            and role_route.primary
        ):
            return registry.route(role_route.primary).provider
    profile = registry.profile(A2_PROFILE_ID)
    return registry.route(profile.primary_model).provider


def classification_eligible(classification: dict) -> tuple[bool, str]:
    """Public/synthetic eligibility for cloud processing in the beta."""
    cls = classification or {}
    if bool(cls.get("nda_applies")):
        return False, "nda_applies"
    origin = cls.get("origin")
    if (
        origin in ("synthetic", "anonymized")
        and get_settings().ai_eval_mode == "real"
        and derive_data_class(cls) not in (DataClass.D3_NDA_BLOCKED, DataClass.UNKNOWN)
    ):
        return True, "real_eval_eligible"
    if cls.get("sensitivity") != "public":
        return False, "sensitivity_not_public"
    if origin not in _ALLOWED_ORIGINS:
        return False, "origin_not_public_or_synthetic"
    return True, "eligible"


def confirmation_text_version_for(
    classification: dict, processing_mode: str = "cloud_assisted"
) -> str:
    if processing_mode == "live":
        return LIVE_RUN_CONFIRMATION_TEXT_VERSION
    cls = classification or {}
    if (
        cls.get("origin") in ("synthetic", "anonymized")
        and get_settings().ai_eval_mode == "real"
    ):
        return REAL_AI_EVAL_CONFIRMATION_TEXT_VERSION
    return CONFIRMATION_TEXT_VERSION


def _live_origin_ok(classification: dict) -> bool:
    """Origin-Gate für explizite Live-Läufe: synthetic/anonymized wie im
    Real-Eval-Pfad, zusätzlich public_source — dann aber nur bei sensitivity
    public (spiegelt classification_eligible)."""
    cls = classification or {}
    origin = cls.get("origin")
    if origin not in _LIVE_RUN_ORIGINS:
        return False
    if origin == "public_source":
        return cls.get("sensitivity") == "public"
    return True


def real_eval_confirmed(run) -> bool:
    """Return whether this exact run consumed the real-evaluation confirmation.

    Legacy path (`cloud_assisted` + real-ai-eval-v1): run and project must both
    remain synthetic/anonymized. Live path (`live` + live-run-v1): additionally
    public_source with public sensitivity. The helper reads only IDs/status
    metadata and is shared by A1/A2/A3 so every live resolver uses the same
    one-run truth.
    """
    live_run = getattr(run, "processing_mode", None) == "live"
    classification = dict(run.effective_data_classification or {})
    if live_run:
        if not _live_origin_ok(classification):
            return False
    elif classification.get("origin") not in _REAL_EVAL_ORIGINS:
        return False
    try:
        db = Session.object_session(run)
    except Exception:
        return False
    if db is None:
        return False
    project = db.get(Project, run.project_id) if run.project_id else None
    if project is None:
        return False
    project_cls = project.data_classification or {}
    if live_run:
        if not _live_origin_ok(project_cls):
            return False
    elif project_cls.get("origin") not in _REAL_EVAL_ORIGINS:
        return False
    expected_mode = "live" if live_run else "cloud_assisted"
    expected_text = (
        LIVE_RUN_CONFIRMATION_TEXT_VERSION
        if live_run
        else REAL_AI_EVAL_CONFIRMATION_TEXT_VERSION
    )
    return db.scalar(
        select(ProcessingConfirmation.confirmation_id).where(
            ProcessingConfirmation.used_by_run_id == run.run_id,
            ProcessingConfirmation.processing_mode == expected_mode,
            ProcessingConfirmation.status == "used",
            ProcessingConfirmation.confirmation_text_version == expected_text,
        )
    ) is not None


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
    """Gate run creation. Non-cloud modes pass through. cloud_assisted/live are
    allowed only for eligible classification + a valid mode-matching confirmation;
    otherwise raises a safe Problem. Returns the confirmation + route class to
    freeze (caller marks it used)."""
    mode = settings.processing_mode
    if mode in _NO_EXTERNAL_CALL_MODES:
        # Es existiert kein lokaler/institutioneller Modelladapter. ``local_only``
        # bleibt daher regelbasiert; eine alte KI-Bestätigung darf keinen Pfad öffnen.
        if mode == "local_only" and settings.internal_cloud_confirmation_id:
            raise _block(
                db, project, actor_user_id, status=403,
                code="local_ai_provider_unavailable",
                detail=("Für diese Datenklasse ist aktuell kein freigegebener "
                        "KI-Provider konfiguriert. Die App führt nur regelbasierte "
                        "Prüfungen aus."),
            )
        return CloudDecision()
    if mode not in ("cloud_assisted", "live"):  # defensive; contract enum
        raise _block(db, project, actor_user_id, status=400,
                     code="invalid_processing_mode", detail="Unknown processing mode.")
    if mode == "live" and get_settings().ai_eval_mode != "real":
        # Live-Läufe existieren nur mit real geschaltetem Provider-Pfad — nie
        # als stiller Demo-/Fake-Ersatz.
        raise _block(
            db, project, actor_user_id, status=403,
            code="live_mode_requires_real_eval",
            detail=("Live-KI ist in dieser Umgebung nicht freigeschaltet. "
                    "Es sind nur regelbasierte oder Demo-Durchläufe möglich."),
        )

    effective_for_gate = effective_classification or project.data_classification
    project_eligible, project_reason = classification_eligible(
        project.data_classification)
    effective_eligible, effective_reason = classification_eligible(
        effective_for_gate)
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
    confirmation = confirmations_repo.get_scoped(
        db, confirmation_id, project.workspace_id)
    requested = set(requested_source_version_ids or [])
    invalid = (
        confirmation is None
        or confirmation.project_id != project.project_id
        or confirmation.status != confirmations_repo.VALID
        # Exakter Modus-Match: eine Demo-/Cloud-Bestätigung darf nie einen
        # Live-Lauf öffnen und umgekehrt.
        or confirmation.processing_mode != mode
        or confirmation.accepted_policy_version != policy_version
        or not requested.issubset(set(confirmation.source_version_ids or []))
        or confirmation.confirmation_text_version
        != confirmation_text_version_for(effective_for_gate, mode)
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
