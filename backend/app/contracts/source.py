"""Source schemas — SourceDocument, TextSourceCreate, UrlSourceCreate."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.contracts.classification import DataClassification

SourceType = Literal["pdf", "docx", "txt", "url"]
SourceStatus = Literal[
    "uploaded", "processing", "processed", "needs_manual_input", "failed"
]


class SourceDocument(BaseModel):
    source_id: str
    project_id: str
    name: str
    type: SourceType
    status: SourceStatus
    data_classification: DataClassification
    current_source_version_id: str | None = None
    created_at: datetime | None = None
    error_message: str | None = None
    # Maschinenlesbare Ursache bei failed/needs_manual_input (additiv), z. B.
    # SOURCE_PDF_ENCRYPTED | SOURCE_NO_TEXT_LAYER | SOURCE_PARSE_FAILED —
    # erlaubt der UI ursachenspezifische Handlungshinweise ohne Textvergleich.
    error_code: str | None = None
    source_url: str | None = None


class TextSourceCreate(BaseModel):
    name: str
    text: str
    data_classification: DataClassification


class UrlSourceCreate(BaseModel):
    url: str
    data_classification: DataClassification
    # Contract: const true — the user must explicitly confirm the URL is public.
    user_confirmed_public: Literal[True]
    name: str | None = None
    # User-pasted public page text. When absent, no server-side fetch is attempted.
    manual_content: str | None = None
