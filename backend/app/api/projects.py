"""Projects router — list/create/get/update, workspace-scoped + idempotent create."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.contracts.budget_precheck import (
    BudgetPrecheck,
    BudgetPrecheckCheck,
    BudgetPrecheckFigures,
)
from app.contracts.processing import ProcessingConfirmation, ProcessingConfirmationCreate
from app.contracts.project import Project, ProjectCreate, ProjectList, ProjectPatch
from app.db.session import get_db
from app.registry import get_registry
from app.repositories import audit, controls, idempotency, projects
from app.repositories import processing_confirmations as confirmations_repo
from app.rules.engine import evaluate_rule
from app.rules.inputs import inputs_from_snapshot
from app.runs import cloud_policy
from app.runs.policy import POLICY_VERSION
from app.runs.project_snapshot import current_inputs
from app.security.data_class import DataClass, derive_data_class
from app.security.deps import AuthContext, require_session, require_unsafe_guards

router = APIRouter(tags=["Projects"])
_NOT_FOUND = "Resource not found"


@router.get("/projects", response_model=ProjectList)
def list_projects(
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> ProjectList:
    rows = projects.list_by_workspace(db, context.user.workspace_id)
    return ProjectList(
        items=[projects.to_contract(db, p) for p in rows],
        next_cursor=None,
    )


@router.post("/projects", response_model=Project, status_code=201)
def create_project(
    payload: ProjectCreate,
    response: Response,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=8, max_length=128
    ),
) -> Project:
    scope = f"{context.user.workspace_id}:{context.user.id}:POST:/projects"
    fingerprint = idempotency.fingerprint(
        "POST", "/api/v1/projects", payload.model_dump_json()
    )

    existing = idempotency.get(db, scope, idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ProblemException(
                status=409,
                code="idempotency_conflict",
                title="Conflict",
                detail="Idempotency-Key was reused with a different request.",
            )
        response.status_code = existing.response_status
        return Project(**existing.response_body)

    project = projects.create(
        db,
        workspace_id=context.user.workspace_id,
        created_by=context.user.id,
        data=payload,
    )
    body = projects.to_contract(db, project).model_dump(mode="json")
    idempotency.save(
        db,
        scope=scope,
        key=idempotency_key,
        request_fingerprint=fingerprint,
        response_status=201,
        response_body=body,
        resource_id=project.project_id,
    )
    audit.record(
        db,
        workspace_id=context.user.workspace_id,
        actor_user_id=context.user.id,
        action="project.create",
        target_type="project",
        target_id=project.project_id,
    )
    db.commit()
    return projects.to_contract(db, project)


@router.post(
    "/projects/{project_id}/processing-confirmations",
    response_model=ProcessingConfirmation,
    status_code=201,
)
def create_processing_confirmation(
    project_id: str,
    payload: ProcessingConfirmationCreate,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=8, max_length=128
    ),
) -> ProcessingConfirmation:
    """Milestone 9D.2: a per-run user acknowledgement that selected public/synthetic
    content may be sent to the configured cloud AI for one cloud_assisted run. Any
    project participant (member or lead_admin) may confirm. This is NOT an
    institutional approval — internal/confidential/NDA stay blocked."""
    project = projects.get_scoped(db, project_id, context.user.workspace_id)
    if project is None:
        raise ProblemException(
            status=404, code="not_found", title=_NOT_FOUND, detail="Project not found.",
        )
    if payload.processing_mode == "local_only":
        # R4.3 (Owner-Entscheid 2026-07-08): KI-Opt-in über den lokalen Pfad —
        # nur für interne/vertrauliche Projekte; NDA/unklassifiziert bleibt
        # fail-closed blockiert. Die Bestätigung dokumentiert die verstandene
        # Warnung (local-ai-confirm-v1).
        data_class = derive_data_class(project.data_classification)
        if data_class not in (DataClass.D1_INTERNAL, DataClass.D2_CONFIDENTIAL_IDEA):
            raise ProblemException(
                status=403, code="local_ai_not_eligible_for_classification",
                title="Forbidden",
                detail=("Der lokale KI-Pfad steht nur für interne oder vertrauliche "
                        "Inhalte zur Verfügung; NDA-gesperrte oder nicht eingestufte "
                        "Inhalte bleiben blockiert."),
            )
        route_class = cloud_policy.LOCAL_AI_ROUTE_CLASS
        text_version = cloud_policy.LOCAL_AI_CONFIRMATION_TEXT_VERSION
    else:
        # The confirmation cannot override the classification gate (corr #2).
        eligible, reason = cloud_policy.classification_eligible(project.data_classification)
        if not eligible:
            raise ProblemException(
                status=403, code="cloud_not_eligible_for_classification",
                title="Forbidden",
                detail=("Cloud-KI ist in dieser Beta nur für öffentliche oder synthetische "
                        "Daten verfügbar; interne, vertrauliche oder NDA-Inhalte sind blockiert."),
            )
        route_class = cloud_policy.provider_route_class()
        text_version = cloud_policy.CONFIRMATION_TEXT_VERSION
    if payload.accepted_policy_version != POLICY_VERSION:
        raise ProblemException(
            status=422, code="policy_version_mismatch", title="Unprocessable Entity",
            detail="Die bestätigte Richtlinienversion ist nicht aktuell.",
        )
    project_versions = confirmations_repo.project_source_version_ids(db, project.project_id)
    if not set(payload.source_version_ids).issubset(project_versions):
        raise ProblemException(
            status=422, code="unknown_source_version", title="Unprocessable Entity",
            detail="Eine ausgewählte Quelle gehört nicht zu diesem Projekt.",
        )

    confirmation = confirmations_repo.create(
        db, project, created_by=context.user.id,
        source_version_ids=payload.source_version_ids,
        accepted_policy_version=payload.accepted_policy_version, purpose=payload.purpose,
        provider_route_class=route_class,
        confirmation_text_version=text_version,
        data_classification_shown=dict(project.data_classification or {}),
        processing_mode=payload.processing_mode,
    )
    controls.record(
        db, workspace_id=project.workspace_id, project_id=project.project_id,
        control_id="CTRL.DATA_POLICY", status="passed",
        detail=("local_ai_confirmation_created"
                if payload.processing_mode == "local_only"
                else "cloud_confirmation_created"),
    )
    audit.record(
        db, workspace_id=project.workspace_id, actor_user_id=context.user.id,
        action="processing_confirmation.created", target_type="project",
        target_id=project.project_id,
        detail={
            "confirmation_id": confirmation.confirmation_id,
            "source_version_ids": list(payload.source_version_ids),
            "processing_mode": payload.processing_mode,
            "data_classification_shown": dict(project.data_classification or {}),
            "confirmation_text_version": text_version,
            "policy_version": POLICY_VERSION,
            "provider_route_class": confirmation.provider_route_class,
        },
    )
    db.commit()
    return confirmations_repo.to_contract(confirmation)


@router.get("/projects/{project_id}", response_model=Project)
def get_project(
    project_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> Project:
    project = projects.get_scoped(db, project_id, context.user.workspace_id)
    if project is None:
        raise ProblemException(
            status=404,
            code="not_found",
            title="Resource not found",
            detail="Project not found.",
        )
    return projects.to_contract(db, project)


# --- Budget-Vorprüfung (read-only, run-unabhängig) ---------------------------
# Genau die zwei deterministischen Budget-Kernregeln; Schwellen kommen NUR aus
# der Registry (rule.condition), die Rechnung NUR aus den bestehenden Handlern.
_PRECHECK_RULE_IDS = (
    "INNO.BUDGET.IMPLEMENTATION_SHARE_40_60",
    "INNO.BUDGET.CASH_MIN5",
)

# Handler-mapping_key → Vorprüfungs-Status (eigenes Vokabular, kein
# Requirement-Status): Ausnahme-Branches bleiben menschliche Prüfung.
_MAPPING_TO_PRECHECK_STATUS = {
    "in_range": "fulfilled",
    "at_or_above_min": "fulfilled",
    "out_of_range_with_claimed_exception": "review",
    "below_with_claimed_exception": "review",
    "out_of_range_without_exception": "blocker",
    "below_without_exception": "blocker",
    "missing": "missing",
}


@router.get(
    "/projects/{project_id}/budget/precheck", response_model=BudgetPrecheck
)
def budget_precheck(
    project_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> BudgetPrecheck:
    """Reine Leseableitung über Live-Daten — persistiert nichts (kein
    RuleResult/OpenIssue/Audit) und ersetzt keinen Analyse-Lauf."""
    project = projects.get_scoped(db, project_id, context.user.workspace_id)
    if project is None:
        raise ProblemException(
            status=404,
            code="not_found",
            title=_NOT_FOUND,
            detail="Project not found.",
        )
    registry = get_registry()
    # current_inputs liefert exakt die Dicts, die auch der Run-Snapshot
    # einfriert — damit ist die Parität zum späteren Lauf strukturell gegeben.
    project_dict, partner_dicts = current_inputs(db, project)
    inputs = inputs_from_snapshot(
        profile_id=project.funding_instrument_profile_id,
        partner_dicts=partner_dicts,
        project_dict=project_dict,
    )

    denominator = inputs.direct_total_project_costs_excluding_overhead

    def _share(numerator: float | None) -> float | None:
        # Fehlender Wert oder 0-Nenner → «Angabe fehlt», nie ein Falschurteil.
        if numerator is None or not denominator:
            return None
        return round(numerator / denominator * 100, 2)

    figures = BudgetPrecheckFigures(
        direct_costs_chf=denominator,
        own_contribution_chf=inputs.implementation_own_contribution,
        cash_contribution_chf=inputs.cash_contribution,
        requested_funding_chf=inputs.total_requested_funding,
        implementation_contribution_chf=inputs.implementation_numerator,
        implementation_share_percent=_share(inputs.implementation_numerator),
        cash_share_percent=_share(inputs.cash_contribution),
        funding_share_percent=_share(inputs.total_requested_funding),
        exception_claimed=inputs.budget_exception_basis is not None,
    )

    checks: list[BudgetPrecheckCheck] = []
    for rule_id in _PRECHECK_RULE_IDS:
        rule = registry.rules[rule_id]
        outcome = evaluate_rule(
            rule, inputs, rule_version=registry.rule_registry_version
        )
        requirement = (
            registry.requirements.get(rule.requirement_id)
            if rule.requirement_id
            else None
        )
        checks.append(
            BudgetPrecheckCheck(
                rule_id=rule.rule_id,
                requirement_id=rule.requirement_id,
                title=requirement.title if requirement else rule.title,
                status=_MAPPING_TO_PRECHECK_STATUS.get(
                    outcome.mapping_key, "missing"
                ),
                reason=outcome.reason,
                observed=outcome.observed,
                condition=rule.condition,
                severity=rule.severity,
                source_ref=rule.source_ref,
                source_version=rule.source_version,
                last_checked=rule.last_checked,
                rule_version=outcome.rule_version,
            )
        )
    return BudgetPrecheck(figures=figures, checks=checks)


@router.patch("/projects/{project_id}", response_model=Project)
def update_project(
    project_id: str,
    payload: ProjectPatch,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> Project:
    project = projects.get_scoped(db, project_id, context.user.workspace_id)
    if project is None:
        raise ProblemException(
            status=404,
            code="not_found",
            title="Resource not found",
            detail="Project not found.",
        )
    projects.apply_patch(db, project, payload)
    audit.record(
        db,
        workspace_id=context.user.workspace_id,
        actor_user_id=context.user.id,
        action="project.update",
        target_type="project",
        target_id=project.project_id,
    )
    db.commit()
    return projects.to_contract(db, project)
