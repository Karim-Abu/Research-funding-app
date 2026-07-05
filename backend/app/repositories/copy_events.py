"""CopyEvent persistence (Slice 3). Metadata only — never raw field text."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.contracts.copy_event import CopyEvent as CopyEventSchema
from app.db.models import AnalysisRun, CopyEvent, DraftVersion, PortalFieldDraft


def create(
    db: Session,
    *,
    run: AnalysisRun,
    draft: PortalFieldDraft,
    version: DraftVersion,
    client_warnings: list[str],
    server_warnings: list[str],
    override_reason_code: str | None,
    override_reason_note: str | None,
    actor_user_id: str | None,
) -> CopyEvent:
    event = CopyEvent(
        copy_event_id=str(uuid.uuid4()),
        run_id=run.run_id,
        workspace_id=run.workspace_id,
        field_id=draft.field_id,
        draft_version_id=version.draft_version_id,
        # Already the sha256 of the version text — no recomputation, no raw text.
        content_hash=version.content_hash,
        client_warnings=client_warnings,
        server_warnings=server_warnings,
        override_reason_code=override_reason_code,
        override_reason_note=override_reason_note,
        actor_user_id=actor_user_id,
    )
    db.add(event)
    db.flush()
    return event


def to_contract(event: CopyEvent) -> CopyEventSchema:
    return CopyEventSchema(
        copy_event_id=event.copy_event_id,
        field_id=event.field_id,
        draft_version_id=event.draft_version_id,
        client_warnings=list(event.client_warnings or []),
        server_warnings=list(event.server_warnings or []),
        override_reason_code=event.override_reason_code,
        created_at=event.created_at,
    )
