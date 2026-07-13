"""Milestone 10 — migration hardening.

Runs the REAL Alembic migrations (subprocess `python -m alembic`) against a throwaway
temp SQLite DB — distinct from the ``Base.metadata.create_all`` test DB used elsewhere —
so a fresh production-style DB is exercised. Covers a fresh upgrade, an existing-DB no-op
upgrade + row-preservation hardening check (M10 adds NO migration), and a latest-migration
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
}
_HEAD = "1d4f8a2c6b90"  # versionierte Metadaten des Innolink-Imports.


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
    missing = _KEY_TABLES - _tables(db)
    assert not missing, f"missing tables after fresh upgrade: {missing}"
    # App connectivity smoke: the migrated DB is a valid, queryable schema.
    con = sqlite3.connect(db)
    try:
        assert con.execute("SELECT 1").fetchone() == (1,)
    finally:
        con.close()


def test_existing_db_upgrade_is_noop_and_preserves_data(tmp_path):
    """Hardening check (NOT a full historical production migration test): M10 adds no
    migration, so upgrading an at-head DB is a no-op that must preserve existing rows."""
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
    """Roundtrip der Head-Migration (Import-Mapping-Metadaten): Down entfernt
    NUR die drei neuen Spalten; alle früheren Revisionen (review_comment,
    edited_text, EVAL.1-Spalten, R3.2-Tabelle, R2.2-Spalten) und bestehende
    Zeilen bleiben unangetastet erhalten."""
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
    assert "review_comment" in _columns(db, "partners")
    assert _USAGE_COST_COLUMNS <= _columns(db, "usage_records")
    assert _FINDING_V2_COLUMNS <= _columns(db, "review_findings")
    assert _FINDING_V2_COLUMNS <= _columns(db, "open_issues")
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
    # Down one (entfernt NUR die Mapping-Metadaten), dann wieder hoch. Alle
    # früheren Revisionen überleben den -1-Schritt unangetastet.
    assert _alembic(db, "downgrade", "-1").returncode == 0
    assert "run_phases" in _tables(db)
    assert not {
        "mapping_version", "mapping_status", "section_metadata"
    }.intersection(_columns(db, "import_candidates"))
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
    finally:
        con.close()
    # Frühere Revisionen werden vom -1-Roundtrip nicht mehr berührt: usage-,
    # Kandidaten- und Partner-Zeile bleiben exakt erhalten (inkl. edited_text
    # und review_comment). Die Import-Metadaten werden sicher zurückgefüllt.
    assert usage == (11, 22, "not_applicable", None), "usage row mutated in roundtrip"
    assert cand == (
        "Original", "Bearbeitet", "accepted", "legacy-anchor-v1",
        "content_detected", "[]",
    ), (
        "candidate row mutated in roundtrip"
    )
    assert phase_rows == (1,), "run phase row lost in mapping-metadata roundtrip"
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
    } <= _project_columns(db)
    assert {"draft_claims", "claim_lineages", "run_quality_summaries"} <= _tables(db)
