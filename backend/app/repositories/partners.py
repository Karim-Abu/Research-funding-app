"""Partner persistence (workspace + project scoped) + ORM→contract mapping."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.partner import Partner as PartnerSchema
from app.contracts.partner import PartnerCreate
from app.db.models import Partner

# Fields shared by PartnerCreate and the ORM row (full replace on update).
_MUTABLE_FIELDS = (
    "name",
    "partner_type",
    "project_role",
    "country",
    "location",
    "department",
    "contribution",
    "uid",
    "industry",
    "fte",
    "startup_status",
    "swiss_value_creation",
    "research_partner_eligibility_status",
    "personnel_independence_status",
    "financial_independence_status",
    "review_comment",
)

_COMMENT_REQUIRING_INDEPENDENCE = ("exception", "needs_input")
_COMMENT_REQUIRING_ELIGIBILITY = ("not_eligible", "needs_verification")


def review_comment_required(data: PartnerCreate) -> bool:
    """Gemeinsame Konsistenzregel für normale und importierte Partner."""
    return bool(
        data.personnel_independence_status in _COMMENT_REQUIRING_INDEPENDENCE
        or data.financial_independence_status in _COMMENT_REQUIRING_INDEPENDENCE
        or data.research_partner_eligibility_status
        in _COMMENT_REQUIRING_ELIGIBILITY
        or data.swiss_value_creation is False
    )


def _payload_values(data: PartnerCreate) -> dict:
    dumped = data.model_dump()
    values = {field: dumped[field] for field in _MUTABLE_FIELDS}
    rep = data.official_representative
    values["official_representative"] = rep.model_dump() if rep is not None else None
    return values


def list_by_project(
    db: Session, project_id: str, workspace_id: str
) -> list[Partner]:
    return list(
        db.scalars(
            select(Partner)
            .where(
                Partner.project_id == project_id,
                Partner.workspace_id == workspace_id,
            )
            .order_by(Partner.created_at.asc())
        )
    )


def get_scoped(db: Session, partner_id: str, workspace_id: str) -> Partner | None:
    return db.scalar(
        select(Partner).where(
            Partner.partner_id == partner_id,
            Partner.workspace_id == workspace_id,
        )
    )


def create(
    db: Session,
    *,
    project_id: str,
    workspace_id: str,
    created_by: str,
    data: PartnerCreate,
    partner_id: str | None = None,
) -> Partner:
    partner = Partner(
        partner_id=partner_id or str(uuid.uuid4()),
        project_id=project_id,
        workspace_id=workspace_id,
        created_by=created_by,
        **_payload_values(data),
    )
    db.add(partner)
    db.flush()
    return partner


def replace(db: Session, partner: Partner, data: PartnerCreate) -> Partner:
    for field, value in _payload_values(data).items():
        setattr(partner, field, value)
    db.add(partner)
    db.flush()
    return partner


def delete(db: Session, partner: Partner) -> None:
    db.delete(partner)
    db.flush()


def to_contract(partner: Partner) -> PartnerSchema:
    return PartnerSchema(
        partner_id=partner.partner_id,
        project_id=partner.project_id,
        name=partner.name,
        partner_type=partner.partner_type,
        project_role=partner.project_role,
        country=partner.country,
        location=partner.location,
        department=partner.department,
        contribution=partner.contribution,
        uid=partner.uid,
        industry=partner.industry,
        fte=partner.fte,
        startup_status=partner.startup_status,
        swiss_value_creation=partner.swiss_value_creation,
        research_partner_eligibility_status=partner.research_partner_eligibility_status,
        official_representative=partner.official_representative,
        personnel_independence_status=partner.personnel_independence_status,
        financial_independence_status=partner.financial_independence_status,
        review_comment=partner.review_comment,
    )


def snapshot_dict(partner: Partner, *, schema_version: str = "run-project-v2") -> dict:
    """Deterministic structured copy for the immutable run snapshot (no PII text
    beyond the structured fields the rules consume)."""
    base = {
        "partner_id": partner.partner_id,
        "partner_type": partner.partner_type,
        "country": partner.country,
        "swiss_value_creation": partner.swiss_value_creation,
        "research_partner_eligibility_status": (
            partner.research_partner_eligibility_status
        ),
        "personnel_independence_status": partner.personnel_independence_status,
        "financial_independence_status": partner.financial_independence_status,
    }
    if schema_version == "run-project-v2":
        # Organisation data needed for section 4.6. Contact/representative PII is
        # deliberately excluded from the model-facing immutable snapshot.
        base.update({
            "name": partner.name,
            "project_role": partner.project_role,
            "department": partner.department,
            "contribution": partner.contribution,
            "industry": partner.industry,
            "fte": partner.fte,
        })
    return base
