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


class DemoSeedManifest(Base):
    """Internal ownership ledger for explicit demo seeds.

    This table is not API-exposed. Reset uses it to delete only objects and
    storage refs that were created by the deterministic demo seed.
    """

    __tablename__ = "demo_seed_manifest"
    __table_args__ = (
        UniqueConstraint(
            "seed_version", "object_type", "object_id",
            name="uq_demo_seed_manifest_object",
        ),
    )

    manifest_id: Mapped[str] = mapped_column(String, primary_key=True)
    seed_version: Mapped[str] = mapped_column(String, nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    object_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    storage_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
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
    # Optional links (both nullable in the public ControlResult schema). Used by
    # the export tool boundary (Milestone 8) to attach controls to a run + a
    # ToolInvocation.
    run_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    tool_invocation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Milestone 9A: links a control to the AgentInvocation that produced it.
    agent_invocation_id: Mapped[str | None] = mapped_column(String, nullable=True)
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
    # Milestone 9D.2: cloud-processing gate provenance frozen on the run.
    cloud_confirmation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_route_class: Mapped[str | None] = mapped_column(String, nullable=True)
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
    # Milestone 9C: candidate origin (internal — public anchor/link schema unchanged).
    # deterministic_lexical (M5) | agent_a1_evidence_mapping (A1).
    generation_origin: Mapped[str] = mapped_column(
        String, nullable=False, default="deterministic_lexical"
    )
    agent_invocation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_id: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    source_extracted_fact_id: Mapped[str | None] = mapped_column(String, nullable=True)
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


# ---------------------------------------------------------------------------
# Review layer (Milestone 7): ReviewFinding, HumanDecision, ReviewApproval,
# ReviewPackage. Deterministic review only — no A3/LLM findings.
# ---------------------------------------------------------------------------


class ReviewFinding(Base):
    """Deterministic or human review finding (openapi ReviewFinding). source +
    finding_code + target are internal; the API exposes only the contract fields."""

    __tablename__ = "review_findings"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "source", "finding_code", name="uq_finding_run_source_code"
        ),
    )

    finding_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String, nullable=False)
    field_id: Mapped[str | None] = mapped_column(String, nullable=True)
    requirement_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Contract enum: blocker | warning | info
    severity: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_improvement: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Contract enum: open | resolved | overridden | dismissed
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    advisory: Mapped[bool] = mapped_column(nullable=False, default=True)
    # Internal: deterministic_review | human | system
    source: Mapped[str] = mapped_column(String, nullable=False)
    # Internal stable key for deterministic dedup/idempotent upsert.
    finding_code: Mapped[str] = mapped_column(String, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String, nullable=True)
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    recommended_next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class HumanDecision(Base):
    """Typed human review decision (openapi HumanDecision). Records review-level
    confirm/override/reject/dismiss/request_changes + optional comment. Never
    mutates technical evidence verification."""

    __tablename__ = "human_decisions"

    decision_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    # Contract enum: requirement_assessment | evidence_anchor | review_finding |
    # portal_field_draft
    target_type: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class ReviewApproval(Base):
    """Auditable review approval (openapi ReviewApproval). Goes stale on any
    later edit to the covered scope."""

    __tablename__ = "review_approvals"

    approval_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # Contract enum: run | field
    scope: Mapped[str] = mapped_column(String, nullable=False)
    scope_id: Mapped[str] = mapped_column(String, nullable=False)
    # Contract enum: open | blocked | approved | changes_required | stale
    status: Mapped[str] = mapped_column(String, nullable=False)
    approval_scope_hash: Mapped[str] = mapped_column(String, nullable=False)
    review_package_version: Mapped[str] = mapped_column(String, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class ReviewPackage(Base):
    """Computed review summary per run (1:1). Refreshed by aggregate_review +
    targeted recheck."""

    __tablename__ = "review_packages"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), primary_key=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    review_package_version: Mapped[str] = mapped_column(String, nullable=False)
    approval_scope_hash: Mapped[str] = mapped_column(String, nullable=False)
    # Contract enum: open | blocked | approved | changes_required | stale
    approval_status: Mapped[str] = mapped_column(String, nullable=False)
    blocker_count: Mapped[int] = mapped_column(nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(nullable=False, default=0)
    stale_finding_count: Mapped[int] = mapped_column(nullable=False, default=0)
    recheck_required: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# Deterministic export artifacts (Milestone 8): ExportArtifact + ToolInvocation.
# Generators read only the immutable frozen snapshot. No LLM/provider/network.
# ---------------------------------------------------------------------------


class ToolInvocation(Base):
    """Canonical registered-tool boundary call (Domain Model ToolInvocation).
    Internal only — no public endpoint. ControlResults link via
    ControlResult.tool_invocation_id."""

    __tablename__ = "tool_invocations"

    invocation_id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    tool_id: Mapped[str] = mapped_column(String, nullable=False)
    caller: Mapped[str] = mapped_column(String, nullable=False)
    input_hash: Mapped[str] = mapped_column(String, nullable=False)
    output_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    # queued | running | succeeded | failed
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    error_class: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class ExportArtifact(Base):
    """Immutable export artifact (openapi ExportArtifact). Public fields:
    export_id, run_id, type, status, draft_marked, filename, created_at. All
    other columns are internal (storage ref, hashes, frozen input snapshot)."""

    __tablename__ = "export_artifacts"

    export_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    # Contract enum: docx | markdown | technical_evidence
    type: Mapped[str] = mapped_column(String, nullable=False)
    # Contract enum: queued | generating | available | failed
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    draft_marked: Mapped[bool] = mapped_column(nullable=False)
    filename: Mapped[str | None] = mapped_column(String, nullable=True)
    # Internal --------------------------------------------------------------
    storage_key: Mapped[str | None] = mapped_column(String, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    approval_id: Mapped[str | None] = mapped_column(String, nullable=True)
    approval_scope_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    review_package_version: Mapped[str | None] = mapped_column(String, nullable=True)
    effective_data_classification: Mapped[dict] = mapped_column(JSON, nullable=False)
    export_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    export_snapshot_hash: Mapped[str] = mapped_column(String, nullable=False)
    tool_invocation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# Agent infrastructure (Milestone 9A): AgentInvocation. Internal only — no
# public endpoint. Stores hashes + metadata only (never source text, full
# prompts with source content, raw provider payloads or API keys).
# ---------------------------------------------------------------------------


class AgentInvocation(Base):
    """One controlled ModelGateway agent call (Domain Model AgentInvocation).
    Infrastructure entity; A1/A2/A3 are not wired into the run graph in M9A."""

    __tablename__ = "agent_invocations"

    invocation_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String, nullable=True)
    agent_id: Mapped[str] = mapped_column(String, nullable=False)
    profile_id: Mapped[str] = mapped_column(String, nullable=False)
    model_route: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    input_schema_id: Mapped[str] = mapped_column(String, nullable=False)
    output_schema_id: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    # queued | running | succeeded | failed | blocked | timed_out
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    input_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    output_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    safe_error_detail: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    usage_record_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Milestone 9B: non-sensitive context metadata (selected/skipped fragment
    # counts, char budget, context_hash) — never raw context or prompt text.
    context_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by_system: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# A1 Project Fact Extraction (Milestone 9B): ExtractedFact. Advisory proposals
# only (output_authority: proposal_requires_validation) — never confirms facts,
# changes RequirementAssessments, verifies evidence, or satisfies hard rules.
# Internal: no public endpoint. Stores provenance refs + metadata, not full
# source documents.
# ---------------------------------------------------------------------------


class ExtractedFact(Base):
    """An advisory A1 fact / conflict / missing-information proposal tied to a
    run (Domain Model ExtractedFact). M9B writes only proposed | conflicted |
    missing; confirmed/rejected require a real HumanDecision in a later milestone."""

    __tablename__ = "extracted_facts"
    __table_args__ = (
        UniqueConstraint("run_id", "fact_fingerprint", name="uq_run_fact_fingerprint"),
    )

    fact_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    fact_type: Mapped[str] = mapped_column(String, nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_statement: Mapped[str] = mapped_column(Text, nullable=False)
    # proposed | conflicted | missing | rejected | confirmed (M9B: first three only)
    status: Mapped[str] = mapped_column(String, nullable=False)
    requirement_id: Mapped[str | None] = mapped_column(String, nullable=True)
    field_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_fragment_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_version_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    profile_id: Mapped[str] = mapped_column(String, nullable=False)
    model_route: Mapped[str | None] = mapped_column(String, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    agent_invocation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    fact_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# A1 Evidence Candidate Mapping (Milestone 9C): the internal dedup + evaluation
# trail for agent-proposed evidence candidates. Internal only — no public
# endpoint. Records, per agent proposal: whether it was newly persisted,
# deduplicated against an existing candidate, or rejected, plus the post-verify
# verification outcome and post-link assessment — for baseline-vs-agent
# evaluation. Never exposed through OpenAPI.
# ---------------------------------------------------------------------------


class AgentEvidenceProposal(Base):
    """One A1.evidence_candidate_mapping proposal and its lifecycle outcome."""

    __tablename__ = "agent_evidence_proposals"

    proposal_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    agent_invocation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_id: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    target_requirement_id: Mapped[str | None] = mapped_column(String, nullable=True)
    fragment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    quote_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    proposed_by_agent: Mapped[bool] = mapped_column(nullable=False, default=True)
    # persisted_new | deduplicated | rejected
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    candidate_id: Mapped[str | None] = mapped_column(String, nullable=True)
    existing_candidate_id: Mapped[str | None] = mapped_column(String, nullable=True)
    duplicate_of_deterministic: Mapped[bool | None] = mapped_column(nullable=True)
    duplicate_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    # Backfilled after the deterministic verify / link stages.
    verification_status: Mapped[str | None] = mapped_column(String, nullable=True)
    linked_assessment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# A2 Solution & Innovation draft suggestions (Milestone 9D): advisory AI draft
# suggestions for SOL.INNOVATION_SOLUTION.EDITOR. Internal only — no public
# endpoint; surfaced through the async operation result. Immutable except the
# status/decision fields. Accepting (only) creates a new DraftVersion.
# ---------------------------------------------------------------------------


class DraftSuggestion(Base):
    """One advisory A2 draft suggestion produced via createRedraft (proposed →
    accepted | rejected | expired | failed). Never auto-applied."""

    __tablename__ = "draft_suggestions"

    suggestion_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    draft_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    base_version_id: Mapped[str] = mapped_column(String, nullable=False)
    field_id: Mapped[str] = mapped_column(String, nullable=False)
    profile_id: Mapped[str] = mapped_column(String, nullable=False)
    operation_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    agent_invocation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    model_route: Mapped[str | None] = mapped_column(String, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # proposed | accepted | rejected | expired | failed
    status: Mapped[str] = mapped_column(String, nullable=False, default="proposed")
    suggested_text: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_anchor_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    open_issue_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    placeholders: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    character_count: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    accepted_draft_version_id: Mapped[str | None] = mapped_column(String, nullable=True)


# ---------------------------------------------------------------------------
# Cloud-processing confirmation (Milestone 9D.2): a per-run user acknowledgement
# that selected public/synthetic content may be sent to the configured cloud AI
# for one cloud_assisted run. NOT an institutional approval. One-run, bound to the
# source versions + policy version. Internal/confidential/NDA remain blocked.
# ---------------------------------------------------------------------------


class ProcessingConfirmation(Base):
    """One-run cloud-processing confirmation (openapi ProcessingConfirmation)."""

    __tablename__ = "processing_confirmations"

    confirmation_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    # valid | used | revoked | expired
    status: Mapped[str] = mapped_column(String, nullable=False, default="valid")
    processing_mode: Mapped[str] = mapped_column(String, nullable=False)
    source_version_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    accepted_policy_version: Mapped[str] = mapped_column(String, nullable=False)
    purpose: Mapped[str] = mapped_column(String, nullable=False)
    provider_route_class: Mapped[str] = mapped_column(String, nullable=False)
    confirmation_text_version: Mapped[str] = mapped_column(String, nullable=False)
    data_classification_shown: Mapped[dict] = mapped_column(JSON, nullable=False)
    expires_after_one_run: Mapped[bool] = mapped_column(nullable=False, default=True)
    used_by_run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
