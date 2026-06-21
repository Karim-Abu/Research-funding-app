"""Typed application settings loaded from environment / backend/.env.

Secrets (seed passwords) come from the environment; the defaults here are
local-dev only and are documented in the README. Never commit real secrets.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database -----------------------------------------------------------
    database_url: str = "sqlite:///./app.db"

    # Version reporting (resolved from final_backend_contracts_v1_1) -------
    api_version: str = "1.1.0"
    policy_version: str = "1.1.0"
    agent_registry_version: str = "1.1.0"
    rule_registry_version: str = "1.1.0"
    tool_registry_version: str = "1.1.0"

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
    max_upload_bytes: int | None = 10 * 1024 * 1024
    supported_source_types: list[str] = ["pdf", "docx", "txt", "url"]

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
