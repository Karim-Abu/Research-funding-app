"""ORM models for the Milestone 1 foundation.

Note: the session entity is named ``UserSession`` to avoid collision with
SQLAlchemy's ``Session``.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Date,
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
    title_en: Mapped[str | None] = mapped_column(String, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    innovation_field: Mapped[str | None] = mapped_column(String, nullable=True)
    funding_instrument_profile_id: Mapped[str] = mapped_column(String, nullable=False)
    # DataClassification stored as a JSON object (5 contract fields).
    data_classification: Mapped[dict] = mapped_column(JSON, nullable=False)
    budget_framework_chf: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Structured budget inputs (Slice 1) — feed the deterministic 40-60% and
    # 5%-cash rules via the frozen run snapshot. All optional; no BudgetPlan
    # entity in this slice.
    direct_total_project_costs_excluding_overhead: Mapped[float | None] = (
        mapped_column(Float, nullable=True)
    )
    implementation_own_contribution: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    cash_contribution: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_requested_funding: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    # Reine Zusatzinformation aus dem Portal. Sie wird nie als direkte
    # Foerderung in die formale Regelbasis gespiegelt.
    total_requested_funding_including_overhead: Mapped[float | None] = (
        mapped_column(Float, nullable=True)
    )
    budget_exception_basis: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_months: Mapped[int | None] = mapped_column(nullable=True)
    primary_application_source_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    # Monotonic resource revision for project-owned import targets. The
    # per-field history lives in ProjectFieldRevision.
    field_revision_number: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
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
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
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
    # RUN 3B: normalized, allow-listed web retrieval provenance only. Full
    # provider responses and search snippets are never stored here.
    retrieval_provenance: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    content_review_status: Mapped[str] = mapped_column(
        String, nullable=False, default="not_applicable"
    )
    content_safety_status: Mapped[str] = mapped_column(
        String, nullable=False, default="not_checked"
    )
    quarantine_reason_code: Mapped[str | None] = mapped_column(String, nullable=True)
    similarity_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    possible_duplicate_source_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
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


class ImportCandidate(Base):
    """R3.2 — ein erkanntes Feld aus einem Innolink-Antragsimport.

    Jeder Kandidat braucht eine explizite menschliche Entscheidung (HITL);
    ``uncertain`` ist nie automatisch übernehmbar. decision enum:
    pending | conflict | accepted | saved_as_source | ignored — ``conflict``
    ist ein Zwischenzustand (bestehender bearbeiteter Draft, Entscheid mit
    expliziter Bestätigung nötig), kein Endzustand.
    """

    __tablename__ = "import_candidates"
    __table_args__ = (
        UniqueConstraint(
            "source_version_id", "field_id", name="uq_import_candidate_version_field"
        ),
    )

    import_candidate_id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("source_documents.source_id"), nullable=False, index=True
    )
    source_version_id: Mapped[str] = mapped_column(
        ForeignKey("source_versions.source_version_id"), nullable=False
    )
    field_id: Mapped[str] = mapped_column(String, nullable=False)
    # Extrahierter Antragstext (D2) — bleibt in der DB, nie in Logs/Audit.
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    # «Bearbeitet übernommen»: menschlich editierter Text (D2, nie in Logs).
    # extracted_text bleibt als Originalausschnitt unverändert erhalten.
    edited_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Mapping-Konfidenz: found | uncertain (uncertain nie auto-übernehmbar).
    confidence: Mapped[str] = mapped_column(String, nullable=False)
    # Menschlich lesbare Fundstelle, z. B. "Seite 3"; None bei Textquellen.
    source_location: Mapped[str | None] = mapped_column(String, nullable=True)
    # Version + nachvollziehbare Abschnittszuordnung des deterministischen
    # Mappings. section_metadata kann D2-Rohstellen enthalten: nie loggen.
    mapping_version: Mapped[str] = mapped_column(
        String, nullable=False, default="innolink-narrative-v2"
    )
    mapping_status: Mapped[str] = mapped_column(
        String, nullable=False, default="content_detected"
    )
    section_metadata: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    decision: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    decided_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Provenienz: die durch «Übernehmen» erzeugte DraftVersion.
    accepted_draft_version_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    current_revision_id: Mapped[str | None] = mapped_column(String, nullable=True)
    revision_number: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class StructuredImportCandidate(Base):
    """Deterministischer, nicht textfeldgebundener Importkandidat.

    Payloads koennen D2 und bei Partnern Personennamen enthalten. Sie werden
    ausschliesslich in der DB gespeichert und nie in Audit- oder Log-Details
    kopiert. Jede fachliche Persistierung benoetigt eine menschliche
    Entscheidung.
    """

    __tablename__ = "structured_import_candidates"
    __table_args__ = (
        UniqueConstraint(
            "source_version_id",
            "candidate_kind",
            "target_key",
            name="uq_structured_import_version_kind_target",
        ),
    )

    candidate_id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("source_documents.source_id"), nullable=False, index=True
    )
    source_version_id: Mapped[str] = mapped_column(
        ForeignKey("source_versions.source_version_id"), nullable=False
    )
    candidate_kind: Mapped[str] = mapped_column(String, nullable=False)
    target_key: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    edited_payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[str] = mapped_column(String, nullable=False)
    source_location: Mapped[str | None] = mapped_column(String, nullable=True)
    mapping_version: Mapped[str] = mapped_column(String, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    decided_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Polymorphe Provenienz auf Project/Partner; bewusst kein FK auf
    # unterschiedliche Zieltabellen.
    applied_resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    supersedes_candidate_id: Mapped[str | None] = mapped_column(
        ForeignKey("structured_import_candidates.candidate_id"), nullable=True
    )
    current_revision_id: Mapped[str | None] = mapped_column(String, nullable=True)
    revision_number: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class ImportCandidateRevision(Base):
    """Versioned narrative decision. ``user_text`` is D2 and stays here."""

    __tablename__ = "import_candidate_revisions"
    __table_args__ = (
        UniqueConstraint(
            "import_candidate_id",
            "revision_number",
            name="uq_import_candidate_revision_number",
        ),
    )

    revision_id: Mapped[str] = mapped_column(String, primary_key=True)
    import_candidate_id: Mapped[str] = mapped_column(
        ForeignKey("import_candidates.import_candidate_id"), nullable=False, index=True
    )
    revision_number: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    user_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    previous_draft_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    applied_draft_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    actor_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class StructuredImportCandidateRevision(Base):
    """Versioned structured decision. Payload values remain D2-only here."""

    __tablename__ = "structured_import_candidate_revisions"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "revision_number",
            name="uq_structured_import_candidate_revision_number",
        ),
    )

    revision_id: Mapped[str] = mapped_column(String, primary_key=True)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("structured_import_candidates.candidate_id"),
        nullable=False,
        index=True,
    )
    revision_number: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    user_payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    previous_target_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    target_resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    previous_target_revision_number: Mapped[int | None] = mapped_column(nullable=True)
    applied_target_revision_number: Mapped[int | None] = mapped_column(nullable=True)
    project_field_revision_id: Mapped[str | None] = mapped_column(String, nullable=True)
    actor_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class ProjectFieldRevision(Base):
    """Immutable current-value history for an importable project field."""

    __tablename__ = "project_field_revisions"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "field_name",
            "revision_number",
            name="uq_project_field_revision_number",
        ),
    )

    revision_id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String, nullable=False)
    revision_number: Mapped[int] = mapped_column(nullable=False)
    value_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_revision_id: Mapped[str | None] = mapped_column(String, nullable=True)
    actor_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
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
    # Milestone 9I-A: links a control to a public-web-research task.
    research_task_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
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
    # KI-Teilstatus getrennt vom allgemeinen, deterministischen Run-Status.
    live_execution_status: Mapped[str | None] = mapped_column(String, nullable=True)
    live_status_reason: Mapped[str | None] = mapped_column(String, nullable=True)
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


class RunPhase(Base):
    """User-facing phase status of one analysis run, persisted so a reload
    shows the same progress. Additive next to the technical stage columns on
    ``AnalysisRun`` (which stay authoritative for the contract RunStage).
    ``detail`` holds counters and skip reasons only — never raw texts,
    prompts or keys."""

    __tablename__ = "run_phases"
    __table_args__ = (
        UniqueConstraint("run_id", "phase_key", name="uq_run_phase_key"),
    )

    run_phase_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    # prepare_documents | detect_facts | formal_checks | web_research |
    # draft_fields | quality_review
    phase_key: Mapped[str] = mapped_column(String, nullable=False)
    # pending | running | succeeded | failed | skipped
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class UsageRecord(Base):
    __tablename__ = "usage_records"

    usage_record_id: Mapped[str] = mapped_column(String, primary_key=True)
    # Nullable since Milestone 9I-A: public-web-research usage is scoped to a
    # research_task, not an analysis run.
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=True, index=True
    )
    # Milestone 9I-A: research-task-scoped usage (never aggregated under run_id=null).
    research_task_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    input_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    # Exact provider usage categories; old rows intentionally remain NULL-free
    # zeroes and are marked unknown_price by their original cost status.
    cached_input_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    cache_write_input_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    # USD is the provider billing currency. CHF is a recorded SNB-reference
    # conversion used for local orientation and existing CHF run guards.
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    fx_chf_per_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_chf: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # EVAL.1 — Kostensemantik: priced | unknown_price | not_applicable.
    # cost_chf=0.0 darf NIE als "kostenlos" gelesen werden; Summen nur über
    # cost_status='priced'. Fail-closed Default: unknown_price (Backfill +
    # vergessliche Schreiber). Kein DB-Enum (Codebase-Konvention: plain String).
    cost_status: Mapped[str] = mapped_column(
        String, nullable=False, default="unknown_price",
        server_default="unknown_price",
    )
    # Version der Preistabelle, nur gesetzt wenn cost_status='priced'.
    price_version: Mapped[str | None] = mapped_column(String, nullable=True)
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
    department: Mapped[str | None] = mapped_column(String, nullable=True)
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
    # Kurze menschliche Begründung, Pflicht bei explizit unklar/nicht
    # bestätigt (API-Konsistenzregel) — fliesst NICHT in Run-Snapshots/Regeln.
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision_number: Mapped[int] = mapped_column(
        nullable=False, default=1, server_default="1"
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
    # Issue-Modell v2 (R2.2, additiv/nullable): technische Identität + Klasse
    # für Dedupe/Fix Queue. Befüllung folgt schrittweise (R2.3+).
    fingerprint: Mapped[str | None] = mapped_column(String, nullable=True)
    severity_class: Mapped[str | None] = mapped_column(String, nullable=True)
    fix_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # RUN 3C: missing-input issues are field + registry-requirement scoped.  The
    # text itself stays in ``description``; these columns contain identifiers
    # and lifecycle metadata only.
    field_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    requirement_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    missing_input_key: Mapped[str | None] = mapped_column(String, nullable=True)
    source_suggestion_id: Mapped[str | None] = mapped_column(String, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stale_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status_reason: Mapped[str | None] = mapped_column(String, nullable=True)


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
    scope: Mapped[str] = mapped_column(
        String, nullable=False, default="application", server_default="application"
    )
    rejection_reason_code: Mapped[str | None] = mapped_column(String, nullable=True)
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
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=True, index=True
    )
    project_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    research_task_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
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
    scope: Mapped[str] = mapped_column(
        String, nullable=False, default="application", server_default="application"
    )
    rejection_reason_code: Mapped[str | None] = mapped_column(String, nullable=True)
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
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=True, index=True
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
    created_by enum: template | user | agent | carried_over."""

    __tablename__ = "draft_versions"

    draft_version_id: Mapped[str] = mapped_column(String, primary_key=True)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("portal_field_drafts.draft_id"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    character_count: Mapped[int] = mapped_column(nullable=False)
    # Contract enum: agent | user | template | carried_over
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    # Internal audit only (not exposed): predecessor version + originating op.
    base_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_operation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class CopyEvent(Base):
    """Server-side record of one Innolink copy action (Slice 3, Council E2-A).

    Governance metadata only: the content_hash is taken from the copied
    DraftVersion (sha256 of its text) — the raw field text is NEVER stored
    here, and the free-text note is never mirrored into audit events."""

    __tablename__ = "copy_events"

    copy_event_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # ``portal_field`` keeps the original field/version reference. Structured
    # transfer targets are snapshot-addressed and therefore have no draft.
    target_type: Mapped[str] = mapped_column(String, nullable=False, default="portal_field")
    target_key: Mapped[str] = mapped_column(String, nullable=False, default="")
    field_id: Mapped[str | None] = mapped_column(String, nullable=True)
    draft_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    # Warning codes (open | limit | review): as reported by the client vs.
    # recomputed on the server — the union decides the override requirement.
    client_warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    server_warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Contract enum: portal_finalization | warning_not_relevant |
    # coordination_draft | other
    override_reason_code: Mapped[str | None] = mapped_column(String, nullable=True)
    # Free text only for reason "other"; max 200 chars, trimmed, event-only.
    override_reason_note: Mapped[str | None] = mapped_column(String, nullable=True)
    actor_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
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
    target_section: Mapped[str | None] = mapped_column(String, nullable=True)
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
    # Issue-Modell v2 (R2.2, additiv/nullable): stabile technische Identität
    # (R2.1-Fingerprint), sechs severity-Klassen, ableitbare Fix-Empfehlung,
    # letzter Emissionszeitpunkt. finding_code bleibt der Idempotenz-Schlüssel.
    fingerprint: Mapped[str | None] = mapped_column(String, nullable=True)
    severity_class: Mapped[str | None] = mapped_column(String, nullable=True)
    fix_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    # Nullable since Milestone 9I-A: public-web-research tool calls are scoped to a
    # research_task, not an analysis run.
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=True, index=True
    )
    # Milestone 9I-A: research-task-scoped tool invocation.
    research_task_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
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
    # Versioned professional contract. Historic rows remain nullable because
    # their role/skill split cannot be reconstructed safely.
    role_id: Mapped[str | None] = mapped_column(String, nullable=True)
    role_version: Mapped[str | None] = mapped_column(String, nullable=True)
    skill_id: Mapped[str | None] = mapped_column(String, nullable=True)
    skill_version: Mapped[str | None] = mapped_column(String, nullable=True)
    contract_version: Mapped[str | None] = mapped_column(String, nullable=True)
    # Ebene E (Live-Readiness): das vom Provider in der Antwort gemeldete
    # Modell (Alias-Auflösung). model_id bleibt das ANGEFRAGTE Modell.
    actual_model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Initial angeforderte Provider-ID. ``model_id`` bleibt der
    # Kompatibilitätswert der letzten/finalen Route.
    requested_model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    retry_count: Mapped[int] = mapped_column(nullable=False, default=0)
    termination_reason: Mapped[str | None] = mapped_column(String, nullable=True)
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
    # IDs, hashes and safe counts only; never raw source/query/prompt/draft text.
    input_artifact_refs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_by_system: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class AgentInvocationAttempt(Base):
    """One provider-route attempt; metadata only, never prompt/output text."""

    __tablename__ = "agent_invocation_attempts"
    __table_args__ = (
        UniqueConstraint(
            "invocation_id", "attempt_index", name="uq_agent_invocation_attempt_index"
        ),
    )

    attempt_id: Mapped[str] = mapped_column(String, primary_key=True)
    invocation_id: Mapped[str] = mapped_column(
        ForeignKey("agent_invocations.invocation_id"), nullable=False, index=True
    )
    attempt_index: Mapped[int] = mapped_column(nullable=False)
    retry_index: Mapped[int] = mapped_column(nullable=False, default=0)
    route_key: Mapped[str] = mapped_column(String, nullable=False)
    route_alias: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    requested_model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    actual_model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error_class: Mapped[str | None] = mapped_column(String, nullable=True)
    termination_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    estimated_cost_chf: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_cost_status: Mapped[str | None] = mapped_column(String, nullable=True)
    usage_record_id: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ProviderPreflightResult(Base):
    """Persisted, redacted synthetic route smoke result."""

    __tablename__ = "provider_preflight_results"

    preflight_id: Mapped[str] = mapped_column(String, primary_key=True)
    route_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    route_alias: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    requested_model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    actual_model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    checks_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    error_class: Mapped[str | None] = mapped_column(String, nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String, nullable=True)
    retryable: Mapped[bool] = mapped_column(nullable=False, default=False)
    configuration_fingerprint: Mapped[str | None] = mapped_column(String, nullable=True)
    registry_version: Mapped[str | None] = mapped_column(String, nullable=True)
    pricing_version: Mapped[str | None] = mapped_column(String, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    triggered_by: Mapped[str | None] = mapped_column(String, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


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
# A2 draft suggestions: advisory proposals with explicit generation provenance.
# Internal only — no public
# endpoint; surfaced through the async operation result. Immutable except the
# status/decision fields. Accepting (only) creates a new DraftVersion.
# ---------------------------------------------------------------------------


class SuggestionContextManifest(Base):
    """Versioned, metadata-only context boundary for one field suggestion.

    The rendered prompt, draft text and source quotes are deliberately not
    persisted here.  IDs, versions and hashes make the exact boundary
    reproducible and allow fail-closed staleness checks.
    """

    __tablename__ = "suggestion_context_manifests"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "field_id", "base_draft_version_id", "context_hash",
            name="uq_suggestion_manifest_context",
        ),
    )

    manifest_id: Mapped[str] = mapped_column(String, primary_key=True)
    schema_version: Mapped[str] = mapped_column(
        String, nullable=False, default="SuggestionContextManifest@v1"
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    field_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    base_draft_version_id: Mapped[str] = mapped_column(String, nullable=False)
    primary_application_source_version_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    requirement_registry_version: Mapped[str] = mapped_column(String, nullable=False)
    rule_registry_version: Mapped[str] = mapped_column(String, nullable=False)
    field_instruction_hash: Mapped[str] = mapped_column(String, nullable=False)
    improvement_mode: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False)
    selected_anchor_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_version_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    market_comparison_id: Mapped[str | None] = mapped_column(String, nullable=True)
    requirement_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rule_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String, nullable=False)
    omitted_anchor_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    component_hashes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    context_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


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
    # Ehrliche Herkunft der Ausgabe. Nullable nur fuer vor dieser Migration
    # erzeugte Zeilen, deren tatsaechlicher Adapter historisch nicht sicher
    # rekonstruiert werden kann. Neue Suggestions setzen den Wert immer.
    # rule_template | fake_demo | model_generated
    generation_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    # Composite-A2 bearbeitet genau einen Registry-Unterabschnitt. Singleton-
    # Felder bleiben null. Technische ID, nicht als Antragstext zu behandeln.
    target_section: Mapped[str | None] = mapped_column(String, nullable=True)
    # Strukturierte, advisory Abschnittsausgabe (Rationale/Fakten/Claims/Luecken).
    # Der vorgeschlagene Text bleibt zusaetzlich in suggested_text, damit der
    # bestehende HITL-Annahmepfad kompatibel bleibt.
    section_result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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
    # RUN 3C additive provenance.  Nullable fields preserve historical rows;
    # new manifest-bound suggestions populate every applicable value.
    project_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    manifest_id: Mapped[str | None] = mapped_column(
        ForeignKey("suggestion_context_manifests.manifest_id"), nullable=True, index=True
    )
    improvement_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    change_summary: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    used_rule_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    missing_inputs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    unsupported_claim_warnings: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    factual_claims: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_version_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    market_comparison_id: Mapped[str | None] = mapped_column(String, nullable=True)
    registry_version: Mapped[str | None] = mapped_column(String, nullable=True)
    output_schema_version: Mapped[str | None] = mapped_column(String, nullable=True)
    context_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    quality_state: Mapped[str | None] = mapped_column(String, nullable=True)
    stale_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    historical_status: Mapped[str | None] = mapped_column(String, nullable=True)
    accept_mode: Mapped[str] = mapped_column(
        String, nullable=False, default="legacy_partial", server_default="legacy_partial"
    )


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


# ---------------------------------------------------------------------------
# Public web research (Milestone 9I-A): ResearchTask + ResearchResult
# ---------------------------------------------------------------------------


class ResearchBrief(Base):
    """Versionierter, vom Menschen freigegebener public-safe Recherchebrief.

    Der Brief enthält ausschliesslich abstrakte Suchdeskriptoren. Rohprojekttext,
    Partnernamen, Budgets und Kontaktangaben gehören nie in diese Tabelle.
    """

    __tablename__ = "research_briefs"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "version", name="uq_research_briefs_project_version"
        ),
    )

    research_brief_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False)
    # draft | approved | superseded
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    research_goal: Mapped[str] = mapped_column(String, nullable=False, default="")
    search_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    application_domain: Mapped[str] = mapped_column(String, nullable=False, default="")
    technology_class: Mapped[str] = mapped_column(String, nullable=False, default="")
    target_customer_segments: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    region: Mapped[str] = mapped_column(String, nullable=False, default="")
    competence_needs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    modules: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class ResearchTask(Base):
    """Explicit, user-initiated public web research task (Domain Model
    ResearchTask). Internal table; the public surface is the openapi ResearchTask
    schema. ``query_text`` only ever holds the server-loaded, human-approved public-safe
    query — never raw confidential/internal project text."""

    __tablename__ = "research_tasks"

    research_task_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    operation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Controlled enum: partner_role_suggestion | competence_gap_analysis |
    # publication_track_record (openapi ResearchTaskCreate.purpose).
    purpose: Mapped[str] = mapped_column(String, nullable=False)
    research_brief_id: Mapped[str | None] = mapped_column(
        ForeignKey("research_briefs.research_brief_id"), nullable=True, index=True
    )
    research_module: Mapped[str | None] = mapped_column(String, nullable=True)
    planner_purpose: Mapped[str | None] = mapped_column(String, nullable=True)
    # person | organisation | topic
    subject_type: Mapped[str] = mapped_column(String, nullable=False)
    subject_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # Server-loaded sanitized query from SearchQueryApproval.
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query_hash: Mapped[str] = mapped_column(String, nullable=False)
    # queued | running | succeeded | failed | blocked | cancelled
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    preferred_domains: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    disallowed_domains: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    competence_needs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    requested_partner_roles: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    max_results: Mapped[int] = mapped_column(nullable=False, default=10)
    max_pages: Mapped[int] = mapped_column(nullable=False, default=1)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    # fake_demo | live; null solange noch kein Provider erfolgreich geantwortet hat.
    execution_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_count: Mapped[int] = mapped_column(nullable=False, default=0)
    # Advisory A1 public-competence synthesis state (non-blocking): null | succeeded |
    # failed | skipped. Used to enforce at-most-one successful synthesis per task.
    a1_synthesis_status: Mapped[str | None] = mapped_column(String, nullable=True)
    internal_public_confirmation_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    # Milestone 9J — Search Query Firewall provenance. ``firewall_data_class`` is the
    # derived D0–D3/UNKNOWN class at creation; ``firewall_approval_id`` links the
    # single-use sanitized-query approval consumed for new D0/D1/D2 brief tasks.
    firewall_data_class: Mapped[str | None] = mapped_column(String, nullable=True)
    firewall_approval_id: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    safe_error_detail: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ResearchResult(Base):
    """A public web search candidate (Domain Model ResearchResult). Snippets are
    NOT evidence; a result becomes source material only after explicit import as a
    SourceDocument. ``professional_evidence`` / ``partner_role_suggestions`` hold
    advisory A1 synthesis output (human-review required)."""

    __tablename__ = "research_results"

    result_id: Mapped[str] = mapped_column(String, primary_key=True)
    research_task_id: Mapped[str] = mapped_column(
        ForeignKey("research_tasks.research_task_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    final_url: Mapped[str | None] = mapped_column(String, nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    publisher: Mapped[str | None] = mapped_column(String, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_category: Mapped[str | None] = mapped_column(String, nullable=True)
    # Preliminary metadata only; it is not an evidence or correctness decision.
    source_quality: Mapped[str] = mapped_column(
        String, nullable=False, default="unassessed"
    )
    potential_sections: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Coverage (located text), deterministic support and human content review are
    # intentionally independent states.
    coverage_status: Mapped[str] = mapped_column(
        String, nullable=False, default="not_checked"
    )
    support_status: Mapped[str] = mapped_column(
        String, nullable=False, default="not_checked"
    )
    content_review_status: Mapped[str] = mapped_column(
        String, nullable=False, default="unreviewed"
    )
    provider_rank: Mapped[int | None] = mapped_column(nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    fetched_content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    fetched_content_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    content_safety_status: Mapped[str] = mapped_column(
        String, nullable=False, default="not_checked"
    )
    quarantine_reason_code: Mapped[str | None] = mapped_column(String, nullable=True)
    possible_duplicate_source_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    partner_candidate_status: Mapped[str | None] = mapped_column(String, nullable=True)
    eligibility_status: Mapped[str] = mapped_column(
        String, nullable=False, default="not_checked"
    )
    eligibility_anchor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    eligibility_source_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    eligibility_official_url: Mapped[str | None] = mapped_column(String, nullable=True)
    eligibility_source_location: Mapped[str | None] = mapped_column(String, nullable=True)
    eligibility_last_checked: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    eligibility_reviewed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    eligibility_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # candidate | imported | rejected | failed
    status: Mapped[str] = mapped_column(String, nullable=False, default="candidate")
    # not_applicable | matched | ambiguous | unresolved
    identity_match_status: Mapped[str] = mapped_column(
        String, nullable=False, default="not_applicable"
    )
    source_document_id: Mapped[str | None] = mapped_column(String, nullable=True)
    professional_evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    partner_role_suggestions: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    safe_error_detail: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# Market & competitor comparison (Milestone 9I-B): beta-internal, built only from
# imported public sources. No finalized contract object — internal tables only.
# ---------------------------------------------------------------------------


class MarketComparison(Base):
    """A structured market/competitor comparison built from imported public sources
    (Domain has no contract object — beta-internal). Run-nullable; evidence comes from
    standalone deterministic quote verification, never from snippets/provider payloads."""

    __tablename__ = "market_comparisons"

    comparison_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # Comparison is decoupled from any analysis run (rule: no run coupling).
    run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    research_task_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    research_brief_id: Mapped[str | None] = mapped_column(String, nullable=True)
    query_approval_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_version_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # draft | ready_for_review | stale | failed
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    # Comparison-level open questions / caveats from the structuring step (advisory).
    research_gaps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    comparison_version: Mapped[int] = mapped_column(nullable=False, default=1)
    source_scope_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    model_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    context_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    stale_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    consequences: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Once-per-comparison generation guard: null | succeeded | failed | skipped.
    generation_status: Mapped[str | None] = mapped_column(String, nullable=True)
    # fake_demo | model_generated | deterministic; truthful provenance is required
    # before a comparison can enter the A2 drafting context.
    generation_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    operation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    safe_error_detail: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class MarketComparisonItem(Base):
    """One comparison row. Each item is either source_backed (>=1 verified quote ref)
    or needs_human_review / insufficient_evidence. ``verified_quote_refs`` carries the
    standalone deterministic verification; ``linked_evidence_anchor_id`` is set only when
    a pre-existing EvidenceAnchor already covers the span (never fabricated)."""

    __tablename__ = "market_comparison_items"

    item_id: Mapped[str] = mapped_column(String, primary_key=True)
    comparison_id: Mapped[str] = mapped_column(
        ForeignKey("market_comparisons.comparison_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    name_normalized: Mapped[str] = mapped_column(String, nullable=False)
    # competitor | alternative_solution | substitute | incumbent_process |
    # reference_solution | market_size_claim | customer_problem (R8) | unknown
    category: Mapped[str] = mapped_column(String, nullable=False, default="unknown")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_customer_segment: Mapped[str | None] = mapped_column(String, nullable=True)
    offering_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)
    weaknesses: Mapped[str | None] = mapped_column(Text, nullable=True)
    differentiation_relevance: Mapped[str | None] = mapped_column(Text, nullable=True)
    # similar | complementary | competing | reference | unclear
    relation_to_project: Mapped[str] = mapped_column(
        String, nullable=False, default="unclear"
    )
    # source_backed | needs_review | insufficient_evidence
    confidence_label: Mapped[str] = mapped_column(
        String, nullable=False, default="insufficient_evidence"
    )
    # proposed | accepted | rejected | needs_human_review
    status: Mapped[str] = mapped_column(String, nullable=False, default="proposed")
    source_document_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # list of verified-quote reference dicts (rule 6). Never search snippets.
    verified_quote_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence_anchor_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    cell_evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    uncertainty: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Lösungstyp, Zentralität, Daten-/Zugriffsmodell und Schweizer Bezug.
    comparison_dimensions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Exakte Fundstelle und fachliche Stützung bleiben getrennt.
    coverage_status: Mapped[str | None] = mapped_column(String, nullable=True)
    support_status: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# Search Query Firewall approvals (Milestone 9J): beta-internal privacy control.
# A single-use record of a firewall decision for a D1/D2 web-research query. The RAW
# query is NEVER stored — only its hash + the sanitized public-safe query + a redaction
# summary (categories/counts, no raw values). Changing the query changes the hash and
# invalidates the approval. Workspace-scoped.
# ---------------------------------------------------------------------------


class SearchQueryApproval(Base):
    """A firewall decision + (for confidential classes) a human approval of a sanitized
    query. Never stores raw D1/D2/D3 query text (only ``raw_query_hash``)."""

    __tablename__ = "search_query_approvals"

    approval_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    actor_user_id: Mapped[str] = mapped_column(String, nullable=False)
    # firecrawl | web_research (intended tool for the sanitized query).
    intended_tool: Mapped[str] = mapped_column(String, nullable=False)
    purpose: Mapped[str | None] = mapped_column(String, nullable=True)
    research_brief_id: Mapped[str | None] = mapped_column(
        ForeignKey("research_briefs.research_brief_id"), nullable=True, index=True
    )
    research_module: Mapped[str | None] = mapped_column(String, nullable=True)
    planner_purpose: Mapped[str | None] = mapped_column(String, nullable=True)
    # D0_PUBLIC | D1_INTERNAL | D2_CONFIDENTIAL_IDEA | D3_NDA_BLOCKED | UNKNOWN
    data_class: Mapped[str] = mapped_column(String, nullable=False)
    # SHA256 of the normalized RAW query. The raw query itself is never persisted.
    raw_query_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    sanitized_query: Mapped[str] = mapped_column(Text, nullable=False)
    risk_score: Mapped[int] = mapped_column(nullable=False, default=0)
    # firewall decision: allow | require_human_approval | block
    decision: Mapped[str] = mapped_column(String, nullable=False)
    reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # [{category, label, count}] — never raw removed values.
    redaction_summary: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # pending | approved | rejected | expired | used
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    used_by_research_task_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ---------------------------------------------------------------------------
# MAS reliability & value assurance (Milestone 9K): beta-internal, run-scoped.
# Deterministic claim extraction + lineage + evidence-sufficiency + a per-run quality
# summary. No finalized contract object. Reliability findings reuse ReviewFinding
# (source="agent", profile_id="M9K.reliability_assurance"). ``claim_text`` is internal
# only (same sensitivity as DraftVersion.text) — never in audit/logs/export.
# ---------------------------------------------------------------------------


class DraftClaim(Base):
    """A single claim-like statement extracted from a run's current DraftVersion text.
    Deterministic + position-aware ``claim_id`` so re-running a pass upserts rather than
    duplicates. ``source_scope_hash`` binds the claim to the pass that produced it."""

    __tablename__ = "draft_claims"

    claim_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    draft_id: Mapped[str] = mapped_column(String, nullable=False)
    draft_version_id: Mapped[str] = mapped_column(String, nullable=False)
    field_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    start_char: Mapped[int] = mapped_column(nullable=False, default=0)
    end_char: Mapped[int] = mapped_column(nullable=False, default=0)
    # Internal-only; same sensitivity as DraftVersion.text. Never audited/logged/exported.
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    # market | innovation | technical | partner_fit | value_creation | requirement |
    # budget | generic
    claim_type: Mapped[str] = mapped_column(String, nullable=False, default="generic")
    # strong | moderate | weak
    strength: Mapped[str] = mapped_column(String, nullable=False, default="moderate")
    requires_evidence: Mapped[bool] = mapped_column(nullable=False, default=True)
    # deterministic_sentence_rule | agent_assisted_if_available
    extraction_method: Mapped[str] = mapped_column(
        String, nullable=False, default="deterministic_sentence_rule"
    )
    source_text_hash: Mapped[str] = mapped_column(String, nullable=False)
    # Binds the claim to its reliability pass (the RunQualitySummary.source_scope_hash).
    source_scope_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class ClaimLineage(Base):
    """Per-claim provenance mapping + deterministic evidence-sufficiency status. One row
    per DraftClaim. Never framed as semantic proof — ``sufficiency_status`` is an evidence
    sufficiency *check* under defined criteria (needs human review when uncertain)."""

    __tablename__ = "claim_lineages"

    lineage_id: Mapped[str] = mapped_column(String, primary_key=True)
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("draft_claims.claim_id"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # direct_evidence | indirect_evidence | weak_evidence | no_evidence |
    # conflicting_evidence | needs_human_review
    lineage_status: Mapped[str] = mapped_column(
        String, nullable=False, default="no_evidence"
    )
    # supports_claim | weakly_supports_claim | does_not_support_claim |
    # insufficient_evidence | needs_human_review
    sufficiency_status: Mapped[str] = mapped_column(
        String, nullable=False, default="insufficient_evidence"
    )
    # {extracted_fact_ids, evidence_anchor_ids, evidence_candidate_ids,
    #  source_fragment_ids, draft_suggestion_id, market_item_ids, a3_finding_ids}
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    matched_terms: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class RunQualitySummary(Base):
    """Deterministic per-run quality/reliability metrics for M10 evaluation. Coverage and
    sufficiency are kept as SEPARATE metrics. Stale when any scoped input changes; a stale
    summary must not be used as current quality evidence."""

    __tablename__ = "run_quality_summaries"

    summary_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.run_id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    operation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # current | stale | failed
    status: Mapped[str] = mapped_column(String, nullable=False, default="current")
    # Excludes this pass's own M9K findings (corr 11) so a pass never staleifies itself.
    source_scope_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    claim_count: Mapped[int] = mapped_column(nullable=False, default=0)
    supported_claims: Mapped[int] = mapped_column(nullable=False, default=0)
    weakly_supported_claims: Mapped[int] = mapped_column(nullable=False, default=0)
    unsupported_claims: Mapped[int] = mapped_column(nullable=False, default=0)
    conflicting_claims: Mapped[int] = mapped_column(nullable=False, default=0)
    # Coverage = fraction of evidence-requiring claims with ANY linked evidence.
    evidence_coverage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Correctness = sufficiency pass-rate over the checked sample (distinct from coverage).
    evidence_correctness_sample_size: Mapped[int] = mapped_column(nullable=False, default=0)
    evidence_correctness_sample_pass_rate: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    review_required_count: Mapped[int] = mapped_column(nullable=False, default=0)
    blocker_count: Mapped[int] = mapped_column(nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(nullable=False, default=0)
    fields_ready: Mapped[int] = mapped_column(nullable=False, default=0)
    fields_needs_review: Mapped[int] = mapped_column(nullable=False, default=0)
    false_consensus_risk_count: Mapped[int] = mapped_column(nullable=False, default=0)
    semantic_drift_count: Mapped[int] = mapped_column(nullable=False, default=0)
    raw_logging_detected: Mapped[bool] = mapped_column(nullable=False, default=False)
    tool_leakage_detected: Mapped[bool] = mapped_column(nullable=False, default=False)
    # ok | risky (high coverage + low sufficiency ⇒ risky, not success).
    quality_flag: Mapped[str] = mapped_column(String, nullable=False, default="ok")
    cost_chf: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_placeholder: Mapped[bool] = mapped_column(nullable=False, default=True)
    latency_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary_version: Mapped[str] = mapped_column(String, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
