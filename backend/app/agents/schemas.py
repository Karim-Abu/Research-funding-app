"""Agent I/O schema validation (Milestone 9A).

Pydantic v2 models for the agent schemas (``additional_properties: false`` →
``extra="forbid"``), a ``schema_id → model`` registry, and helpers the gateway
uses to validate provider output. M9A implements the A1 fact-extraction schemas
(M9B is A1); A2/A3 models are added in their milestones. Invocation-time
validation fails safely if a profile's concrete model is not yet implemented.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

# Shared classification type (data_policy classification_dimensions).
Sensitivity = Literal["public", "internal", "confidential"]
Origin = Literal["public_source", "synthetic", "anonymized", "real_project"]
ProcessingMode = Literal["deterministic_only", "cloud_assisted", "local_only"]
WebResearchMode = Literal["off", "validated_public"]


class DataClassificationRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sensitivity: Sensitivity
    origin: Origin
    processing_mode: ProcessingMode
    web_research_mode: WebResearchMode = "off"
    nda_applies: bool = False


# --- A1 ProjectFactExtraction ----------------------------------------------


class ProjectFactExtractionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    fragment_ids: list[str]
    active_requirement_ids: list[str]
    active_field_ids: list[str]
    data_classification: DataClassificationRef
    versioned_user_input_ids: list[str] = []


class ExtractedFactRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str
    statement: str
    target_ref: str | None = None
    source_fragment_ids: list[str] = []
    versioned_user_input_ids: list[str] = []

    @model_validator(mode="after")
    def _require_provenance(self) -> "ExtractedFactRecord":
        # Every extracted fact must cite at least one source (agents.yaml
        # acceptance criterion); a fact without provenance is invalid output.
        if not self.source_fragment_ids and not self.versioned_user_input_ids:
            raise ValueError("extracted fact has no source provenance")
        return self


class FactConflictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict_id: str
    description: str
    fact_ids: list[str] = []


class MissingInformationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_ref: str
    description: str


class ProjectFactExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: list[ExtractedFactRecord]
    conflicts: list[FactConflictRecord]
    missing_information: list[MissingInformationRecord]
    source_instruction_warnings: list[str] = []


# --- registry + helpers ----------------------------------------------------

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "ProjectFactExtractionInput@v1": ProjectFactExtractionInput,
    "ProjectFactExtractionResult@v1": ProjectFactExtractionResult,
}


class SchemaNotImplementedError(Exception):
    """A profile declared a schema with no concrete Pydantic model yet."""


def validate_payload(schema_id: str, data: object) -> BaseModel:
    """Validate ``data`` against the model for ``schema_id``.

    Raises ``SchemaNotImplementedError`` (safe-fail at invocation time) or
    ``pydantic.ValidationError`` on invalid output.
    """
    model = SCHEMA_MODELS.get(schema_id)
    if model is None:
        raise SchemaNotImplementedError(schema_id)
    return model.model_validate(data)


def fact_reference_violations(
    result: ProjectFactExtractionResult, allowed_fragment_ids: set[str]
) -> list[str]:
    """Fragment ids cited by facts that are not in the allowed run-snapshot set
    (catches hallucinated/invalid evidence references)."""
    violations: list[str] = []
    for fact in result.facts:
        for frag in fact.source_fragment_ids:
            if frag not in allowed_fragment_ids:
                violations.append(frag)
    return violations


__all__ = [
    "SCHEMA_MODELS",
    "DataClassificationRef",
    "ProjectFactExtractionInput",
    "ProjectFactExtractionResult",
    "ExtractedFactRecord",
    "SchemaNotImplementedError",
    "ValidationError",
    "validate_payload",
    "fact_reference_violations",
]
