"""Typed application settings loaded from environment / backend/.env.

Secrets (seed passwords) come from the environment; the defaults here are
local-dev only and are documented in the README. Never commit real secrets.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database -----------------------------------------------------------
    database_url: str = "sqlite:///./app.db"
    app_env: Literal["development", "test", "production"] = "development"
    demo_data_enabled: bool = False

    # Version reporting (resolved from final_backend_contracts_v1_1) -------
    api_version: str = "1.1.0"
    policy_version: str = "1.1.0"
    agent_registry_version: str = "1.1.0"
    rule_registry_version: str = "1.1.0"
    requirement_registry_version: str = "1.0.0"
    tool_registry_version: str = "1.1.0"

    # Requirement / Rule registry (Milestone 4). Resolved relative to the repo
    # root by the loader when unset; override for tests/alternate layouts.
    contracts_dir: str | None = None

    # Session / cookie ---------------------------------------------------
    session_cookie_name: str = "rf_session"
    session_ttl_seconds: int = 60 * 60 * 8
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    # CSRF / Origin ------------------------------------------------------
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Capabilities -------------------------------------------------------
    polling_interval_seconds: int = 2
    # URL import is not implemented in this milestone (Firecrawl out of scope).
    supported_source_types: list[str] = ["pdf", "docx", "txt"]
    url_import_enabled: bool = False

    # Source ingestion — deployment/technical limits (NOT funding rules) -----
    source_storage_dir: str = "var/sources"
    max_upload_bytes: int = 10 * 1024 * 1024
    max_files_per_request: int = 10
    max_total_request_bytes: int = 50 * 1024 * 1024
    max_archive_entries: int = 256
    max_expanded_archive_bytes: int = 50 * 1024 * 1024
    max_parsing_concurrency: int = 2

    # Deterministic evidence baseline (Milestone 5) ----------------------
    evidence_max_candidates_per_requirement: int = 3

    # Run orchestration (Milestone 3) ------------------------------------
    checkpoint_db_path: str = "var/checkpoints.db"
    max_run_concurrency: int = 2
    run_default_max_retries: int = 1
    run_default_max_redrafts: int = 2
    run_default_timeout_seconds: int = 600

    # Deterministic exports (Milestone 8) --------------------------------
    export_storage_dir: str = "var/exports"
    max_export_bytes: int = 25 * 1024 * 1024
    export_generation_timeout_seconds: int = 60
    max_exports_per_run_and_type: int = 5
    max_export_concurrency: int = 2

    # Seed data (dev defaults; override via env) -------------------------
    seed_workspace_id: str = "ws-demo"
    seed_workspace_name: str = "Demo Workspace"
    seed_funding_profile_id: str = "innosuisse_innovation_project_with_implementation_partner"
    seed_funding_profile_title: str = "Innosuisse Innovation Project (with implementation partner)"
    seed_lead_admin_email: str = "anna.keller@example.test"
    seed_lead_admin_name: str = "Anna Keller"
    seed_lead_admin_password: str = "changeme-dev-lead"
    seed_member_email: str = "tobias.frei@example.test"
    seed_member_name: str = "Tobias Frei"
    seed_member_password: str = "changeme-dev-member"

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
