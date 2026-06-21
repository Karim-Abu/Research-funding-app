"""Problem Details (RFC 9457) — schema ``Problem`` / ``FieldError``."""
from __future__ import annotations

from pydantic import BaseModel


class FieldError(BaseModel):
    field: str
    message: str
    code: str | None = None


class Problem(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    code: str
    correlation_id: str
    instance: str | None = None
    field_errors: list[FieldError] | None = None
    retry_after_seconds: int | None = None
