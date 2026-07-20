"""Milestone 10 — migration hardening.

Runs the REAL Alembic migrations (subprocess `python -m alembic`) against a throwaway
temp SQLite DB — distinct from the ``Base.metadata.create_all`` test DB used elsewhere —
so a fresh production-style DB is exercised. Covers a fresh upgrade, an existing at-head
no-op upgrade + row-preservation hardening check, and a latest-migration
down/up roundtrip. Inspected with stdlib ``sqlite3`` to stay independent of app settings.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
_KEY_TABLES = {
    "projects", "source_documents", "source_versions", "analysis_runs",
    "portal_field_drafts", "draft_versions", "evidence_anchors", "evidence_links",
    "review_findings", "search_query_approvals", "market_comparisons",
    "draft_claims", "claim_lineages", "run_quality_summaries", "copy_events",
    "research_briefs",
    "import_candidate_revisions", "structured_import_candidate_revisions",
    "project_field_revisions",
}
_HEAD = "f7b9d2c4a681"  # RUN 2B revisions and formal evidence scope.


def _alembic(db_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["APP_ENV"] = "test"
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=_BACKEND, env=env, capture_output=True, text=True, timeout=300,
    )


def _tables(db_path: Path) -> set[str]:
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    finally:
        con.close()
    return {r[0] for r in rows}


def _columns(db_path: Path, table: str) -> set[str]:
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    finally:
        con.close()
    return {r[1] for r in rows}


def _project_columns(db_path: Path) -> set[str]:
    return _columns(db_path, "projects")


# R2.2 — die additiven Issue-Modell-v2-Spalten (zwei Revisionen unter Head).
_FINDING_V2_COLUMNS = {
    "fingerprint", "severity_class", "fix_recommendation", "last_seen_at",
}

# EVAL.1 — die additiven Kostensemantik-Spalten der Head-Migration.
_USAGE_COST_COLUMNS = {"cost_status", "price_version"}

# v2-Vertragsmetadaten sind additiv und enthalten ausschliesslich sichere IDs,
# Hashes und Zählwerte (nie Prompt-, Query- oder Entwurfstext).
_ROLE_SKILL_COLUMNS = {
    "role_id", "role_version", "skill_id", "skill_version",
    "contract_version", "input_artifact_refs",
}

_LIVE_INVOCATION_COLUMNS = {
    "requested_model_id", "retry_count", "termination_reason",
}

_LIVE_RUN_COLUMNS = {"live_execution_status", "live_status_reason"}

_LIVE_RESEARCH_RESULT_COLUMNS = {
    "publisher", "published_at", "source_category", "source_quality",
    "potential_sections", "coverage_status", "support_status",
    "content_review_status",
}


def _head_version(db_path: Path) -> str | None:
    con = sqlite3.connect(db_path)
    try:
        row = con.execute("SELECT version_num FROM alembic_version").fetchone()
    finally:
        con.close()
    return row[0] if row else None


def test_fresh_db_upgrade_head(tmp_path):
    db = tmp_path / "fresh.db"
    result = _alembic(db, "upgrade", "head")
    assert result.returncode == 0, result.stderr
    assert _head_version(db) == _HEAD
    assert _ROLE_SKILL_COLUMNS <= _columns(db, "agent_invocations")
    assert _LIVE_INVOCATION_COLUMNS <= _columns(db, "agent_invocations")
    assert _LIVE_RUN_COLUMNS <= _columns(db, "analysis_runs")
    assert "source_url" in _columns(db, "source_documents")
    assert _LIVE_RESEARCH_RESULT_COLUMNS <= _columns(db, "research_results")
    assert "generation_kind" in _columns(db, "market_comparisons")
    assert {"primary_application_source_id", "field_revision_number"} <= _project_columns(db)
    assert "revision_number" in _columns(db, "partners")
    assert {"current_revision_id", "revision_number"} <= _columns(
        db, "import_candidates"
    )
    assert {"current_revision_id", "revision_number"} <= _columns(
        db, "structured_import_candidates"
    )
    assert {"scope", "rejection_reason_code"} <= _columns(db, "evidence_candidates")
    assert {"scope", "rejection_reason_code"} <= _columns(db, "evidence_anchors")
    assert {"agent_invocation_attempts", "provider_preflight_results"} <= _tables(db)
    assert {
        "requested_model_id", "actual_model_id", "retry_index",
        "termination_reason", "estimated_cost_chf", "estimated_cost_status",
    } <= _columns(db, "agent_invocation_attempts")
    missing = _KEY_TABLES - _tables(db)
    assert not missing, f"missing tables after fresh upgrade: {missing}"
    # App connectivity smoke: the migrated DB is a valid, queryable schema.
    con = sqlite3.connect(db)
    try:
        assert con.execute("SELECT 1").fetchone() == (1,)
    finally:
        con.close()


def test_existing_db_upgrade_is_noop_and_preserves_data(tmp_path):
    """An at-head upgrade is a no-op and must preserve existing rows."""
    db = tmp_path / "existing.db"
    assert _alembic(db, "upgrade", "head").returncode == 0
    con = sqlite3.connect(db)
    try:
        con.execute(
            "INSERT INTO workspaces (id, name, created_at) "
            "VALUES ('ws-m10', 'M10 Existing', '2026-01-01T00:00:00+00:00')"
        )
        con.commit()
    finally:
        con.close()
    # Re-run upgrade head — a no-op for M10.
    assert _alembic(db, "upgrade", "head").returncode == 0
    assert _head_version(db) == _HEAD
    con = sqlite3.connect(db)
    try:
        row = con.execute(
            "SELECT name FROM workspaces WHERE id='ws-m10'"
        ).fetchone()
    finally:
        con.close()
    assert row == ("M10 Existing",), "existing core row lost across a no-op upgrade"


def test_latest_migration_downgrade_upgrade_roundtrip(tmp_path):
    """Roundtrip der additiven Recherchebrief-/Provenienzmigration."""
    db = tmp_path / "roundtrip.db"
    assert _alembic(db, "upgrade", "head").returncode == 0
    assert "run_phases" in _tables(db)
    assert {
        "run_phase_id", "run_id", "phase_key", "status", "error_code",
        "detail", "started_at", "ended_at", "created_at", "updated_at",
    } <= _columns(db, "run_phases")
    assert "import_candidates" in _tables(db)
    assert "edited_text" in _columns(db, "import_candidates")
    assert {"mapping_version", "mapping_status", "section_metadata"} <= _columns(
        db, "import_candidates"
    )
    assert "structured_import_candidates" in _tables(db)
    assert {
        "candidate_id", "workspace_id", "project_id",
        "source_id", "source_version_id", "candidate_kind", "target_key",
        "payload_json", "edited_payload_json", "confidence", "source_location",
        "mapping_version", "decision", "decided_by", "decided_at",
        "applied_resource_id", "supersedes_candidate_id", "created_at",
    } <= _columns(db, "structured_import_candidates")
    assert {"title_en", "start_date", "end_date", "total_requested_funding_including_overhead"} <= _project_columns(db)
    assert "department" in _columns(db, "partners")
    assert "review_comment" in _columns(db, "partners")
    assert {"generation_kind", "target_section", "section_result_json"} <= _columns(
        db, "draft_suggestions"
    )
    assert "target_section" in _columns(db, "review_findings")
    assert {
        "research_brief_id", "research_module", "planner_purpose", "execution_mode",
    } <= _columns(db, "research_tasks")
    assert {
        "research_brief_id", "research_module", "planner_purpose",
    } <= _columns(db, "search_query_approvals")
    assert {
        "comparison_dimensions", "coverage_status", "support_status",
    } <= _columns(db, "market_comparison_items")
    assert _USAGE_COST_COLUMNS <= _columns(db, "usage_records")
    assert _FINDING_V2_COLUMNS <= _columns(db, "review_findings")
    assert _FINDING_V2_COLUMNS <= _columns(db, "open_issues")
    assert {
        "import_candidate_revisions",
        "structured_import_candidate_revisions",
        "project_field_revisions",
    } <= _tables(db)
    assert {"current_revision_id", "revision_number"} <= _columns(
        db, "import_candidates"
    )
    # Row preservation across the roundtrip: bestehende Zeilen (usage_records,
    # ImportCandidate mit edited_text, Partner mit review_comment) müssen den
    # Downgrade + Upgrade der Head-Migration unverändert überleben; die
    # run_phases-Zeile bleibt erhalten; nur die neuen Importspalten verschwinden.
    con = sqlite3.connect(db)
    try:
        con.execute(
            "INSERT INTO usage_records (usage_record_id, workspace_id,"
            " input_tokens, output_tokens, cost_chf, cost_status, created_at)"
            " VALUES ('usg-eval1', 'ws-m10', 11, 22, 0.0, 'not_applicable',"
            " '2026-01-01T00:00:00+00:00')"
        )
        con.execute(
            "INSERT INTO import_candidates (import_candidate_id, workspace_id,"
            " project_id, source_id, source_version_id, field_id,"
            " extracted_text, edited_text, confidence, decision, created_at)"
            " VALUES ('cand-rt', 'ws-m10', 'p-rt', 's-rt', 'sv-rt',"
            " 'INTRO.APP.ABSTRACT', 'Original', 'Bearbeitet', 'found',"
            " 'accepted', '2026-01-01T00:00:00+00:00')"
        )
        con.execute(
            "INSERT INTO partners (partner_id, project_id, workspace_id, name,"
            " partner_type, review_comment, created_by, created_at, updated_at)"
            " VALUES ('prt-rt', 'p-rt', 'ws-m10', 'Industrie AG',"
            " 'implementation_partner', 'Begründung', 'u-rt',"
            " '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
        )
        con.execute(
            "INSERT INTO run_phases (run_phase_id, run_id, phase_key, status,"
            " detail, created_at, updated_at)"
            " VALUES ('rp-rt', 'run-rt', 'prepare_documents', 'succeeded',"
            " '{}', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
        )
        con.commit()
    finally:
        con.close()
    # Down one entfernt nur die additive Live-Routing-Ebene. Alle übrigen
    # Strukturen (inkl. Rollen-/Skill-, Recherchebrief- und
    # Copy-Event-Migrationen) sowie alle Bestandsdaten bleiben erhalten.
    assert _alembic(db, "downgrade", "-1").returncode == 0
    assert _ROLE_SKILL_COLUMNS <= _columns(db, "agent_invocations")
    assert _LIVE_INVOCATION_COLUMNS <= _columns(db, "agent_invocations")
    assert _LIVE_RUN_COLUMNS <= _columns(db, "analysis_runs")
    assert {"agent_invocation_attempts", "provider_preflight_results"} <= _tables(db)
    assert "source_url" in _columns(db, "source_documents")
    assert _LIVE_RESEARCH_RESULT_COLUMNS <= _columns(db, "research_results")
    assert "generation_kind" in _columns(db, "market_comparisons")
    assert "actual_model_id" in _columns(db, "agent_invocations")
    assert "research_briefs" in _tables(db)
    assert {"research_brief_id", "research_module", "planner_purpose"} <= _columns(
        db, "research_tasks"
    )
    assert "run_phases" in _tables(db)
    assert {"mapping_version", "mapping_status", "section_metadata"} <= _columns(
        db, "import_candidates"
    )
    assert "structured_import_candidates" in _tables(db)
    assert {
        "title_en", "start_date", "end_date",
        "total_requested_funding_including_overhead",
    } <= _project_columns(db)
    assert "department" in _columns(db, "partners")
    assert {"generation_kind", "target_section", "section_result_json"} <= _columns(
        db, "draft_suggestions"
    )
    assert "target_section" in _columns(db, "review_findings")
    assert "review_comment" in _columns(db, "partners")
    assert "edited_text" in _columns(db, "import_candidates")
    assert _USAGE_COST_COLUMNS <= _columns(db, "usage_records")
    assert "import_candidates" in _tables(db)
    assert _FINDING_V2_COLUMNS <= _columns(db, "review_findings")
    assert _FINDING_V2_COLUMNS <= _columns(db, "open_issues")
    assert "copy_events" in _tables(db)
    assert "cash_contribution" in _project_columns(db)
    assert "duration_months" in _project_columns(db)
    assert "run_quality_summaries" in _tables(db)
    assert not {
        "import_candidate_revisions",
        "structured_import_candidate_revisions",
        "project_field_revisions",
    } & _tables(db)
    assert not {"current_revision_id", "revision_number"} & _columns(
        db, "import_candidates"
    )
    assert "revision_number" not in _columns(db, "partners")
    assert "primary_application_source_id" not in _project_columns(db)
    assert not {"scope", "rejection_reason_code"} & _columns(
        db, "evidence_candidates"
    )
    con = sqlite3.connect(db)
    try:
        kept = con.execute(
            "SELECT name, partner_type FROM partners"
            " WHERE partner_id='prt-rt'"
        ).fetchone()
    finally:
        con.close()
    assert kept == ("Industrie AG", "implementation_partner"), (
        "partner row lost on downgrade"
    )
    assert _alembic(db, "upgrade", "head").returncode == 0
    assert _head_version(db) == _HEAD
    assert _ROLE_SKILL_COLUMNS <= _columns(db, "agent_invocations")
    assert _LIVE_INVOCATION_COLUMNS <= _columns(db, "agent_invocations")
    assert _LIVE_RUN_COLUMNS <= _columns(db, "analysis_runs")
    assert "source_url" in _columns(db, "source_documents")
    assert _LIVE_RESEARCH_RESULT_COLUMNS <= _columns(db, "research_results")
    assert "generation_kind" in _columns(db, "market_comparisons")
    assert {"agent_invocation_attempts", "provider_preflight_results"} <= _tables(db)
    assert "run_phases" in _tables(db)
    assert _USAGE_COST_COLUMNS <= _columns(db, "usage_records")
    assert "import_candidates" in _tables(db)
    assert {
        "import_candidate_id", "workspace_id", "project_id", "source_id",
        "source_version_id", "field_id", "extracted_text", "edited_text",
        "confidence", "source_location", "decision", "decided_by", "decided_at",
        "accepted_draft_version_id", "created_at", "mapping_version",
        "mapping_status", "section_metadata",
    } <= _columns(db, "import_candidates")
    assert "review_comment" in _columns(db, "partners")
    assert {"current_revision_id", "revision_number"} <= _columns(
        db, "import_candidates"
    )
    assert "revision_number" in _columns(db, "partners")
    assert {"primary_application_source_id", "field_revision_number"} <= _project_columns(db)
    assert {
        "import_candidate_revisions",
        "structured_import_candidate_revisions",
        "project_field_revisions",
    } <= _tables(db)
    con = sqlite3.connect(db)
    try:
        usage = con.execute(
            "SELECT input_tokens, output_tokens, cost_status, price_version"
            " FROM usage_records WHERE usage_record_id='usg-eval1'"
        ).fetchone()
        cand = con.execute(
            "SELECT extracted_text, edited_text, decision, mapping_version,"
            " mapping_status, section_metadata FROM import_candidates"
            " WHERE import_candidate_id='cand-rt'"
        ).fetchone()
        partner = con.execute(
            "SELECT name, review_comment FROM partners WHERE partner_id='prt-rt'"
        ).fetchone()
        phase_rows = con.execute("SELECT COUNT(*) FROM run_phases").fetchone()
        import_revision = con.execute(
            "SELECT revision_number, status, action, user_text "
            "FROM import_candidate_revisions WHERE import_candidate_id='cand-rt'"
        ).fetchone()
        partner_revision = con.execute(
            "SELECT revision_number FROM partners WHERE partner_id='prt-rt'"
        ).fetchone()
    finally:
        con.close()
    # Frühere Revisionen werden vom -1-Roundtrip nicht berührt.
    assert usage == (11, 22, "not_applicable", None), "usage row mutated in roundtrip"
    assert cand == (
        "Original", "Bearbeitet", "accepted", "legacy-anchor-v1",
        "content_detected", "[]",
    ), (
        "candidate row mutated in roundtrip"
    )
    assert phase_rows == (1,), "run phase row lost in mapping-metadata roundtrip"
    assert import_revision == (1, "accepted", "legacy_migrated", "Bearbeitet")
    assert partner_revision == (1,)
    assert partner == ("Industrie AG", "Begründung"), (
        "partner row mutated in roundtrip"
    )
    assert {
        "direct_total_project_costs_excluding_overhead",
        "implementation_own_contribution",
        "cash_contribution",
        "total_requested_funding",
        "budget_exception_basis",
        "duration_months",
        "title_en",
        "start_date",
        "end_date",
        "total_requested_funding_including_overhead",
    } <= _project_columns(db)
    assert "structured_import_candidates" in _tables(db)
    assert "department" in _columns(db, "partners")
    assert {"generation_kind", "target_section", "section_result_json"} <= _columns(
        db, "draft_suggestions"
    )
    assert "target_section" in _columns(db, "review_findings")
    assert "research_briefs" in _tables(db)
    assert {
        "research_brief_id", "research_module", "planner_purpose", "execution_mode",
    } <= _columns(db, "research_tasks")
    assert {
        "research_brief_id", "research_module", "planner_purpose",
    } <= _columns(db, "search_query_approvals")
    assert {
        "comparison_dimensions", "coverage_status", "support_status",
    } <= _columns(db, "market_comparison_items")
    assert {"draft_claims", "claim_lineages", "run_quality_summaries"} <= _tables(db)
