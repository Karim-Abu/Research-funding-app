"""DataClassification — five required dimensions (exact contract enums)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class DataClassification(BaseModel):
    sensitivity: Literal["public", "internal", "confidential"]
    origin: Literal["public_source", "synthetic", "anonymized", "real_project"]
    processing_mode: Literal["deterministic_only", "cloud_assisted", "local_only"]
    web_research_mode: Literal["off", "validated_public"]
    nda_applies: bool
