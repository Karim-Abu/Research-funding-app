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
_HEAD = "262f51ba5176"  # copy events (Slice 3).


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


def _project_columns(db_path: Path) -> set[str]:
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("PRAGMA table_info(projects)").fetchall()
    finally:
        con.close()
    return {r[1] for r in rows}


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
    db = tmp_path / "roundtrip.db"
    assert _alembic(db, "upgrade", "head").returncode == 0
    assert "copy_events" in _tables(db)
    # Down one (drops the Slice-3 copy_events table), then back up. The
    # Slice-1 budget columns (one revision earlier) must survive the -1 step.
    assert _alembic(db, "downgrade", "-1").returncode == 0
    assert "copy_events" not in _tables(db)
    assert "cash_contribution" in _project_columns(db)
    assert "duration_months" in _project_columns(db)
    assert "run_quality_summaries" in _tables(db)
    assert _alembic(db, "upgrade", "head").returncode == 0
    assert _head_version(db) == _HEAD
    assert "copy_events" in _tables(db)
    assert {
        "direct_total_project_costs_excluding_overhead",
        "implementation_own_contribution",
        "cash_contribution",
        "total_requested_funding",
        "budget_exception_basis",
        "duration_months",
    } <= _project_columns(db)
    assert {"draft_claims", "claim_lineages", "run_quality_summaries"} <= _tables(db)
