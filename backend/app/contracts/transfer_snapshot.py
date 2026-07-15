"""Read/write contracts for deterministic, manual Innolink transfer.

The POST body identifies a frozen structured value only.  It intentionally has
no text/value field: the server resolves and hashes the value from the immutable
RunProjectSnapshot.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


StructuredCopyTarget = Literal["partner_row", "partner_cell", "budget_value", "duration"]


class TransferCopyEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: StructuredCopyTarget
    target_key: str


class TransferCopyEvent(BaseModel):
    copy_event_id: str
    target_type: StructuredCopyTarget
    target_key: str
    created_at: datetime


class TransferSnapshot(BaseModel):
    """Deliberately flexible JSON projection; values are all RunSnapshot based."""

    model_config = ConfigDict(extra="forbid")

    snapshot_available: bool
    stale: bool
    stale_message: str | None = None
    project: dict
    partners: list[dict]
    budget: dict
    sources: list[dict]
    manual_portal_tasks: list[str]
