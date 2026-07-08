"""R5.1 — Advisory-Facts-Rename: Grep-Guard, Warning-Erhalt, Contract-Wire-Key.

Der Guard stellt sicher, dass ``confirmed_facts``/``retrieve_confirmed_project_facts``
in aktivem Backend-Code nur noch auf explizit contract-pinned markierten Zeilen
vorkommen (Wire-Strings des eingefrorenen Contracts v1.1). Fake-only, kein Netz.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest

from app.agents import field_drafting
from app.agents.field_drafting_context import assemble_a2_context, build_input_payload
from app.agents.schemas import validate_payload
from app.db.models import ExtractedFact
from app.db.session import SessionLocal
from tests.a2_helpers import build_run_with_draft, bundle, fake_resolver, success_fake

APP_DIR = Path(__file__).resolve().parents[1] / "app"
PATTERNS = (
    re.compile(r"\bconfirmed_facts\b"),
    re.compile(r"retrieve_confirmed_project_facts"),
)
MARKER = "contract-pinned"


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def test_confirmed_facts_only_on_contract_pinned_lines():
    offenders = [
        f"{p.relative_to(APP_DIR)}:{n}: {line.strip()}"
        for p in sorted(APP_DIR.rglob("*.py"))
        for n, line in enumerate(
            p.read_text(encoding="utf-8").splitlines(), start=1
        )
        if any(rx.search(line) for rx in PATTERNS) and MARKER not in line
    ]
    assert offenders == [], (
        "confirmed_facts ohne contract-pinned-Marker in aktivem Code:\n"
        + "\n".join(offenders)
    )


def _add_proposed_fact(db, run) -> str:
    fact_id = "fact-" + uuid.uuid4().hex[:8]
    db.add(
        ExtractedFact(
            fact_id=fact_id, run_id=run.run_id, workspace_id=run.workspace_id,
            fact_type="project_fact", normalized_value=None,
            original_statement="Synthetische Angabe (advisory).",
            status="proposed", source_fragment_ids=["frag"],
            source_version_ids=[], profile_id="A1.project_fact_extraction",
            fact_fingerprint=fact_id,
        )
    )
    db.flush()
    return fact_id


def test_unconfirmed_facts_warning_preserved(db):
    # Der FE-sichtbare Warning-Key überlebt den Rename wörtlich.
    run, draft, base = build_run_with_draft(db)
    _add_proposed_fact(db, run)
    out = field_drafting.run_a2_solution_innovation(
        db, run, draft_id=draft.draft_id, base_version_id=base,
        operation_id="op-r51", provider_resolver=fake_resolver(success_fake(bundle())),
    )
    assert out.status == "succeeded"
    assert "based_on_unconfirmed_facts" in out.view["warnings"]


def test_wire_key_still_contract_valid(db):
    # Der Contract-Wire-Key "confirmed_facts" (FieldDraftingInput@v1) bleibt,
    # gefüllt mit advisory Facts.
    run, _draft, _base = build_run_with_draft(db)
    _add_proposed_fact(db, run)
    ctx = assemble_a2_context(
        db, run, field_id="SOL.INNOVATION_SOLUTION.EDITOR",
        profile_id="A2.solution_innovation",
    )
    assert len(ctx.advisory_facts) == 1
    payload = build_input_payload(ctx, run.run_id)
    assert "confirmed_facts" in payload and len(payload["confirmed_facts"]) == 1
    validate_payload("FieldDraftingInput@v1", payload)  # darf nicht raisen
