"""Agent I/O schema validation (Milestone 9A).

Pydantic v2 models for the agent schemas (``additional_properties: false`` →
``extra="forbid"``), a ``schema_id → model`` registry, and helpers the gateway
uses to validate provider output. M9A implements the A1 fact-extraction schemas
(M9B is A1); A2/A3 models are added in their milestones. Invocation-time
validation fails safely if a profile's concrete model is not yet implemented.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

# Shared classification type (data_policy classification_dimensions).
Sensitivity = Literal["public", "internal", "confidential"]
Origin = Literal["public_source", "synthetic", "anonymized", "real_project"]
ProcessingMode = Literal["deterministic_only", "cloud_assisted", "local_only", "live"]
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
    support_status: str | None = None
    context_kind: Literal[
        "application_evidence", "external_evidence", "external",
        "drafting_context", "research_candidate",
    ] | None = None
    source_version_id: str | None = None


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
    confirmed_facts: list[ExtractedFactRecord]  # contract-pinned: schema_catalog.yaml FieldDraftingInput@v1 — Inhalt ist advisory (R5.1)
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


# --- RUN 3C normalized field suggestion output -----------------------------


class FieldSuggestionMissingInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    reason: str
    requirement_ids: list[str] = Field(min_length=1)


class FieldSuggestionClaimV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str
    claim_type: Literal[
        "number", "date", "organization", "product", "market",
        "technology", "legal", "other",
    ]
    anchor_ids: list[str] = []


class FieldSuggestionOutputV1(BaseModel):
    """Server-normalized structured contract for a manifest-bound suggestion.

    ``factual_claims`` is advisory model metadata only.  Independent server
    extraction validates the complete ``suggestion_text`` separately.
    """

    model_config = ConfigDict(extra="forbid")

    suggestion_text: str = Field(min_length=1)
    change_summary: list[str] = []
    used_anchor_ids: list[str] = []
    used_rule_ids: list[str] = []
    missing_inputs: list[FieldSuggestionMissingInputV1] = []
    unsupported_claim_warnings: list[str] = []
    factual_claims: list[FieldSuggestionClaimV1] = []
    character_count: int = Field(ge=0)
    character_limit: int = Field(gt=0)
    character_limit_status: Literal["within_limit", "exceeded"]
    language: Literal["de", "en"]

    @model_validator(mode="after")
    def _validate_character_count(self) -> "FieldSuggestionOutputV1":
        expected = len(self.suggestion_text)
        if self.character_count != expected:
            raise ValueError("character_count_mismatch")
        expected_status = "within_limit" if expected <= self.character_limit else "exceeded"
        if self.character_limit_status != expected_status:
            raise ValueError("character_limit_status_mismatch")
        return self


# --- A2 subsection drafting (additive code-only contract) ------------------

ContextKind = Literal[
    "accepted_project_input",
    "imported_applicant_text",
    "external_evidence",
    "research_candidate",
    "portal_requirement",
    "open_issue",
    "market_finding",
]


class SectionContextSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ContextKind
    item_count: int = 0
    character_count: int = 0
    truncated: bool = False


class SectionDraftingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    profile_id: str
    field_profile: PortalFieldProfileView
    target_section: str
    accepted_project_input: dict[str, Any]
    external_evidence: list[EvidenceLinkRecord]
    research_candidate_count: int = 0
    open_issues: list[OpenIssueRecord]
    context_components: list[SectionContextSummary]
    language: Literal["de", "en"]


class SectionDraftCandidateRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: str
    target_section: str
    suggested_text: str
    rationale: str
    preserved_facts: list[str] = []
    removed_or_reframed_claims: list[str] = []
    new_claims: list[str] = []
    missing_inputs: list[PlaceholderRecord] = []
    evidence_anchor_ids: list[str] = []
    research_source_ids: list[str] = []
    open_issue_ids: list[str] = []


class PortalSectionDraftBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_candidate: SectionDraftCandidateRecord
    warnings: list[str] = []


# --- A3 Evidence & Consistency review (Milestone 9G) ------------------------

FindingSeverity = Literal["blocker", "warning", "info"]
FindingStatus = Literal["open", "resolved", "overridden", "dismissed"]


class DraftVersionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: str
    draft_version_id: str
    text: str
    created_by: str | None = None
    character_count: int | None = None


class RequirementAssessmentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    status: str
    basis: str | None = None


class RuleResultRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    status: str
    requirement_id: str | None = None


class CriticReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    profile_ids: list[str]
    current_drafts: list[DraftVersionRecord]
    requirements: list[RequirementAssessmentRecord]
    rule_results: list[RuleResultRecord]
    evidence_links: list[EvidenceLinkRecord]
    # M9G/corr-1: confirmed facts ONLY. Proposed A1 facts are passed as marked
    # context text, never here. Usually empty in the current system.
    confirmed_facts: list[ExtractedFactRecord]  # contract-pinned: schema_catalog.yaml CriticReviewInput@v1
    structured_project_data: StructuredProjectDataResult


class ReviewFindingRecord(BaseModel):
    """One advisory A3 finding. ``extra="forbid"`` rejects any attempt to carry an
    approval decision, confidence value, draft-replacement text, or a
    requirement/evidence status mutation (those keys are simply not present)."""

    model_config = ConfigDict(extra="forbid")

    origin_profile_id: str
    severity: FindingSeverity
    description: str
    status: FindingStatus = "open"
    field_id: str | None = None
    target_section: str
    requirement_id: str | None = None
    evidence_anchor_id: str | None = None
    evidence_link_id: str | None = None
    evidence_status: str | None = None
    suggested_improvement: str | None = None
    recommended_next_action: str


class ProfileReviewSummaryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    finding_count: int | None = None
    limitations: list[str] = []


class ReviewFindingBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[ReviewFindingRecord]
    profile_summaries: list[ProfileReviewSummaryRecord]
    overall_limitations: list[str] = []


# --- A1 PublicCompetenceResearch (Milestone 9I-A) --------------------------

EvidenceType = Literal[
    "institutional_profile", "publication", "public_project",
    "professional_competence", "track_record",
]


class PublicCompetenceResearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    research_task_id: str
    project_id: str
    research_result_source_version_ids: list[str]
    requested_partner_roles: list[str]
    competence_needs: list[str]


class ProfessionalEvidenceRecord(BaseModel):
    """One public professional-evidence claim. ``source_version_id`` ties the claim to
    an imported public SourceVersion; the persistence layer assigns the public id and
    source_id. Advisory only — never a confirmed fact."""

    model_config = ConfigDict(extra="forbid")

    evidence_type: EvidenceType
    subject_name: str
    organisation: str | None = None
    claim: str
    source_url: str
    source_title: str
    accessed_at: str | None = None
    source_version_id: str | None = None
    source_fragment_id: str | None = None
    exact_quote: str | None = None


class PartnerRoleSuggestionRecord(BaseModel):
    """Advisory partner-role suggestion. Evidence is referenced by 0-based index into
    the bundle's ``professional_evidence`` array (the model never invents ids)."""

    model_config = ConfigDict(extra="forbid")

    role_name: str
    competence_gap: str
    suggested_subject_name: str | None = None
    suggested_organisation: str | None = None
    professional_evidence_indexes: list[int] = []


class IdentityMatchRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_name: str
    status: Literal["matched", "ambiguous", "unresolved"]
    note: str | None = None


class PublicCompetenceResearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    professional_evidence: list[ProfessionalEvidenceRecord]
    partner_role_suggestions: list[PartnerRoleSuggestionRecord]
    unresolved_identity_matches: list[IdentityMatchRecord] = []
    warnings: list[str] = []


# --- registry + helpers ----------------------------------------------------

# --- MC MarketComparison (Milestone 9I-B, beta-internal, code-only schemas) ------

MarketCategory = Literal[
    "competitor", "alternative_solution", "substitute", "incumbent_process",
    "reference_solution", "market_size_claim", "customer_problem", "unknown",
]
MarketRelation = Literal["similar", "complementary", "competing", "reference", "unclear"]


class MarketCandidateFragment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fragment_id: str
    source_version_id: str
    source_document_id: str
    text: str


class MarketComparisonInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    comparison_id: str
    project_title: str
    # ONLY imported public fragments are fed to the model (never draft/private text).
    candidate_fragments: list[MarketCandidateFragment]


class MarketComparisonItemRecord(BaseModel):
    """One structured comparison item. Evidence is referenced by ``source_fragment_id`` +
    an exact ``quote`` copied from that fragment; the model never invents ids/offsets and
    never asserts market facts without a quote (verified deterministically downstream)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    category: MarketCategory = "unknown"
    description: str | None = None
    target_customer_segment: str | None = None
    offering_summary: str | None = None
    strengths: str | None = None
    weaknesses: str | None = None
    differentiation_relevance: str | None = None
    solution_type: str | None = None
    centralization: Literal["centralized", "decentralized", "hybrid", "unclear"] = "unclear"
    data_access_model: str | None = None
    swiss_relevance: str | None = None
    core_problem_or_benefit: str | None = None
    relevant_functions: list[str] = []
    price_business_model: str | None = None
    uncertainty: str | None = None
    relation_to_project: MarketRelation = "unclear"
    source_fragment_id: str | None = None
    source_document_id: str | None = None
    quote: str | None = None


class MarketComparisonResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketComparisonItemRecord]
    research_gaps: list[str] = []
    warnings: list[str] = []


# --- Versioned role/skill contracts (v2, additive) -------------------------


class FactEvidenceRecordV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str
    fact_text: str
    fact_type: str
    provenance_type: Literal["source_fragment", "versioned_user_input", "external_source"]
    source_fragment_id: str | None = None
    quote: str | None = None
    confidence: Literal["high", "medium", "low"]


class FactEvidenceAnalysisResultV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: list[FactEvidenceRecordV2]
    applicant_claims: list[FactEvidenceRecordV2] = []
    external_evidence_claims: list[FactEvidenceRecordV2] = []
    open_questions: list[str] = []
    conflicts: list[str] = []
    pii_redaction_status: Literal["not_required", "applied", "requires_human_review"]


class MissingInputV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    reason: str


class ProposalSectionSuggestionV2(BaseModel):
    """Normalized A2 output contract; persistence still projects to DraftSuggestion."""

    model_config = ConfigDict(extra="forbid")

    field_id: str
    section_id: str | None = None
    proposed_text: str
    character_count: int = Field(ge=0)
    character_limit: int = Field(gt=0)
    change_summary: list[str] = []
    preserved_facts: list[str] = []
    evidence_refs: list[str] = []
    applicant_claims_used: list[str] = []
    unsupported_claims: list[str] = []
    missing_inputs: list[MissingInputV2] = []
    removed_non_final_content: list[str] = []
    confidence: Literal["high", "medium", "low"]
    requires_human_review: Literal[True] = True

    @model_validator(mode="after")
    def _within_declared_limit(self) -> "ProposalSectionSuggestionV2":
        if self.character_count != len(self.proposed_text) or self.character_count > self.character_limit:
            raise ValueError("character count/limit mismatch")
        return self


class CriticalFindingV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str
    severity: FindingSeverity
    field_id: str | None = None
    section_id: str | None = None
    issue: str
    rationale: str
    evidence_refs: list[str] = []
    suggested_fix: str
    requires_human_review: Literal[True] = True
    affected_count: int = Field(default=1, ge=1)
    examples: list[str] = Field(default_factory=list, max_length=5)


class CriticalReviewBundleV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[CriticalFindingV2]
    cross_field_conflicts: list[str] = []
    strengths: list[str] = []
    overall_status: Literal["open", "review_required", "limited"]


class ResearchSynthesisFindingV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str
    category: str
    source_refs: list[str] = []
    support_status: Literal[
        "location_found", "supports_partially", "supports_strongly",
        "conflict_or_uncertain", "human_review_required",
    ]
    freshness: str | None = None
    relevance: str | None = None
    caveat: str | None = None


class ResearchEvidenceSynthesisV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[ResearchSynthesisFindingV2]
    market_comparison_rows: list[dict] = []
    partner_candidates: list[dict] = []
    open_evidence_gaps: list[str] = []


class EvidenceSupportVerificationV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_ref: str
    source_ref: str
    support_status: Literal[
        "supports_strongly", "supports_partially", "conflict_or_uncertain",
        "human_review_required", "evidence_missing",
    ]
    rationale: str
    exact_verified: bool


SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "ProjectFactExtractionInput@v1": ProjectFactExtractionInput,
    "ProjectFactExtractionResult@v1": ProjectFactExtractionResult,
    "EvidenceCandidateMappingInput@v1": EvidenceCandidateMappingInput,
    "EvidenceCandidateMappingResult@v1": EvidenceCandidateMappingResult,
    "FieldDraftingInput@v1": FieldDraftingInput,
    "PortalFieldDraftBundle@v1": PortalFieldDraftBundle,
    "SectionDraftingInput@v1": SectionDraftingInput,
    "PortalSectionDraftBundle@v1": PortalSectionDraftBundle,
    "CriticReviewInput@v1": CriticReviewInput,
    "ReviewFindingBundle@v1": ReviewFindingBundle,
    "PublicCompetenceResearchInput@v1": PublicCompetenceResearchInput,
    "PublicCompetenceResearchResult@v1": PublicCompetenceResearchResult,
    "MarketComparisonInput@v1": MarketComparisonInput,
    "MarketComparisonResult@v1": MarketComparisonResult,
    "FactEvidenceAnalysisResult@v2": FactEvidenceAnalysisResultV2,
    "ProposalSectionSuggestion@v2": ProposalSectionSuggestionV2,
    "FieldSuggestionOutput@v1": FieldSuggestionOutputV1,
    "CriticalReviewBundle@v2": CriticalReviewBundleV2,
    "ResearchEvidenceSynthesis@v2": ResearchEvidenceSynthesisV2,
    "EvidenceSupportVerification@v2": EvidenceSupportVerificationV2,
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


def json_schema_for(schema_id: str) -> dict | None:
    """JSON Schema of the declared output model (R5.5b) — handed to provider
    adapters for provider-native structured output. ``None`` for schema ids
    without an implemented model; validation stays with ``validate_payload``."""
    model = SCHEMA_MODELS.get(schema_id)
    return model.model_json_schema() if model is not None else None


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
    "json_schema_for",
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
