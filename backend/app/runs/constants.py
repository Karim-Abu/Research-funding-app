"""Canonical run constants for the minimal M3 technical workflow."""
from __future__ import annotations

# Subset of the 12 canonical contract stages used by the minimal M3 graph.
M3_STAGES = ["initialize", "validate_source_snapshot", "finalize_run"]

# Technical progress per stage — NOT proposal-analysis progress.
STAGE_PROGRESS = {
    "initialize": 33,
    "validate_source_snapshot": 66,
    "finalize_run": 100,
}

ACTIVE_RUN_STATUSES = ("created", "running", "paused_for_review")
TERMINAL_RUN_STATUSES = ("completed", "stopped", "failed", "cancelled")
TERMINAL_OPERATION_STATUSES = ("succeeded", "failed", "cancelled")

# Frozen contract/registry versions (openapi x-contracts + M2 deterministic
# parser/normalizer/chunker versions). Stored immutably on each run.
SNAPSHOT_VERSIONS = {
    "funding_instrument_profile_version": "1.1.0",
    "portal_field_profile_version": "1.1.0",
    "rule_registry_version": "1.1.0",
    "data_policy_version": "1.1.0",
    "tool_registry_version": "1.1.0",
    "agent_registry_version": "1.1.0",
    "prompt_versions": {},
    "model_ids": [],
    "parser_version": "parser-1",
    "normalizer_version": "normalizer-1",
    "chunker_version": "chunker-1",
    "requirement_registry_version": "1.0.0",
    "control_registry_version": "1.0.0",
    "schema_catalog_version": "1.0.0",
}
