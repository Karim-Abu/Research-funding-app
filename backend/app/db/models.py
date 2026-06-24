"""ORM models for the Milestone 1 foundation.

Note: the session entity is named ``UserSession`` to avoid collision with
SQLAlchemy's ``Session``.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    # Contract enum: lead_admin | member
    role: Mapped[str] = mapped_column(String, nullable=False)
    display_label: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user")


class UserSession(Base):
    __tablename__ = "user_sessions"

    # The opaque session id is the cookie value (never exposed in response bodies).
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    csrf_token: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="sessions")


class FundingProfile(Base):
    __tablename__ = "funding_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    innovation_field: Mapped[str | None] = mapped_column(String, nullable=True)
    funding_instrument_profile_id: Mapped[str] = mapped_column(String, nullable=False)
    # DataClassification stored as a JSON object (5 contract fields).
    data_classification: Mapped[dict] = mapped_column(JSON, nullable=False)
    budget_framework_chf: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Contract enum: draft | active | archived
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    active_run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String, nullable=True)
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("scope", "idempotency_key", name="uq_idempotency_scope_key"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    # Scope keys the record to a workspace+user so keys cannot collide across tenants.
    scope: Mapped[str] = mapped_column(String, nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    response_status: Mapped[int] = mapped_column(nullable=False)
    response_body: Mapped[dict] = mapped_column(JSON, nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# Sources (Milestone 2): SourceDocument -> SourceVersion -> SourceFragment
# ---------------------------------------------------------------------------


class SourceDocument(Base):
    __tablename__ = "source_documents"

    source_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    # Display name / original filename — metadata only, never used in a path.
    name: Mapped[str] = mapped_column(String, nullable=False)
    # Contract enum: pdf | docx | txt | url
    type: Mapped[str] = mapped_column(String, nullable=False)
    # Contract enum: uploaded | processing | processed | needs_manual_input | failed
    status: Mapped[str] = mapped_column(String, nullable=False, default="uploaded")
    # Effective DataClassification (5 fields) as JSON.
    data_classification: Mapped[dict] = mapped_column(JSON, nullable=False)
    current_source_version_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class SourceVersion(Base):
    """Immutable once terminal. Rows are mutated only while processing
    (status uploaded/processing); reprocessing creates a new version."""

    __tablename__ = "source_versions"

    source_version_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_document_id: Mapped[str] = mapped_column(
        ForeignKey("source_documents.source_id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(nullable=False, default=1)
    original_content_hash: Mapped[str] = mapped_column(String, nullable=False)
    normalized_content_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    # Full normalized source text; fragment offsets are relative to this.
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String, nullable=True)
    normalizer_version: Mapped[str | None] = mapped_column(String, nullable=True)
    chunker_version: Mapped[str | None] = mapped_column(String, nullable=True)
    parsing_warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String, nullable=False, default="uploaded"
    )
    # Effective DataClassification of this version (consistent with the document).
    data_classification: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Storage key (never the bytes); resolved by SourceStorage.
    storage_ref: Mapped[str] = mapped_column(String, nullable=False)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    byte_size: Mapped[int] = mapped_column(nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_attempt: Mapped[int] = mapped_column(nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class SourceFragment(Base):
    __tablename__ = "source_fragments"

    fragment_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_version_id: Mapped[str] = mapped_column(
        ForeignKey("source_versions.source_version_id"), nullable=False, index=True
    )
    ordinal: Mapped[int] = mapped_column(nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int | None] = mapped_column(nullable=True)
    section: Mapped[str | None] = mapped_column(String, nullable=True)
    # Offsets relative to SourceVersion.normalized_text.
    start_offset: Mapped[int] = mapped_column(nullable=False)
    end_offset: Mapped[int] = mapped_column(nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    # Optional stricter override classification for this fragment.
    classification: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class ControlResult(Base):
    """Minimal deterministic control outcomes (size, type, signature,
    archive-safety, classification, path-safety, processing). Distinct from
    AuditEvent — not a replacement."""

    __tablename__ = "control_results"

    control_result_id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    source_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    control_id: Mapped[str] = mapped_column(String, nullable=False)
    # Data Policy control_results enum: passed | warning | blocked | failed
    status: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# Run orchestration (Milestone 3): AnalysisRun + AsyncOperation + snapshots
# ---------------------------------------------------------------------------


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        # At most one active run per project (SQLite partial unique index).
        Index(
            "uq_active_run_per_project",
            "project_id",
            unique=True,
            sqlite_where=text(
                "status IN ('created','running','paused_for_review')"
            ),
        ),
    )

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    # Contract RunStatus
    status: Mapped[str] = mapped_column(String, nullable=False, default="created")
    # Contract stage enum
    current_stage: Mapped[str] = mapped_column(
        String, nullable=False, default="initialize"
    )
    progress_percent: Mapped[int] = mapped_column(nullable=False, default=0)
    processing_mode: Mapped[str] = mapped_column(String, nullable=False)
    effective_data_classification: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Frozen contract/version snapshot (funding/rule/policy/tool/agent/parser/…).
    snapshot_versions: Mapped[dict] = mapped_column(JSON, nullable=False)
    recheck_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    semantic_findings_stale: Mapped[bool] = mapped_column(default=False, nullable=False)
    review_package_version: Mapped[str | None] = mapped_column(String, nullable=True)
    approval_scope_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    estimated_cost_chf: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    actual_cost_chf: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    stop_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    last_error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Cooperative cancellation flag, checked by the executor between stages.
    cancel_requested: Mapped[bool] = mapped_column(default=False, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class AsyncOperation(Base):
    __tablename__ = "async_operations"

    operation_id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # Contract AsyncOperation status
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    progress_percent: Mapped[int] = mapped_column(nullable=False, default=0)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Serialized Problem (or null) — no raw stack traces.
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class RunSourceSnapshot(Base):
    """Immutable run → SourceVersion association (the frozen input snapshot)."""

    __tablename__ = "run_source_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "source_version_id", name="uq_run_source_version"
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    source_version_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class RunPolicySnapshot(Base):
    """Immutable frozen runtime limits — execution reads this, never project limits."""

    __tablename__ = "run_policy_snapshots"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), primary_key=True
    )
    processing_mode: Mapped[str] = mapped_column(String, nullable=False)
    max_cost_chf: Mapped[float] = mapped_column(Float, nullable=False)
    max_llm_calls: Mapped[int] = mapped_column(nullable=False)
    max_web_calls: Mapped[int] = mapped_column(nullable=False)
    max_retries: Mapped[int] = mapped_column(nullable=False, default=1)
    max_redrafts: Mapped[int] = mapped_column(nullable=False, default=2)
    timeout_seconds: Mapped[int] = mapped_column(nullable=False, default=600)
    allowed_routes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    policy_version: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class UsageRecord(Base):
    __tablename__ = "usage_records"

    usage_record_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    input_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    cost_chf: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# Requirements, rules & partner eligibility (Milestone 4)
# ---------------------------------------------------------------------------


class Partner(Base):
    """Structured project partner (openapi Partner schema). The eligibility /
    independence fields feed the deterministic partner rules."""

    __tablename__ = "partners"

    partner_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    # Contract enum: research_partner | implementation_partner | other
    partner_type: Mapped[str] = mapped_column(String, nullable=False)
    project_role: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    contribution: Mapped[str | None] = mapped_column(String, nullable=True)
    uid: Mapped[str | None] = mapped_column(String, nullable=True)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    fte: Mapped[float | None] = mapped_column(Float, nullable=True)
    startup_status: Mapped[bool | None] = mapped_column(nullable=True)
    swiss_value_creation: Mapped[bool | None] = mapped_column(nullable=True)
    # Contract enum: eligible | not_eligible | needs_verification | null
    research_partner_eligibility_status: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    official_representative: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Contract enum: confirmed | exception | needs_input | null
    personnel_independence_status: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    financial_independence_status: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class RunProjectSnapshot(Base):
    """Immutable frozen copy of the structured project + partner inputs at run
    creation. Staleness is detected by comparing the current inputs hash to
    ``content_hash`` — the run is never re-evaluated against changed data."""

    __tablename__ = "run_project_snapshots"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), primary_key=True
    )
    project_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    partners_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    requirement_registry_version: Mapped[str] = mapped_column(String, nullable=False)
    rule_registry_version: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class RuleResult(Base):
    """Deterministic outcome of one rule for one run (Domain Model RuleResult).
    Status enum: passed | failed | needs_input | not_applicable."""

    __tablename__ = "rule_results"

    rule_result_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    requirement_id: Mapped[str | None] = mapped_column(String, nullable=True)
    rule_id: Mapped[str] = mapped_column(String, nullable=False)
    rule_version: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    # Richer registry result_mapping label (e.g. warning, human_decision_required).
    outcome_label: Mapped[str] = mapped_column(String, nullable=False)
    mapping_key: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    execution_mode: Mapped[str] = mapped_column(String, nullable=False)
    # Observed structured values + expected condition (NO raw source text).
    observed: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class RequirementAssessment(Base):
    """Aggregated requirement outcome for one run (openapi RequirementAssessment).
    Status: fulfilled | partial | open | needs_input | blocked."""

    __tablename__ = "requirement_assessments"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "requirement_id", name="uq_run_requirement"
        ),
    )

    assessment_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    requirement_id: Mapped[str] = mapped_column(String, nullable=False)
    requirement_version: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    # Basis enum: deterministic_rule | semantic_assessment | hybrid | human_override
    basis: Mapped[str] = mapped_column(String, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    stale: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class OpenIssue(Base):
    """Open question / gap / conflict tied to a requirement (openapi OpenIssue).
    Status: open | resolved | overridden | dismissed."""

    __tablename__ = "open_issues"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "target_type", "target_id", name="uq_run_issue_target"
        ),
    )

    issue_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    issue_type: Mapped[str] = mapped_column(String, nullable=False)
    # Severity enum: blocker | warning | info
    severity: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[str] = mapped_column(String, nullable=False)
    recommended_next_action: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    responsible_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# Deterministic evidence baseline (Milestone 5): EvidenceCandidate ->
# EvidenceAnchor -> EvidenceLink. No LLM/embeddings — exact lexical + verify.
# ---------------------------------------------------------------------------


class EvidenceCandidate(Base):
    """Deterministic lexical evidence candidate (internal; not API-exposed).

    A proposed exact span copied from a frozen SourceFragment that targets a
    versioned RequirementDefinition. Stores the exact span position so the
    verifier can validate the quote at its expected offset (never a global
    first-match)."""

    __tablename__ = "evidence_candidates"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "target_requirement_id", "fragment_id", "quote_hash",
            name="uq_candidate_run_target_fragment_quote",
        ),
    )

    candidate_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(
        String, nullable=False, default="requirement"
    )
    target_requirement_id: Mapped[str] = mapped_column(String, nullable=False)
    fragment_id: Mapped[str] = mapped_column(String, nullable=False)
    source_version_id: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    proposed_quote: Mapped[str] = mapped_column(Text, nullable=False)
    quote_hash: Mapped[str] = mapped_column(String, nullable=False)
    # Exact span position within the fragment's normalized_text.
    span_start_in_fragment: Mapped[int] = mapped_column(nullable=False)
    span_end_in_fragment: Mapped[int] = mapped_column(nullable=False)
    match_type: Mapped[str] = mapped_column(
        String, nullable=False, default="exact_normalized"
    )
    # Internal lexical relevance — NEVER surfaced as confidence; separate from
    # source verification.
    retrieval_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Domain Model: proposed | accepted | rejected | needs_human_review.
    status: Mapped[str] = mapped_column(String, nullable=False, default="proposed")
    retrieval_algorithm_version: Mapped[str] = mapped_column(String, nullable=False)
    # Set by the verify stage to the anchor produced for this candidate's quote.
    anchor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class EvidenceAnchor(Base):
    """Versioned concrete found-passage (openapi EvidenceAnchor). Locked to the
    exact SourceVersion + normalizer version. M5 never sets human_verified and
    leaves match_score/coverage null."""

    __tablename__ = "evidence_anchors"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "source_version_id", "start_offset", "end_offset",
            "quote_hash", name="uq_anchor_run_version_offsets_quote",
        ),
    )

    anchor_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_version_id: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    source_name: Mapped[str] = mapped_column(String, nullable=False)
    # Contract enum: pdf | docx | txt | url
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    fragment_id: Mapped[str] = mapped_column(String, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    quote_hash: Mapped[str] = mapped_column(String, nullable=False)
    page: Mapped[int | None] = mapped_column(nullable=True)
    section: Mapped[str | None] = mapped_column(String, nullable=True)
    start_offset: Mapped[int | None] = mapped_column(nullable=True)
    end_offset: Mapped[int | None] = mapped_column(nullable=True)
    # Contract enum: exact_normalized | fuzzy | semantic | manual
    match_type: Mapped[str] = mapped_column(
        String, nullable=False, default="exact_normalized"
    )
    # NULL in M5 — semantics undefined by the contract for deterministic exactness.
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    normalizer_version: Mapped[str] = mapped_column(String, nullable=False)
    # Contract enum: unverified | exact_verified | human_verified | rejected
    verification_status: Mapped[str] = mapped_column(String, nullable=False)
    human_checked_by: Mapped[str | None] = mapped_column(String, nullable=True)
    human_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class EvidenceLink(Base):
    """Target-specific link anchor -> assessment/draft/claim/finding/fact
    (openapi EvidenceLink). M5 creates only active requirement_assessment links."""

    __tablename__ = "evidence_links"
    __table_args__ = (
        UniqueConstraint(
            "anchor_id", "target_type", "target_id", name="uq_link_anchor_target"
        ),
    )

    evidence_link_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    anchor_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_anchors.anchor_id"), nullable=False, index=True
    )
    # Contract enum: requirement_assessment | draft_version | draft_claim |
    # review_finding | extracted_fact
    target_type: Mapped[str] = mapped_column(
        String, nullable=False, default="requirement_assessment"
    )
    target_id: Mapped[str] = mapped_column(String, nullable=False)
    claim_id: Mapped[str | None] = mapped_column(String, nullable=True)
    claim_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Contract enum: active | stale | removed
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# Deterministic template drafts (Milestone 6): PortalFieldDraft -> DraftVersion
# ---------------------------------------------------------------------------


class PortalFieldDraft(Base):
    """One deterministic draft per run + portal field (openapi PortalFieldDraft).
    Public fields only on the API; run_id/timestamps/template version stay
    internal."""

    __tablename__ = "portal_field_drafts"
    __table_args__ = (
        UniqueConstraint("run_id", "field_id", name="uq_draft_run_field"),
    )

    draft_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    field_id: Mapped[str] = mapped_column(String, nullable=False)
    field_name: Mapped[str] = mapped_column(String, nullable=False)
    # Contract enum: draft | needs_review | reviewed | blocked | stale
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="needs_review"
    )
    character_limit: Mapped[int | None] = mapped_column(nullable=True)
    current_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    open_issue_count: Mapped[int] = mapped_column(nullable=False, default=0)
    template_catalog_version: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class DraftVersion(Base):
    """Immutable text version of a PortalFieldDraft (openapi DraftVersion).
    created_by enum: template | user (M6 never sets agent)."""

    __tablename__ = "draft_versions"

    draft_version_id: Mapped[str] = mapped_column(String, primary_key=True)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("portal_field_drafts.draft_id"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    character_count: Mapped[int] = mapped_column(nullable=False)
    # Contract enum: agent | user | template
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    # Internal audit only (not exposed): predecessor version + originating op.
    base_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_operation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
