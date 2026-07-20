"""Partner schemas — exact openapi-v1_1.yaml PartnerCreate / Partner shapes."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PartnerType = Literal["research_partner", "implementation_partner", "other"]
ResearchEligibility = Literal["eligible", "not_eligible", "needs_verification"]
IndependenceStatus = Literal["confirmed", "exception", "needs_input"]


class PersonRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str
    person_id: str | None = None
    email: str | None = None
    organisation_id: str | None = None


class PartnerCreate(BaseModel):
    name: str
    partner_type: PartnerType
    project_role: str | None = None
    country: str | None = None
    location: str | None = None
    department: str | None = None
    contribution: str | None = None
    uid: str | None = None
    industry: str | None = None
    fte: float | None = Field(default=None, ge=0)
    startup_status: bool | None = None
    swiss_value_creation: bool | None = None
    research_partner_eligibility_status: ResearchEligibility | None = None
    official_representative: PersonRef | None = None
    personnel_independence_status: IndependenceStatus | None = None
    financial_independence_status: IndependenceStatus | None = None
    # Kurze Begründung; die API erzwingt sie, wenn ein Status explizit als
    # unklar/nicht bestätigt erfasst wird (Konsistenzregel, kein Urteil).
    review_comment: str | None = None


class Partner(PartnerCreate):
    partner_id: str
    project_id: str
    revision_number: int = Field(ge=1)
