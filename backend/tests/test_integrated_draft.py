"""R5.9 — Integrated Draft Run (DraftPackage over the 8 supported fields), fake provider.

Covers: the DraftPackage shape (8 fields, each a status), the 6 A2 fields producing an
AIProposal or controlled missing_inputs, deterministic NAME / missing_inputs NAME_EN, the
no-auto-accept invariant (human review always, nothing copy-ready/final), usage linkage +
aggregation, research-context usage for VC/SOL (candidate ids never become anchors), the
status mapping (invented anchor → failed, placeholder → missing_inputs), and the
whitelist-only / no-canary report.
"""
from __future__ import annotations

import uuid

import pytest

from app.agents import a2_fields
from app.config.settings import get_settings
from app.db.models import Project, ResearchResult, Workspace
from app.db.session import SessionLocal
from app.integrated_draft.package import DraftPackage
from app.integrated_draft.report import render_report
from app.integrated_draft.runner import run_integrated_draft
from app.registry.loader import get_registry
from tests.a2_helpers import (
    MARKET_PURPOSE,
    PARTNER_PURPOSE,
    bundle,
    fake_resolver,
    success_fake,
)

WS = "ws-integrated-draft"
CANARY = "PROJECT_SECRET_MARKER_R5_INJECTION"
VC_FIELD = "VC.BUSINESS_TARGETS_MODEL.EDITOR"
SOL_FIELD = "SOL.INNOVATION_SOLUTION.EDITOR"
NAME_FIELD = "INTRO.APP.NAME"
NAME_EN_FIELD = "INTRO.APP.NAME_EN"
_A2_FIELDS = {
    "INTRO.APP.ABSTRACT", "INTRO.APP.EXECUTIVE_SUMMARY",
    "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS", VC_FIELD, SOL_FIELD,
    "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION",
}
_STATUSES = {"generated", "deterministic", "missing_inputs", "skipped", "unavailable", "failed"}
_D0 = {"sensitivity": "public", "origin": "synthetic", "processing_mode": "cloud_assisted",
       "web_research_mode": "validated_public", "nda_applies": False}


@pytest.fixture
def db():
    s = SessionLocal()
    if s.get(Workspace, WS) is None:
        s.add(Workspace(id=WS, name="Integrated Draft Test WS"))
        s.commit()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def fake_provider(monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_fake_provider", True)


def _base_project(db, *, title="F1 Integrated Draft (synthetisch)", description="Synthetisch.") -> Project:
    pid = "idp-" + uuid.uuid4().hex[:8]
    p = Project(
        project_id=pid, workspace_id=WS, title=title, description=description,
        innovation_field="Industrial AI / Manufacturing",
        funding_instrument_profile_id=(
            "innosuisse_innovation_project_with_implementation_partner"
        ),
        data_classification=dict(_D0), created_by="user-anna", status="draft",
    )
    db.add(p)
    db.flush()
    return db.get(Project, pid)


def _make_seed_ctx(seeded_ids: list[str]):
    """A seed_context that seeds — per VC/SOL child project — one open research
    CANDIDATE (records its id into ``seeded_ids``; R8: darf nie Kontext/Beleg werden)
    plus one IMPORTED public source (R8/Anforderung 10: der einzige Research-Weg in
    den A2-Kontext)."""
    from app.db.models import ResearchTask, SourceDocument, SourceFragment, SourceVersion

    def _seed(db, field_id, project):
        purpose = {VC_FIELD: MARKET_PURPOSE, SOL_FIELD: PARTNER_PURPOSE}.get(field_id)
        if purpose is None:
            return
        task_id = "rt-" + uuid.uuid4().hex[:8]
        db.add(ResearchTask(
            research_task_id=task_id, project_id=project.project_id,
            workspace_id=project.workspace_id, created_by="user-anna", purpose=purpose,
            subject_type="topic", query_text="öffentliche Suche", normalized_query_hash="qh",
            status="succeeded",
        ))
        rid = "rr-" + uuid.uuid4().hex[:8]
        db.add(ResearchResult(
            result_id=rid, research_task_id=task_id, workspace_id=project.workspace_id,
            source_url="https://research.example.org/r/1", title="Öffentliche Quelle",
            snippet="Auszug (kein Beleg).", provider_rank=1, status="candidate",
        ))
        text = (
            "Der Markt für Anbieter und Wettbewerber wächst; alternative Lösungen "
            "und Produkte für Kunden sind öffentlich beschrieben."
        )
        source_id = "src-" + uuid.uuid4().hex[:8]
        version_id = "sv-" + uuid.uuid4().hex[:8]
        dc = {
            "sensitivity": "public", "origin": "public_source",
            "processing_mode": "deterministic_only",
            "web_research_mode": "validated_public", "nda_applies": False,
        }
        db.add(SourceDocument(
            source_id=source_id, project_id=project.project_id,
            workspace_id=project.workspace_id, name="Marktbericht (öffentlich)",
            type="url", status="processed", data_classification=dc,
            current_source_version_id=version_id, created_by="user-anna",
        ))
        db.add(SourceVersion(
            source_version_id=version_id, source_document_id=source_id, version_number=1,
            original_content_hash="h", normalized_content_hash="h2", normalized_text=text,
            parser_version="parser-1", normalizer_version="normalizer-1",
            chunker_version="chunker-1", processing_status="processed",
            data_classification=dc, storage_ref="b" * 32,
            original_filename="market.html", byte_size=len(text), mime_type="text/html",
        ))
        db.add(SourceFragment(
            fragment_id="frag-" + uuid.uuid4().hex[:8], source_version_id=version_id,
            ordinal=0, original_text=text, normalized_text=text, start_offset=0,
            end_offset=len(text), content_hash="fh",
        ))
        db.flush()
        seeded_ids.append(rid)

    return _seed


def _run(db, project, *, resolver_for=None, seed_context=None, title_en=None) -> DraftPackage:
    return run_integrated_draft(
        db, base_project=project, actor_user_id="user-anna", case_id="F1",
        provider_mode="fake", data_mode="fake_test",
        resolver_for=resolver_for, seed_context=seed_context, title_en=title_en,
    )


# --- package shape -----------------------------------------------------------


def test_package_has_eight_fields_each_with_status(db, fake_provider):
    project = _base_project(db)
    pkg = _run(db, project)
    assert len(pkg.fields) == 8
    expected_ids = [f.field_id for f in get_registry().m6_draft_fields()]
    assert [f.field_id for f in pkg.fields] == expected_ids
    assert all(f.status in _STATUSES for f in pkg.fields)


def test_six_a2_fields_generate_or_missing_inputs(db, fake_provider):
    project = _base_project(db)
    pkg = _run(db, project)
    a2 = [f for f in pkg.fields if f.field_id in _A2_FIELDS]
    assert len(a2) == 6
    for f in a2:
        assert f.status in ("generated", "missing_inputs")
        if f.status == "generated":
            assert f.generation_kind == "fake_demo"
            assert f.ai_proposal is None
            assert f.draft_proposal is not None
            assert f.draft_proposal["human_review_required"] is True


def test_name_deterministic_and_name_en_missing(db, fake_provider):
    project = _base_project(db, title="Mein Antragstitel")
    pkg = _run(db, project)
    by_id = {f.field_id: f for f in pkg.fields}
    assert by_id[NAME_FIELD].status == "deterministic"
    assert by_id[NAME_FIELD].suggestion_text == "Mein Antragstitel"
    assert by_id[NAME_EN_FIELD].status == "missing_inputs"
    assert by_id[NAME_EN_FIELD].missing_inputs


def test_name_missing_when_title_empty(db, fake_provider):
    project = _base_project(db, title="   ")
    pkg = _run(db, project)
    name = next(f for f in pkg.fields if f.field_id == NAME_FIELD)
    assert name.status == "missing_inputs"


def test_name_en_deterministic_when_title_en_provided(db, fake_provider):
    title_en = "QUALIMON — AI-based Quality Monitoring for Production Lines"
    project = _base_project(db, title="Mein Antragstitel")
    pkg = _run(db, project, title_en=title_en)
    assert len(pkg.fields) == 8
    name_en = next(f for f in pkg.fields if f.field_id == NAME_EN_FIELD)
    assert name_en.status == "deterministic"
    assert name_en.suggestion_text == title_en
    assert not name_en.missing_inputs


def test_name_en_missing_when_title_en_blank(db, fake_provider):
    project = _base_project(db, title="Mein Antragstitel")
    pkg = _run(db, project, title_en="   ")
    name_en = next(f for f in pkg.fields if f.field_id == NAME_EN_FIELD)
    assert name_en.status == "missing_inputs"
    assert name_en.missing_inputs


# --- no auto-accept ----------------------------------------------------------


def test_no_auto_accept_no_copy_ready(db, fake_provider):
    project = _base_project(db)
    pkg = _run(db, project)
    assert pkg.human_review_required is True
    assert all(f.human_review_required is True for f in pkg.fields)
    # No copy-ready / final markers exist anywhere in the structure.
    assert not hasattr(pkg, "copy_ready") and not hasattr(pkg, "submitted")
    for f in pkg.fields:
        assert not hasattr(f, "copy_ready") and not hasattr(f, "accepted")


# --- usage -------------------------------------------------------------------


def test_fake_demo_exposes_no_model_usage_metadata(db, fake_provider):
    project = _base_project(db)
    pkg = _run(db, project)
    generated = [f for f in pkg.fields if f.status == "generated"]
    assert len(generated) == 6
    for f in generated:
        assert f.generation_kind == "fake_demo"
        assert f.ai_proposal is None
        assert f.provider is None and f.model is None
        assert f.usage_record_id is None
        assert f.input_tokens is None and f.output_tokens is None and f.total_tokens is None
    assert pkg.usage_summary["total_tokens"] == 0
    assert pkg.usage_summary["usage_record_count"] == 0
    assert pkg.usage_summary["cost_status_counts"] == {}


# --- research context --------------------------------------------------------


def test_research_context_used_and_never_evidence(db, fake_provider):
    seeded_ids: list[str] = []
    project = _base_project(db)
    pkg = _run(db, project, seed_context=_make_seed_ctx(seeded_ids))
    assert pkg.research_summary["market"]["used"] is True
    assert pkg.research_summary["partner"]["used"] is True
    # R8 (Anforderung 10): NUR die akzeptierte (importierte) Quelle ist Kontext —
    # offene Kandidaten fliessen nicht mehr ein.
    assert pkg.research_summary["market"]["imported_sources"] >= 1
    assert pkg.research_summary["market"]["candidates"] == 0
    # No seeded ResearchResult id ever appears in any used_anchor_ids.
    seeded = set(seeded_ids)
    assert len(seeded) == 2
    for f in pkg.fields:
        used = (f.draft_proposal or {}).get("used_anchor_ids", [])
        assert seeded.isdisjoint(used)


# --- status mapping ----------------------------------------------------------


def test_invented_anchor_field_fails_package_continues(db, fake_provider):
    project = _base_project(db)

    def resolver_for(field_id):
        cfg = a2_fields.resolve_field_config(field_id)
        anchors = ["anchor-ghost"] if field_id == VC_FIELD else []
        return fake_resolver(success_fake(
            bundle(field_id=field_id, suggested_text=cfg.fake_text, evidence_anchor_ids=anchors)
        ))

    pkg = _run(db, project, resolver_for=resolver_for)
    assert len(pkg.fields) == 8  # package still complete
    vc = next(f for f in pkg.fields if f.field_id == VC_FIELD)
    assert vc.status == "failed"


def test_placeholder_bundle_maps_to_missing_inputs(db, fake_provider):
    project = _base_project(db)

    def resolver_for(field_id):
        cfg = a2_fields.resolve_field_config(field_id)
        placeholders = (
            [{"label": "Marktgrösse", "reason": "kein Beleg"}] if field_id == VC_FIELD else []
        )
        return fake_resolver(success_fake(
            bundle(field_id=field_id, suggested_text=cfg.fake_text, placeholders=placeholders)
        ))

    pkg = _run(db, project, resolver_for=resolver_for)
    vc = next(f for f in pkg.fields if f.field_id == VC_FIELD)
    assert vc.status == "missing_inputs"
    assert vc.missing_inputs and vc.missing_inputs[0]["label"] == "Marktgrösse"


# --- no-raw / report ---------------------------------------------------------


def test_no_canary_in_report(db, fake_provider):
    project = _base_project(db, description=f"Vertraulich: {CANARY} nie nach aussen.")
    pkg = _run(db, project)
    report = render_report(pkg, generated_at="2026-07-09")
    assert CANARY not in report


def test_report_is_whitelist_only(db, fake_provider):
    project = _base_project(db)
    pkg = _run(db, project)
    report = render_report(pkg, generated_at="2026-07-09")
    for section in ("Case Summary", "Field Summary", "Generated Draft Preview",
                    "Usage Summary", "Research Usage", "Quality Notes", "Limitations"):
        assert section in report
    # No prompt/system-instruction leakage, no keys.
    assert "BEGIN UNTRUSTED" not in report
    assert "api_key" not in report.lower() and "system prompt" not in report.lower()
