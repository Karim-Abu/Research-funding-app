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
    run_classification_source_merge_enabled: bool = True

    # Draft carry-over (Slice 2, Council E1-A): a new run reuses the latest
    # meaningful (user/agent/carried_over) draft version of the newest prior
    # run per field instead of rebuilding the template. Off → template-only.
    draft_carry_over_enabled: bool = True

    # Copy governance (Slice 3, Council E2-A): the Innolink copy view records a
    # server-side CopyEvent per copy. Off → the UI copies without a server call
    # (today's behavior); the endpoint itself stays active.
    copy_events_enabled: bool = True

    # Deterministic exports (Milestone 8) --------------------------------
    export_storage_dir: str = "var/exports"
    max_export_bytes: int = 25 * 1024 * 1024
    export_generation_timeout_seconds: int = 60
    max_exports_per_run_and_type: int = 5
    max_export_concurrency: int = 2

    # Agent infrastructure (Milestone 9A) — keys are env-only, never defaulted
    # to a real value, never logged. Missing keys never break startup; the route
    # is simply marked unavailable and the fake provider is used.
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    # External cloud processing of internal real-project data requires an
    # institutionally approved provider route. Not approved in the beta.
    agent_institutional_route_approved: bool = False
    # Optional, env-gated real-provider smoke test (never required for CI).
    run_real_provider_smoke: bool = False
    # Milestone 9B: explicit A1 context character budget (payload minimization,
    # in addition to the profile's max_input_fragments). Deterministic truncation
    # at fragment boundaries keeps the model-facing payload minimal.
    a1_context_char_budget: int = 24000
    # Milestone 9D: dev/test-only deterministic fake agent provider for A2 draft
    # suggestions (no network/key). Off in production — A2 then uses the real
    # adapters and is simply unavailable without a configured key.
    agent_fake_provider: bool = False
    # R4.3 (Owner-Tabelle §3.1): "real" erlaubt direkte OpenAI/Anthropic-Calls
    # AUSSCHLIESSLICH für synthetische/anonymisierte Evaluationsfälle (F1
    # synthetic) — nie für echte D1/D2-Daten. Default off; das Setzen der
    # Variable gilt als dokumentierte Owner-Freigabe für den Evaluationslauf.
    ai_eval_mode: Literal["off", "real"] = "off"

    # Milestone 9I-A: public web research. Keys are env-only, never defaulted/logged.
    # web_research_enabled gates the whole feature; a missing Firecrawl key + no fake
    # simply reports the feature unavailable (no crash). The web fake provider has its
    # OWN flag — it is NOT implied by agent_fake_provider (binding correction 5).
    web_research_enabled: bool = False
    firecrawl_api_key: str | None = None
    web_research_fake_provider: bool = False
    # Milestone 9J: even an approved, firewall-sanitized D2 (confidential) query must not
    # reach a LIVE web provider unless this flag is explicitly enabled. Default off; the
    # D2 sanitized-query flow otherwise routes to the fake provider / is blocked. D0
    # public/synthetic web research is unaffected (stays live-capable).
    d2_web_research_enabled: bool = False
    # Deployment/technical limits for web research (NOT funding rules).
    web_search_max_results: int = 10
    web_fetch_max_bytes: int = 5 * 1024 * 1024
    web_fetch_max_redirects: int = 5
    web_research_timeout_seconds: int = 60
    web_research_max_credits: int = 50

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
