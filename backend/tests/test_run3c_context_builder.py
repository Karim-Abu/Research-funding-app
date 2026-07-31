from __future__ import annotations

import hashlib
import uuid

import pytest
from sqlalchemy import select

from app.agents.field_drafting_context import (
    ContextSelectionError, assemble_a2_context, persist_suggestion_manifest,
    suggestion_context_options,
)
from app.agents import suggestion_staleness
from app.db.models import (
    EvidenceAnchor, MarketComparison, MarketComparisonItem,
    SourceDocument, SourceFragment, SourceVersion,
    SuggestionContextManifest,
)
from app.repositories import draft_suggestions
from app.runs import project_snapshot
from app.db.session import SessionLocal
from tests.a2_helpers import (
    VC_FIELD_ID, VC_GOOD_TEXT, add_imported_public_source, build_run_with_draft,
)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _external_anchor(db, run, *, quote="Öffentlich belegte Marktinformation."):
    source_id = add_imported_public_source(db, run, text=quote)
    source = db.get(SourceDocument, source_id)
    version = db.get(SourceVersion, source.current_source_version_id)
    version.content_review_status = "reviewed"
    version.content_safety_status = "passed"
    fragment = db.scalar(select(SourceFragment).where(
        SourceFragment.source_version_id == version.source_version_id
    ))
    anchor = EvidenceAnchor(
        anchor_id="anchor-" + uuid.uuid4().hex[:8], run_id=None,
        project_id=run.project_id, workspace_id=run.workspace_id,
        source_version_id=version.source_version_id, source_id=source_id,
        source_name=source.name, source_type="url", fragment_id=fragment.fragment_id,
        quote=quote, quote_hash=_hash(quote), match_type="manual",
        normalizer_version="nfc-ws-v1", verification_status="human_verified",
        scope="external",
    )
    db.add(anchor)
    db.flush()
    return source, version, anchor


def _context(db, run, base, selected):
    return assemble_a2_context(
        db, run, field_id=VC_FIELD_ID,
        profile_id="A2.value_creation_market_logic", target_section="3.2",
        section_markers=("3.1", "3.2", "3.3"), base_version_id=base,
        selected_anchor_ids=selected, manifest_mode=True,
    )


def test_manifest_context_uses_only_explicit_current_reviewed_anchor(db):
    run, _draft, base = build_run_with_draft(
        db, field_id=VC_FIELD_ID, draft_text=VC_GOOD_TEXT,
        character_limit=15000, field_name="Value Creation",
    )
    _source, version, anchor = _external_anchor(db, run)
    ctx = _context(db, run, base, [anchor.anchor_id])
    assert ctx.allowed_anchor_ids == {anchor.anchor_id}
    assert ctx.source_version_ids == {version.source_version_id}
    assert "Search-Snippet" not in ctx.context_text
    assert ctx.research_context == {}
    options = suggestion_context_options(db, run)
    assert [item["anchor_id"] for item in options["anchors"]] == [anchor.anchor_id]
    assert "quote" not in options["anchors"][0]


def test_manifest_budget_omits_whole_anchor_and_records_it(db, monkeypatch):
    run, draft, base = build_run_with_draft(
        db, field_id=VC_FIELD_ID, draft_text=VC_GOOD_TEXT,
        character_limit=15000, field_name="Value Creation",
    )
    _source, _version, anchor = _external_anchor(
        db, run, quote=("Ein vollstaendiger belegter Satz. " * 500),
    )
    from app.config.settings import get_settings

    monkeypatch.setattr(get_settings(), "a1_context_char_budget", 5000)
    ctx = _context(db, run, base, [anchor.anchor_id])
    assert ctx.allowed_anchor_ids == set()
    assert ctx.omitted_anchor_ids == {anchor.anchor_id}
    assert ctx.meta["context_truncated"] is True
    assert ctx.meta["omitted_anchor_ids"] == [anchor.anchor_id]
    assert anchor.anchor_id not in ctx.context_text
    suggestion = _suggestion(db, run, draft, base, ctx)
    assert suggestion_staleness.reason(db, run, suggestion) is None


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("stale", "selected_anchor_source_version_stale"),
        ("quarantine", "selected_anchor_quarantined"),
        ("generated", "selected_anchor_generated_content"),
    ],
)
def test_manifest_context_rejects_stale_quarantined_or_generated_anchor(
    db, mutation, reason
):
    run, _draft, base = build_run_with_draft(
        db, field_id=VC_FIELD_ID, draft_text=VC_GOOD_TEXT,
        character_limit=15000, field_name="Value Creation",
    )
    source, version, anchor = _external_anchor(db, run)
    if mutation == "stale":
        source.current_source_version_id = "new-version"
    elif mutation == "quarantine":
        version.content_safety_status = "quarantined"
    else:
        source.name = "Generated Output Review Package"
    db.flush()
    with pytest.raises(ContextSelectionError) as exc:
        _context(db, run, base, [anchor.anchor_id])
    assert exc.value.code == reason


def test_unverified_application_anchor_is_skipped_not_fatal(db, monkeypatch):
    """Regression (Run 85f40540, 2026-07-29): automatisch einbezogene
    Application-Anker im Zustand «rejected» liessen JEDEN Redraft des Felds
    mit selected_anchor_not_verified scheitern — ohne jede Nutzer-Auswahl.
    Jetzt: auslassen; nur die EXPLIZITE Auswahl bleibt der behebbare Fehler."""
    from types import SimpleNamespace

    from app.agents import field_drafting_context as fdc

    run, _draft, base = build_run_with_draft(
        db, field_id=VC_FIELD_ID, draft_text=VC_GOOD_TEXT,
        character_limit=15000, field_name="Value Creation",
    )
    source = db.scalar(select(SourceDocument).where(
        SourceDocument.project_id == run.project_id
    ))
    version = db.scalar(select(SourceVersion).where(
        SourceVersion.source_document_id == source.source_id
    ))
    anchor = EvidenceAnchor(
        anchor_id="anchor-rejected-" + uuid.uuid4().hex[:6], run_id=run.run_id,
        workspace_id=run.workspace_id, project_id=run.project_id,
        source_version_id=version.source_version_id, source_id=source.source_id,
        source_name=source.name, source_type="txt", fragment_id="frag",
        quote="Nicht verifizierte Angabe.", quote_hash=_hash("x"),
        match_type="exact_normalized", normalizer_version="normalizer-1",
        verification_status="rejected", scope="application",
    )
    db.add(anchor)
    db.flush()
    requirement_id = next(iter(fdc._linked_requirement_ids(VC_FIELD_ID)))
    monkeypatch.setattr(
        fdc, "formal_application_scope",
        lambda _db, _run: SimpleNamespace(
            status="configured", source_id=source.source_id,
            source_version_id=version.source_version_id,
        ),
    )
    monkeypatch.setattr(
        fdc, "_anchor_requirement_map",
        lambda _db, _run: {anchor.anchor_id: requirement_id},
    )
    # Automatisch einbezogen (keine Auswahl): Kontext gelingt, Anker fehlt.
    ctx = _context(db, run, base, [])
    assert anchor.anchor_id not in ctx.allowed_anchor_ids
    # Explizite Auswahl desselben Ankers bleibt der behebbare Fehler.
    with pytest.raises(ContextSelectionError) as exc:
        _context(db, run, base, [anchor.anchor_id])
    assert exc.value.code == "selected_anchor_not_verified"


def test_market_context_is_source_backed_and_limited_to_five(db):
    run, _draft, base = build_run_with_draft(
        db, field_id=VC_FIELD_ID, draft_text=VC_GOOD_TEXT,
        character_limit=15000, field_name="Value Creation",
    )
    _source, version, anchor = _external_anchor(db, run)
    comparison = MarketComparison(
        comparison_id="comparison-" + uuid.uuid4().hex[:8],
        project_id=run.project_id, workspace_id=run.workspace_id,
        run_id=run.run_id, research_task_ids=[], query_approval_ids=[],
        source_version_ids=[version.source_version_id], status="ready_for_review",
        research_gaps=[], warnings=[], consequences=[], created_by="user-anna",
    )
    db.add(comparison)
    for index in range(7):
        db.add(MarketComparisonItem(
            item_id=f"item-{index}-{uuid.uuid4().hex[:6]}",
            comparison_id=comparison.comparison_id, workspace_id=run.workspace_id,
            name=f"Marktalternative {index}", name_normalized=f"marktalternative-{index}",
            category="alternative_solution", description="Markt Zielkunden Wettbewerb",
            relation_to_project="competing", confidence_label="source_backed",
            status="accepted", source_document_ids=[], verified_quote_refs=[],
            evidence_anchor_ids=[anchor.anchor_id], cell_evidence={},
            comparison_dimensions={},
        ))
    db.flush()
    ctx = _context(db, run, base, [anchor.anchor_id])
    assert ctx.market_comparison_id == comparison.comparison_id
    assert len(ctx.market_findings) == 5
    assert all(item["anchor_ids"] == [anchor.anchor_id] for item in ctx.market_findings)


def _suggestion(db, run, draft, base, ctx):
    manifest = persist_suggestion_manifest(
        db, run, ctx, base_version_id=base, prompt_version="prompt-v1",
        output_schema_version="FieldSuggestionOutput@v1",
    )
    return draft_suggestions.create(
        db, run, draft_id=draft.draft_id, base_version_id=base,
        field_id=VC_FIELD_ID, profile_id="A2.value_creation_market_logic",
        operation_id="op-" + uuid.uuid4().hex[:8], agent_invocation_id=None,
        prompt_version="prompt-v1", model_route=None, model_id=None,
        generation_kind="fake_demo", target_section="3.2",
        section_result_json={}, suggested_text="3.2 Markt: [offen].",
        rationale=None, evidence_anchor_ids=[], open_issue_ids=[], placeholders=[],
        character_count=20, manifest_id=manifest.manifest_id,
        improvement_mode="clearer", source_version_ids=sorted(ctx.source_version_ids),
        market_comparison_id=ctx.market_comparison_id,
        registry_version=manifest.rule_registry_version,
        output_schema_version="FieldSuggestionOutput@v1",
        context_hash=manifest.context_hash, quality_state="completed",
        accept_mode="whole_suggestion_only",
    )


def test_staleness_detects_draft_snapshot_registry_and_field_changes(db, monkeypatch):
    run, draft, base = build_run_with_draft(
        db, field_id=VC_FIELD_ID, draft_text=VC_GOOD_TEXT,
        character_limit=15000, field_name="Value Creation",
    )
    monkeypatch.setattr(project_snapshot, "is_stale", lambda _db, _snapshot: False)
    ctx = _context(db, run, base, [])
    suggestion = _suggestion(db, run, draft, base, ctx)
    assert suggestion_staleness.reason(db, run, suggestion) is None

    draft.current_version_id = "new-draft-version"
    assert suggestion_staleness.reason(db, run, suggestion) == "draft_version_changed"
    draft.current_version_id = base

    manifest = db.get(SuggestionContextManifest, suggestion.manifest_id)
    old_requirement_version = manifest.requirement_registry_version
    manifest.requirement_registry_version = "changed"
    assert suggestion_staleness.reason(db, run, suggestion) == "registry_version_changed"
    manifest.requirement_registry_version = old_requirement_version

    old_instruction_hash = manifest.field_instruction_hash
    manifest.field_instruction_hash = "changed"
    assert suggestion_staleness.reason(db, run, suggestion) == "field_instruction_changed"
    manifest.field_instruction_hash = old_instruction_hash

    monkeypatch.setattr(project_snapshot, "is_stale", lambda _db, _snapshot: True)
    assert suggestion_staleness.reason(db, run, suggestion) == "run_snapshot_changed"


def test_staleness_detects_source_anchor_and_market_changes(db):
    run, draft, base = build_run_with_draft(
        db, field_id=VC_FIELD_ID, draft_text=VC_GOOD_TEXT,
        character_limit=15000, field_name="Value Creation",
    )
    source, version, anchor = _external_anchor(db, run)
    comparison = MarketComparison(
        comparison_id="comparison-" + uuid.uuid4().hex[:8],
        project_id=run.project_id, workspace_id=run.workspace_id,
        run_id=run.run_id, research_task_ids=[], query_approval_ids=[],
        source_version_ids=[version.source_version_id], status="ready_for_review",
        research_gaps=[], warnings=[], consequences=[], created_by="user-anna",
    )
    db.add(comparison)
    db.add(MarketComparisonItem(
        item_id="item-" + uuid.uuid4().hex[:8], comparison_id=comparison.comparison_id,
        workspace_id=run.workspace_id, name="Alternative", name_normalized="alternative",
        category="alternative_solution", description="Markt Wettbewerb Zielkunden",
        relation_to_project="competing", confidence_label="source_backed",
        status="accepted", source_document_ids=[], verified_quote_refs=[],
        evidence_anchor_ids=[anchor.anchor_id], cell_evidence={}, comparison_dimensions={},
    ))
    db.flush()
    ctx = _context(db, run, base, [anchor.anchor_id])
    suggestion = _suggestion(db, run, draft, base, ctx)
    assert suggestion_staleness.reason(db, run, suggestion) is None

    anchor.verification_status = "rejected"
    assert suggestion_staleness.reason(db, run, suggestion) == "anchor_changed"
    anchor.verification_status = "human_verified"
    source.current_source_version_id = "new-source-version"
    assert suggestion_staleness.reason(db, run, suggestion) == "source_version_changed"
    source.current_source_version_id = version.source_version_id
    comparison.stale_reason = "source_version_changed"
    assert suggestion_staleness.reason(db, run, suggestion) == "market_comparison_changed"
