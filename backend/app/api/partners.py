"""Partners router — listPartners / createPartner / updatePartner / deletePartner."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from app.api.errors import ProblemException
from app.contracts.partner import Partner, PartnerCreate
from app.db.session import get_db
from app.repositories import audit, idempotency
from app.repositories import partners as partners_repo
from app.repositories import projects as projects_repo
from app.security.deps import AuthContext, require_session, require_unsafe_guards

router = APIRouter(tags=["Partners"])


def _require_project(db, project_id, workspace_id):
    project = projects_repo.get_scoped(db, project_id, workspace_id)
    if project is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Project not found.",
        )
    return project


def _require_partner(db, partner_id, workspace_id):
    partner = partners_repo.get_scoped(db, partner_id, workspace_id)
    if partner is None:
        raise ProblemException(
            status=404, code="not_found", title="Resource not found",
            detail="Partner not found.",
        )
    return partner


@router.get("/projects/{project_id}/partners", response_model=list[Partner])
def list_partners(
    project_id: str,
    context: AuthContext = Depends(require_session),
    db: Session = Depends(get_db),
) -> list[Partner]:
    _require_project(db, project_id, context.user.workspace_id)
    rows = partners_repo.list_by_project(db, project_id, context.user.workspace_id)
    return [partners_repo.to_contract(p) for p in rows]


@router.post(
    "/projects/{project_id}/partners", response_model=Partner, status_code=201
)
def create_partner(
    project_id: str,
    payload: PartnerCreate,
    response: Response,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=8, max_length=128
    ),
) -> Partner:
    _require_project(db, project_id, context.user.workspace_id)

    scope = f"{context.user.workspace_id}:{context.user.id}:POST:/partners"
    fingerprint = idempotency.fingerprint(
        "POST", f"/projects/{project_id}/partners", payload.model_dump_json()
    )
    existing = idempotency.get(db, scope, idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ProblemException(
                status=409, code="idempotency_conflict", title="Conflict",
                detail="Idempotency-Key was reused with a different request.",
            )
        response.status_code = existing.response_status
        return Partner(**existing.response_body)

    partner = partners_repo.create(
        db, project_id=project_id, workspace_id=context.user.workspace_id,
        created_by=context.user.id, data=payload,
    )
    body = partners_repo.to_contract(partner).model_dump(mode="json")
    idempotency.save(
        db, scope=scope, key=idempotency_key, request_fingerprint=fingerprint,
        response_status=201, response_body=body, resource_id=partner.partner_id,
    )
    audit.record(
        db, workspace_id=context.user.workspace_id, actor_user_id=context.user.id,
        action="partner.create", target_type="partner", target_id=partner.partner_id,
    )
    db.commit()
    return partners_repo.to_contract(partner)


@router.patch("/partners/{partner_id}", response_model=Partner)
def update_partner(
    partner_id: str,
    payload: PartnerCreate,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> Partner:
    partner = _require_partner(db, partner_id, context.user.workspace_id)
    partners_repo.replace(db, partner, payload)
    audit.record(
        db, workspace_id=context.user.workspace_id, actor_user_id=context.user.id,
        action="partner.update", target_type="partner", target_id=partner_id,
    )
    db.commit()
    return partners_repo.to_contract(partner)


@router.delete("/partners/{partner_id}", status_code=204)
def delete_partner(
    partner_id: str,
    context: AuthContext = Depends(require_unsafe_guards),
    db: Session = Depends(get_db),
) -> Response:
    partner = _require_partner(db, partner_id, context.user.workspace_id)
    partners_repo.delete(db, partner)
    audit.record(
        db, workspace_id=context.user.workspace_id, actor_user_id=context.user.id,
        action="partner.delete", target_type="partner", target_id=partner_id,
    )
    db.commit()
    return Response(status_code=204)
