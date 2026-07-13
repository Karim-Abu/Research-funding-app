"""Milestone 9I-B — market & competitor comparison (fake provider only, no network).

Covers: imported-public-source scope + deterministic pre-filter, the beta-internal
structuring agent (fake), standalone deterministic quote verification, source-backed vs
needs_review items, dedup, data-policy gating, no draft/assessment/approval mutation,
comparison-scoped guard, and no provider/key leak.
"""
from __future__ import annotations

import hashlib
import uuid

import pytest
from sqlalchemy import func, select

from app.config.settings import get_settings
from app.db.models import (
    DraftVersion,
    EvidenceAnchor,
    MarketComparison,
    MarketComparisonItem,
    Project,
    RequirementAssessment,
    SourceDocument,
    SourceFragment,
    SourceVersion,
)
from app.db.session import SessionLocal
from app.market import executor as market_executor
from app.market import service, source_scope, verify
from tests.conftest import ANNA_EMAIL, ANNA_PASSWORD, login, unsafe_headers

PUBLIC_DC = {
    "sensitivity": "public", "origin": "synthetic", "processing_mode": "cloud_assisted",
    "web_research_mode": "validated_public", "nda_applies": False,
}
MARKET_TEXT = (
    "Die Plattform Acme ist eine alternative Lösung für den Markt. "
    "Konkurrenten bieten ähnliche Produkte für Kunden an. "
    "Im Vergleich unterscheidet sich das Angebot durch Differenzierung."
)


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def web_enabled(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "web_research_enabled", True)
    monkeypatch.setattr(s, "web_research_fake_provider", True)
    monkeypatch.setattr(s, "firecrawl_api_key", None)
    return s


def _headers(csrf: str) -> dict[str, str]:
    h = unsafe_headers(csrf)
    h["Idempotency-Key"] = uuid.uuid4().hex
    return h


def _create_project(client, csrf, classification=PUBLIC_DC, title="Market Project") -> str:
    res = client.post("/api/v1/projects", json={
        "title": title, "description": "market comparison test",
        "funding_instrument_profile_id":
            "innosuisse_innovation_project_with_implementation_partner",
        "data_classification": classification,
    }, headers=_headers(csrf))
    assert res.status_code == 201, res.text
    return res.json()["project_id"]


def _seed_imported_public_source(db, project_id, workspace_id, text=MARKET_TEXT):
    """Insert a web-imported public SourceDocument(type=url) + version + one fragment."""
    doc_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    dc = {"sensitivity": "public", "origin": "public_source",
          "processing_mode": "deterministic_only", "web_research_mode": "validated_public",
          "nda_applies": False}
    db.add(SourceDocument(
        source_id=doc_id, project_id=project_id, workspace_id=workspace_id,
        name="Öffentliche Webquelle", type="url", status="processed",
        data_classification=dc, current_source_version_id=version_id,
        created_by="user-anna",
    ))
    db.add(SourceVersion(
        source_version_id=version_id, source_document_id=doc_id, version_number=1,
        original_content_hash=hashlib.sha256(text.encode()).hexdigest(),
        normalized_content_hash=hashlib.sha256(text.encode()).hexdigest(),
        normalized_text=text, normalizer_version="normalizer-1",
        processing_status="processed", data_classification=dc,
        storage_ref="ref", original_filename="web", byte_size=len(text), mime_type="text/plain",
    ))
    db.add(SourceFragment(
        fragment_id=str(uuid.uuid4()), source_version_id=version_id, ordinal=0,
        original_text=text, normalized_text=text, start_offset=0, end_offset=len(text),
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
    ))
    db.commit()
    return doc_id, version_id


def _generate(client, csrf, project_id):
    res = client.post(f"/api/v1/projects/{project_id}/market-comparisons", headers=_headers(csrf))
    assert res.status_code == 202, res.text
    body = res.json()
    op = client.get(f"/api/v1/operations/{body['operation_id']}")
    assert op.status_code == 200
    return body, op.json()


# --- standalone quote verification ------------------------------------------

def test_verify_quote_exact_and_altered(client, db, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    _doc, version_id = _seed_imported_public_source(db, project_id, project.workspace_id)
    frag = db.scalar(select(SourceFragment).where(SourceFragment.source_version_id == version_id))

    exact = "Die Plattform Acme ist eine alternative Lösung"
    ref = verify.verify_quote(db, fragment=frag, source_document_id=_doc, quote=exact)
    assert ref is not None
    assert ref["quote"] == exact and ref["quote_hash"] and ref["normalizer_version"] == "normalizer-1"
    assert ref["verification_method"] == "deterministic_position_match"
    assert ref["linked_evidence_anchor_id"] is None  # no run anchor exists

    # Altered/absent quote → not evidence.
    assert verify.verify_quote(db, fragment=frag, source_document_id=_doc,
                               quote="Acme ist Weltmarktführer") is None


# --- source scope + prefilter ----------------------------------------------

def test_source_scope_filters_public_url_only(client, db, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    _seed_imported_public_source(db, project_id, project.workspace_id)
    sources = source_scope.imported_public_sources(db, project_id, project.workspace_id)
    assert len(sources) == 1 and sources[0].type == "url"
    cands = source_scope.prefilter_fragments(db, sources)
    assert len(cands) == 1 and cands[0].signal_score >= 3


def test_prefilter_skips_sources_without_market_terms(client, db, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    _seed_imported_public_source(db, project_id, project.workspace_id,
                                 text="Ein neutraler Absatz ohne relevante Begriffe.")
    sources = source_scope.imported_public_sources(db, project_id, project.workspace_id)
    assert source_scope.prefilter_fragments(db, sources) == []


# --- generation end-to-end --------------------------------------------------

def test_generate_produces_source_backed_item(client, db, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    _seed_imported_public_source(db, project_id, project.workspace_id)
    body, op = _generate(client, csrf, project_id)
    assert op["status"] == "succeeded"

    view = client.get(f"/api/v1/market-comparisons/{body['resource_id']}").json()
    assert view["status"] == "ready_for_review"
    assert view["item_count"] >= 1
    item = view["items"][0]
    assert item["confidence_label"] == "source_backed"
    assert item["evidence_quotes"], "source-backed item must carry a verified quote"
    quote = item["evidence_quotes"][0]
    assert quote["quote"] in MARKET_TEXT
    assert quote["linked_evidence_anchor_id"] is None
    assert view["research_gaps"]
    # No provider/model/confidence-number leakage in the public payload.
    blob = str(view).lower()
    assert "anthropic" not in blob and "haiku" not in blob and "firecrawl" not in blob


def test_market_size_and_customer_problem_categories(client, db, web_enabled):
    """R8 (Anforderung 11): die persistierte Zusammenfassung strukturiert auch
    Marktgrössen-Kandidaten und Kundenprobleme — nur mit verifiziertem Zitat,
    nie als gesicherte Tatsache (Anforderung 12)."""
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    _seed_imported_public_source(
        db, project_id, project.workspace_id,
        text=(
            "Der Markt für Anomalieerkennung wächst laut Bericht deutlich. "
            "Kunden beschreiben das Problem manueller Qualitätsprüfung als grösste "
            "Herausforderung. Anbieter und Wettbewerber bieten alternative Lösungen an."
        ),
    )
    body, op = _generate(client, csrf, project_id)
    assert op["status"] == "succeeded"
    view = client.get(f"/api/v1/market-comparisons/{body['resource_id']}").json()
    by_category = {i["category"]: i for i in view["items"]}
    assert "market_size_claim" in by_category
    assert "customer_problem" in by_category
    for item in by_category.values():
        # Kein Market-Claim ohne Quelle als Tatsache: entweder verifiziertes Zitat
        # (source_backed) oder ehrlich needs_human_review.
        if item["confidence_label"] == "source_backed":
            assert item["evidence_quotes"] and item["source_document_ids"]
        else:
            assert item["status"] == "needs_human_review"
    assert by_category["market_size_claim"]["confidence_label"] == "source_backed"


def test_no_imported_sources_gives_empty_with_gaps(client, db, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    body, op = _generate(client, csrf, project_id)
    assert op["status"] == "succeeded"
    view = client.get(f"/api/v1/market-comparisons/{body['resource_id']}").json()
    assert view["status"] == "ready_for_review"
    assert view["item_count"] == 0
    assert view["research_gaps"]  # rule 13: gaps instead of invented content
    cmp_row = db.get(MarketComparison, body["resource_id"])
    assert cmp_row.generation_status == "skipped"


def test_internal_project_blocked(client, db, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    internal = {"sensitivity": "internal", "origin": "real_project",
                "processing_mode": "cloud_assisted", "web_research_mode": "off",
                "nda_applies": False}
    project_id = _create_project(client, csrf, classification=internal, title="Internal")
    res = client.post(f"/api/v1/projects/{project_id}/market-comparisons", headers=_headers(csrf))
    assert res.status_code == 422


def test_unsupported_item_quote_becomes_needs_review(client, db, web_enabled, monkeypatch):
    import json as _json

    def bad_bundle(candidates):
        return _json.dumps({"items": [{
            "name": "Erfundener Anbieter", "category": "competitor",
            "description": None, "target_customer_segment": None, "offering_summary": None,
            "strengths": None, "weaknesses": None, "differentiation_relevance": None,
            "relation_to_project": "competing",
            "source_fragment_id": candidates[0].fragment_id,
            "source_document_id": candidates[0].source_document_id,
            "quote": "Dieser Satz steht in keiner Quelle.",
        }], "research_gaps": [], "warnings": []})

    monkeypatch.setattr(market_executor, "_fake_bundle", bad_bundle)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    _seed_imported_public_source(db, project_id, project.workspace_id)
    body, op = _generate(client, csrf, project_id)
    assert op["status"] == "succeeded"
    view = client.get(f"/api/v1/market-comparisons/{body['resource_id']}").json()
    item = view["items"][0]
    assert item["confidence_label"] == "insufficient_evidence"
    assert item["status"] == "needs_human_review"
    assert item["evidence_quotes"] == []  # fabricated quote is never stored as evidence


def test_duplicate_names_deduped(client, db, web_enabled, monkeypatch):
    import json as _json

    def dup_bundle(candidates):
        q = candidates[0].text[:40]
        item = {
            "name": "Acme", "category": "competitor", "description": None,
            "target_customer_segment": None, "offering_summary": None, "strengths": None,
            "weaknesses": None, "differentiation_relevance": None,
            "relation_to_project": "competing",
            "source_fragment_id": candidates[0].fragment_id,
            "source_document_id": candidates[0].source_document_id, "quote": q,
        }
        return _json.dumps({"items": [item, {**item, "name": "ACME"}],
                            "research_gaps": [], "warnings": []})

    monkeypatch.setattr(market_executor, "_fake_bundle", dup_bundle)
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    _seed_imported_public_source(db, project_id, project.workspace_id)
    body, _ = _generate(client, csrf, project_id)
    view = client.get(f"/api/v1/market-comparisons/{body['resource_id']}").json()
    assert view["item_count"] == 1


def test_no_draft_assessment_anchor_mutation(client, db, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    _seed_imported_public_source(db, project_id, project.workspace_id)
    before_anchors = db.scalar(select(func.count(EvidenceAnchor.anchor_id))) or 0
    before_drafts = db.scalar(select(func.count(DraftVersion.draft_version_id))) or 0
    before_assess = db.scalar(select(func.count(RequirementAssessment.assessment_id))) or 0
    _generate(client, csrf, project_id)
    assert (db.scalar(select(func.count(EvidenceAnchor.anchor_id))) or 0) == before_anchors
    assert (db.scalar(select(func.count(DraftVersion.draft_version_id))) or 0) == before_drafts
    assert (db.scalar(select(func.count(RequirementAssessment.assessment_id))) or 0) == before_assess


def test_generation_guard_once_per_comparison(client, db, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    _seed_imported_public_source(db, project_id, project.workspace_id)
    body, _ = _generate(client, csrf, project_id)
    cid = body["resource_id"]
    before = db.scalar(select(func.count(MarketComparisonItem.item_id)).where(
        MarketComparisonItem.comparison_id == cid)) or 0
    # Re-run the executor directly: guard skips (no duplicate items).
    market_executor.comparison_executor(cid, body["operation_id"])
    db.expire_all()
    after = db.scalar(select(func.count(MarketComparisonItem.item_id)).where(
        MarketComparisonItem.comparison_id == cid)) or 0
    assert after == before


def test_item_status_update(client, db, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    _seed_imported_public_source(db, project_id, project.workspace_id)
    body, _ = _generate(client, csrf, project_id)
    view = client.get(f"/api/v1/market-comparisons/{body['resource_id']}").json()
    item_id = view["items"][0]["item_id"]
    res = client.post(f"/api/v1/market-comparison-items/{item_id}/status",
                      json={"status": "accepted"}, headers=_headers(csrf))
    assert res.status_code == 200 and res.json()["status"] == "accepted"


def test_capability_reflects_market_comparison(client, web_enabled):
    login(client, ANNA_EMAIL, ANNA_PASSWORD)
    caps = client.get("/api/v1/capabilities").json()
    assert caps["features"]["market_comparison"] is True
