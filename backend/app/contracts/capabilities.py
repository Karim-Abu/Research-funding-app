"""Capabilities schema."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Capabilities(BaseModel):
    api_version: str
    polling_interval_seconds: int = Field(ge=1, le=10)
    max_upload_bytes: int | None = Field(default=None, ge=1)
    supported_source_types: list[Literal["pdf", "docx", "txt", "url"]]
    features: dict[str, bool]
