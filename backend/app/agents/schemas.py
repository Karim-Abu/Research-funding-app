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
    fact_type: str | None = None
    normalized_value: str | None = None
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


# --- A1 EvidenceCandidateMapping (Milestone 9C) ----------------------------

EvidenceTargetType = Literal["requirement", "portal_field"]


class ExtractedFactRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str
    statement: str | None = None


class EvidenceCandidateMappingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    facts: list[ExtractedFactRef]
    fragment_ids: list[str]
    target_requirement_ids: list[str]
    target_field_ids: list[str]


class EvidenceCandidateRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str | None = None
    fragment_id: str
    quote: str
    target_type: EvidenceTargetType
    target_id: str
    match_rationale: str | None = None
    extracted_fact_id: str | None = None
    match_type: str = "exact_normalized"

    @model_validator(mode="after")
    def _require_quote_and_fragment(self) -> "EvidenceCandidateRecord":
        # A candidate without a fragment reference or a non-empty quote cannot be
        # provenance-checked; the orchestrator additionally verifies the quote.
        if not self.fragment_id or not self.quote.strip():
            raise ValueError("evidence candidate missing fragment_id or quote")
        return self


class TargetRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: EvidenceTargetType
    target_id: str


class EvidenceConflictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    candidate_ids: list[str] = []


class EvidenceCandidateMappingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[EvidenceCandidateRecord]
    unmapped_targets: list[TargetRef]
    conflicts: list[EvidenceConflictRecord] = []


# --- A2 Solution & Innovation field drafting (Milestone 9D) -----------------


class PortalFieldProfileView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: str
    label: str
    character_limit: int | None = None
    mandatory_questions: list[str] = []
    guidance: str | None = None


class EvidenceLinkRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor_id: str
    quote: str
    source_name: str
    verification_status: str
    page: int | None = None
    section: str | None = None
    requirement_id: str | None = None


class OpenIssueRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_id: str
    issue_type: str
    severity: str
    description: str
    target_type: str
    target_id: str


class StructuredProjectDataResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_title: str | None = None
    funding_instrument_profile_id: str | None = None
    partner_count: int = 0


class FieldDraftingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    profile_id: str
    field_profiles: list[PortalFieldProfileView]
    confirmed_facts: list[ExtractedFactRecord]
    verified_evidence: list[EvidenceLinkRecord]
    structured_project_data: StructuredProjectDataResult
    open_issues: list[OpenIssueRecord]
    language: str


class DraftCandidateRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: str
    suggested_text: str
    rationale: str | None = None
    evidence_anchor_ids: list[str] = []
    open_issue_ids: list[str] = []
    character_count: int | None = None


class PlaceholderRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    reason: str | None = None


class PortalFieldDraftBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_candidates: list[DraftCandidateRecord]
    placeholders: list[PlaceholderRecord]
    field_level_warnings: list[OpenIssueRecord] = []


# --- registry + helpers ----------------------------------------------------

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "ProjectFactExtractionInput@v1": ProjectFactExtractionInput,
    "ProjectFactExtractionResult@v1": ProjectFactExtractionResult,
    "EvidenceCandidateMappingInput@v1": EvidenceCandidateMappingInput,
    "EvidenceCandidateMappingResult@v1": EvidenceCandidateMappingResult,
    "FieldDraftingInput@v1": FieldDraftingInput,
    "PortalFieldDraftBundle@v1": PortalFieldDraftBundle,
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
    "EvidenceCandidateMappingInput",
    "EvidenceCandidateMappingResult",
    "EvidenceCandidateRecord",
    "TargetRef",
    "SchemaNotImplementedError",
    "ValidationError",
    "validate_payload",
    "fact_reference_violations",
]
