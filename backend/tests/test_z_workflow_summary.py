"""E3 — «Entwurf vorhanden/bearbeitet ⇒ In Bearbeitung»: workflow_summary
zählt echte Draft-Inhalte unabhängig von der Herkunft (user/agent/import);
Template-Versionen zählen weiterhin nicht. (z-Präfix: die Builder legen
ws-demo-Projekte an — muss nach test_demo_seed laufen.)"""
from __future__ import annotations

import hashlib
import uuid

import pytest

from app.db.models import DraftVersion
from app.db.session import SessionLocal
from app.workflow_summary import calculate
from tests.a2_helpers import build_run_with_draft


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _completed_run(db):
    run, draft, base = build_run_with_draft(db)
    run.status = "completed"
    db.flush()
    return run, draft, base


def _add_version(db, draft, *, created_by: str) -> None:
    text = f"4.1 Inhalt von {created_by}.\n4.2 Weiterer Inhalt."
    version_id = "ver-" + uuid.uuid4().hex[:8]
    db.add(DraftVersion(
        draft_version_id=version_id, draft_id=draft.draft_id, text=text,
        character_count=len(text), created_by=created_by,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    ))
    draft.current_version_id = version_id
    db.flush()


def test_template_only_is_not_in_bearbeitung(db):
    run, _draft, _base = _completed_run(db)
    summary = calculate(db, run.project_id, run.workspace_id)
    assert summary.next_action != "continue_draft"


@pytest.mark.parametrize("created_by", ["user", "agent", "import"])
def test_real_draft_content_sets_continue_draft(db, created_by):
    run, draft, _base = _completed_run(db)
    _add_version(db, draft, created_by=created_by)
    summary = calculate(db, run.project_id, run.workspace_id)
    assert summary.next_action == "continue_draft"
    assert summary.current_step == 5  # Entwurf
