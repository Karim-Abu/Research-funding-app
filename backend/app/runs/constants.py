"""Canonical run constants for the deterministic precheck workflow."""
from __future__ import annotations

# Subset of the 12 canonical contract stages. M5 adds the deterministic evidence
# baseline (extract_facts_and_map_evidence with A1 disabled, then verify_evidence)
# before requirement evaluation. Drafting/review stages remain out of scope.
WORKFLOW_STAGES = [
    "initialize",
    "validate_source_snapshot",
    "extract_facts_and_map_evidence",
    "verify_evidence",
    "evaluate_requirements_and_rules",
    "draft_fields",
    "create_template_drafts",
    "finalize_run",
]

# Technical progress per stage — covers the deterministic precheck + evidence
# baseline + deterministic template drafts. NOT a complete/reviewed proposal
# (no AI drafting, critic, review, approval or submission gate).
STAGE_PROGRESS = {
    "initialize": 12,
    "validate_source_snapshot": 25,
    "extract_facts_and_map_evidence": 37,
    "verify_evidence": 50,
    "evaluate_requirements_and_rules": 62,
    "draft_fields": 75,
    "create_template_drafts": 87,
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
