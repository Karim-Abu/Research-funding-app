from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select

from app.agents import missing_inputs
from app.db.models import OpenIssue
from app.db.session import SessionLocal
from tests.a2_helpers import FIELD_ID, build_run_with_draft


def test_missing_input_issue_deduplicates_resolves_reopens_and_stales():
    db = SessionLocal()
    try:
        run, _draft, _base = build_run_with_draft(db)
        suggestion = SimpleNamespace(suggestion_id="suggestion-1", field_id=FIELD_ID)
        item = {
            "key": "market-size",
            "label": "Marktgrösse fehlt",
            "reason": "Bitte belastbare Marktgrösse ergänzen.",
            "requirement_ids": ["REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH"],
        }

        first = missing_inputs.sync_issues(db, run, suggestion, [item, item])
        second = missing_inputs.sync_issues(db, run, suggestion, [item])
        assert first == second
        assert len(list(db.scalars(select(OpenIssue).where(
            OpenIssue.target_type == "missing_input",
            OpenIssue.run_id == run.run_id,
        )))) == 1

        missing_inputs.sync_issues(db, run, suggestion, [])
        issue = db.get(OpenIssue, first[0])
        assert issue.status == "resolved"
        assert issue.resolved_at is not None

        missing_inputs.sync_issues(db, run, suggestion, [item])
        assert issue.status == "open"
        assert issue.status_reason == "missing_input_reappeared"

        assert missing_inputs.mark_suggestion_issues_stale(
            db, suggestion.suggestion_id, reason="registry_version_changed"
        ) == 1
        assert issue.status == "stale"
        assert issue.status_reason == "registry_version_changed"
    finally:
        db.rollback()
        db.close()
