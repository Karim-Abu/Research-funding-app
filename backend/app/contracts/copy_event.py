"""CopyEvent schemas (Slice 3, Council E2-A).

Governance metadata for one Innolink copy action. The client never sends raw
field text; the server derives content_hash from the copied DraftVersion. The
free-text note (reason "other" only) stays on the event and is never echoed
back or mirrored into audit events.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

WarningCode = Literal["open", "limit", "review"]
OverrideReasonCode = Literal[
    "portal_finalization", "warning_not_relevant", "coordination_draft", "other"
]


class CopyEventCreate(BaseModel):
    """createCopyEvent body. extra="forbid" rejects unknown payload properties
    (there is deliberately no request property named "warnings")."""

    model_config = ConfigDict(extra="forbid")

    draft_version_id: str
    client_warnings: list[WarningCode] = []
    override_reason_code: OverrideReasonCode | None = None
    override_reason_note: str | None = Field(default=None, max_length=200)


class CopyEvent(BaseModel):
    copy_event_id: str
    field_id: str
    draft_version_id: str
    client_warnings: list[WarningCode]
    server_warnings: list[WarningCode]
    override_reason_code: OverrideReasonCode | None = None
    created_at: datetime
