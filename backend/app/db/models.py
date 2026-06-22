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
    String,
    Text,
    UniqueConstraint,
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
