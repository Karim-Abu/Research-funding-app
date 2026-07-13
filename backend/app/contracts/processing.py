"""Cloud-processing confirmation contracts (Milestone 9D.2).

A per-run user acknowledgement that selected public/synthetic content may be sent to
the configured cloud AI for one cloud_assisted run. Matches the openapi
ProcessingConfirmationCreate / ProcessingConfirmation schemas.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProcessingConfirmationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # R4.3 (additiv, Owner-Entscheid 2026-07-08): "local_only" = KI-Opt-in für
    # interne/vertrauliche Projekte über den lokalen Verarbeitungspfad.
    processing_mode: Literal["cloud_assisted", "local_only"]
    source_version_ids: list[str] = Field(min_length=1)
    accepted_policy_version: str
    purpose: str
    expires_after_one_run: bool = True

    @field_validator("expires_after_one_run")
    @classmethod
    def _must_expire(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("expires_after_one_run must be true")
        return v


class ProcessingConfirmation(BaseModel):
    confirmation_id: str
    project_id: str
    created_by: str
    status: Literal["valid", "used", "revoked", "expired"]
    source_version_ids: list[str]
    policy_version: str
    created_at: datetime
