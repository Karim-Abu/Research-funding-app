"""Export schemas — exact openapi-v1_1.yaml shapes (Milestone 8)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ExportType = Literal["docx", "markdown", "technical_evidence"]
ExportStatus = Literal["queued", "generating", "available", "failed"]


class ExportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ExportType
    force_draft: bool = False


class ExportArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_id: str
    run_id: str
    type: ExportType
    status: ExportStatus
    draft_marked: bool
    filename: str | None = None
    created_at: datetime | None = None
