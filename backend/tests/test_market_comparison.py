"""Milestone 9I-B — market & competitor comparison (fake provider only, no network).

Covers: imported-public-source scope + deterministic pre-filter, the beta-internal
structuring agent (fake), standalone deterministic quote verification, source-backed vs
needs_review items, dedup, data-policy gating, no draft/assessment/approval mutation,
comparison-scoped guard, and no provider/key leak.
"""
from __future__ import annotations

import hashlib
import uuid
import time

import pytest
from sqlalchemy import func, select

from app.config.settings import get_settings
from app.db.models import (
    DraftVersion,
    EvidenceAnchor,
    EvidenceLink,
    MarketComparison,
    MarketComparisonItem,
    Project,
    ResearchResult,
    ResearchTask,
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
    monkeypatch.setattr(s, "web_research_fake_provider", False)
    monkeypatch.setattr(s, "firecrawl_api_key", "unit-test-key")
    from app.agents.providers.fake import FakeProvider

    monkeypatch.setattr(
        market_executor,
        "_resolver",
        lambda candidates: (
            lambda _route: FakeProvider(raw_output=market_executor._fake_bundle(candidates))
        ),
    )
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


def _seed_imported_public_source(
    db,
    project_id,
    workspace_id,
    text=MARKET_TEXT,
    *,
    content_review_status="reviewed",
    support_status="supports",
    result_status="imported",
    result_safety_status="passed",
    execution_mode="live",
    document_status="processed",
    version_status="processed",
    source_url: str | None = None,
):
    """Insert a web-imported public SourceDocument(type=url) + version + one fragment."""
    doc_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    effective_url = source_url or "https://public.example.test/market-report"
    dc = {"sensitivity": "public", "origin": "public_source",
          "processing_mode": "deterministic_only", "web_research_mode": "validated_public",
          "nda_applies": False}
    db.add(SourceDocument(
        source_id=doc_id, project_id=project_id, workspace_id=workspace_id,
        name="Öffentliche Webquelle", type="url", status=document_status,
        data_classification=dc, current_source_version_id=version_id,
        created_by="user-anna",
    ))
    db.add(SourceVersion(
        source_version_id=version_id, source_document_id=doc_id, version_number=1,
        original_content_hash=hashlib.sha256(text.encode()).hexdigest(),
        normalized_content_hash=hashlib.sha256(text.encode()).hexdigest(),
        normalized_text=text, normalizer_version="normalizer-1",
        processing_status=version_status, data_classification=dc,
        storage_ref="ref", original_filename="web", byte_size=len(text), mime_type="text/plain",
        content_review_status=content_review_status,
        content_safety_status="passed",
    ))
    db.add(SourceFragment(
        fragment_id=str(uuid.uuid4()), source_version_id=version_id, ordinal=0,
        original_text=text, normalized_text=text, start_offset=0, end_offset=len(text),
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
    ))
    task_id = str(uuid.uuid4())
    db.add(ResearchTask(
        research_task_id=task_id, project_id=project_id, workspace_id=workspace_id,
        created_by="user-anna", purpose="market_comparison", subject_type="topic",
        query_text="public market comparison", normalized_query_hash="unit-test",
        status="succeeded", preferred_domains=[], disallowed_domains=[],
        competence_needs=[], requested_partner_roles=[], max_results=1, max_pages=1,
        provider="firecrawl", execution_mode=execution_mode, result_count=1,
        firewall_data_class="D0_PUBLIC", research_module="competition_alternatives",
        planner_purpose="competitors_alternatives",
    ))
    db.add(ResearchResult(
        result_id=str(uuid.uuid4()), research_task_id=task_id, workspace_id=workspace_id,
        source_url=effective_url,
        final_url=effective_url, title="Public market report",
        snippet="Public candidate snippet", status=result_status,
        content_safety_status=result_safety_status,
        content_review_status=content_review_status,
        support_status=support_status,
        source_document_id=doc_id,
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


def _seed_comparison_sources(db, project_id, workspace_id, **kwargs):
    """RUN 3B full-comparison fixture: three independent reviewed sources."""
    return [
        _seed_imported_public_source(db, project_id, workspace_id, **kwargs)
        for _ in range(3)
    ]


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


@pytest.mark.parametrize(
    ("content_review_status", "support_status", "result_status"),
    [
        ("unreviewed", "not_checked", "imported"),
        ("reviewed", "does_not_support", "imported"),
        ("reviewed", "supports", "rejected"),
    ],
)
def test_source_scope_excludes_unreviewed_non_supporting_and_rejected_results(
    client, db, web_enabled, content_review_status, support_status, result_status
):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    _seed_imported_public_source(
        db,
        project_id,
        project.workspace_id,
        content_review_status=content_review_status,
        support_status=support_status,
        result_status=result_status,
    )
    assert source_scope.imported_public_sources(
        db, project_id, project.workspace_id
    ) == []


@pytest.mark.parametrize(
    ("execution_mode", "document_status", "version_status"),
    [
        ("fake_demo", "processed", "processed"),
        ("live", "processing", "processed"),
        ("live", "processed", "pending"),
    ],
)
def test_source_scope_excludes_demo_and_incomplete_sources(
    client, db, web_enabled, execution_mode, document_status, version_status
):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    _seed_imported_public_source(
        db,
        project_id,
        project.workspace_id,
        execution_mode=execution_mode,
        document_status=document_status,
        version_status=version_status,
    )
    assert source_scope.imported_public_sources(
        db, project_id, project.workspace_id
    ) == []


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
    _seed_comparison_sources(db, project_id, project.workspace_id)
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
    assert quote["linked_evidence_anchor_id"]
    assert item["external_evidence_anchor_ids"] == [quote["linked_evidence_anchor_id"]]
    assert item["cell_evidence"]["name"] == item["external_evidence_anchor_ids"]
    assert view["research_gaps"]
    # Allow-listed provenance is visible; raw provider output is not persisted.
    assert view["provider"] and view["model_ref"] and view["context_hash"]
    assert len(view["source_version_ids"]) == 3


def _seed_reviewed_public_source_without_market_signal(
    db,
    project_id: str,
    workspace_id: str,
    *,
    index: int | None = None,
) -> tuple[str, str, str]:
    """Seed a reviewed, supported imported public source without market-signal terms."""
    idx_suffix = f" {index}" if index is not None else ""
    doc_id, version_id = _seed_imported_public_source(
        db,
        project_id,
        workspace_id,
        text=(
            "In diesem Abschnitt wird ein Projektplan beschrieben, inklusive "
            "organisatorischer Schritte, Rollen und Zeitplanangaben ohne "
            "marktbezogenen Inhalt." + idx_suffix
        ),
        source_url=f"https://public.example.test/market-report-{uuid.uuid4()}",
    )
    result = db.scalar(select(ResearchResult).where(
        ResearchResult.source_document_id == doc_id
    ))
    assert result is not None
    # Keep the historical review path explicit for the full BFF-style chain.
    return result.result_id, doc_id, version_id


def test_market_comparison_two_reviewed_live_sources_becomes_limited(client, db, web_enabled):
    """Regression for market-scope recovery: two reviewed live public sources are counted,
    but with no markt-relevante Begriffe darf der Vergleich nur als limited enden."""
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    source_version_ids: list[str] = []
    result_ids: list[str] = []
    source_ids: list[str] = []
    anchor_ids: list[str] = []

    for idx in range(2):
        result_id, _doc_id, version_id = _seed_reviewed_public_source_without_market_signal(
            db, project_id, project.workspace_id, index=idx
        )
        review = client.post(
            f"/api/v1/research-results/{result_id}/review",
            json={"decision": "supports"},
            headers=unsafe_headers(csrf),
        )
        assert review.status_code == 200, review.text

        result = db.get(ResearchResult, result_id)
        assert result is not None
        result_ids.append(result_id)
        source_version_ids.append(version_id)
        source_ids.append(result.source_document_id)
        document = db.get(SourceDocument, result.source_document_id)
        assert document is not None
        task = db.get(ResearchTask, result.research_task_id)
        assert task is not None
        assert task.execution_mode == "live"
        assert result.content_review_status == "reviewed"
        assert result.support_status == "supports"

        fragment = db.scalar(select(SourceFragment).where(
            SourceFragment.source_version_id == version_id
        ))
        assert fragment is not None
        passages = client.get(
            f"/api/v1/research-results/{result_id}/anchor-passages"
        ).json()
        assert passages and passages != []
        passage = passages[0]
        assert passage is not None
        assert passage["start_offset"] < passage["end_offset"] <= len(fragment.normalized_text)
        assert passage["safety_status"] in {"passed", "human_released"}
        assert passage["content_review_status"] == "reviewed"

        anchor = client.post(
            f"/api/v1/research-results/{result_id}/external-anchors",
            json={
                "fragment_id": fragment.fragment_id,
                "quote": passage["excerpt"],
            },
            headers=_headers(csrf),
        )
        assert anchor.status_code == 200, anchor.text
        anchor_data = anchor.json()
        assert anchor_data["source_id"] == result.source_document_id
        assert anchor_data["source_version_id"] == version_id
        assert anchor_data["scope"] == "external"
        assert anchor_data["verification_status"] == "exact_verified"
        anchor_ids.append(anchor_data["anchor_id"])

    assert len(result_ids) == 2
    assert len(source_ids) == 2
    assert len(set(source_ids)) == 2
    assert len(anchor_ids) == 2
    assert len(set(anchor_ids)) == 2
    source_rows = source_scope.imported_public_sources(db, project_id, project.workspace_id)
    assert len(source_rows) == 2
    assert set(result_ids) == set(rr.result_id for rr in db.scalars(
        select(ResearchResult).where(
            ResearchResult.source_document_id.in_([row.source_id for row in source_rows])
        )
    ))
    assert all(row.project_id == project_id and row.workspace_id == project.workspace_id for row in source_rows)
    assert len(source_rows[0].source_id) > 0 and len(source_rows[1].source_id) > 0
    fragments = source_scope.prefilter_fragments(db, source_rows)
    assert fragments == []
    assert len(source_rows[0].source_id) > 0 and len(source_rows[1].source_id) > 0
    assert len(source_rows[0].current_source_version_id or "") > 0
    assert len(source_rows[1].current_source_version_id or "") > 0

    result_rows = list(db.scalars(
        select(ResearchResult).where(ResearchResult.source_document_id.in_([row.source_id for row in source_rows]))
    ))
    assert len(result_rows) == 2
    assert len(set((r.final_url or r.source_url) for r in result_rows)) == 2
    version_rows = list(db.scalars(
        select(SourceVersion).where(SourceVersion.source_version_id.in_(source_version_ids))
    ))
    assert len(version_rows) == 2
    assert len(set(v.normalized_content_hash for v in version_rows)) == 2
    assert all(v.processing_status == "processed" for v in version_rows)
    assert all(v.content_review_status == "reviewed" for v in version_rows)
    assert all(v.content_safety_status in {"passed", "human_released"} for v in version_rows)
    anchors = list(db.scalars(select(EvidenceAnchor).where(EvidenceAnchor.anchor_id.in_(anchor_ids))))
    assert len(anchors) == 2
    assert {a.scope for a in anchors} == {"external"}
    assert {a.verification_status for a in anchors} == {"exact_verified"}
    assert all(a.start_offset is not None and a.end_offset is not None for a in anchors)
    links = list(db.scalars(select(EvidenceLink).where(
        EvidenceLink.anchor_id.in_(anchor_ids),
        EvidenceLink.target_type == "market_comparison_item",
    )))
    assert len(links) == 0

    created = client.post(
        f"/api/v1/projects/{project_id}/market-comparisons", headers=_headers(csrf)
    )
    assert created.status_code == 202, created.text
    created_body = created.json()
    op_id = created_body["operation_id"]
    poll = client.get(f"/api/v1/operations/{op_id}")
    assert poll.status_code == 200
    for _ in range(20):
        poll = client.get(f"/api/v1/operations/{op_id}")
        assert poll.status_code == 200
        state = poll.json()
        if state.get("status") in {"succeeded", "failed", "cancelled"}:
            break
        time.sleep(0.05)
    assert state["status"] == "succeeded"

    view = client.get(f"/api/v1/market-comparisons/{created_body['resource_id']}").json()
    assert view["status"] == "limited"
    assert "limited_external_evidence" in view["warnings"]
    assert view["item_count"] == 0
    assert len(view["items"]) == 0
    assert len(view["source_version_ids"]) == 2
    assert len(set(view["source_version_ids"])) == 2
    assert set(view["source_version_ids"]) == set(source_version_ids)
    assert view["source_version_ids"] == sorted(view["source_version_ids"])


def test_view_exposes_judgment_landscape_and_market_picture(client, db, web_enabled):
    """The read-time view layers the analytical objects on top of the persisted
    comparison: candidates carry a candidate_type, market statistics stay out of
    the landscape, and the judgment never claims global nonexistence."""
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    _seed_comparison_sources(
        db, project_id, project.workspace_id,
        text=(
            "Die Plattform Acme ist eine alternative Lösung für den Markt. "
            "Der Markt wächst laut Bericht. Kunden beschreiben ein Problem."
        ),
    )
    body, op = _generate(client, csrf, project_id)
    assert op["status"] == "succeeded"
    view = client.get(f"/api/v1/market-comparisons/{body['resource_id']}").json()

    assert view["solution_landscape"] is not None
    assert view["market_picture"] is not None
    assert view["competition_judgment"] is not None
    assert view["scope_stale"] is False

    landscape = view["solution_landscape"]
    types = {c["candidate_type"] for c in landscape["candidates"]}
    assert "adjacent_solution" in types  # from legacy alternative_solution
    # Market statistics never appear as a solution candidate.
    assert all(c["name"] and c["candidate_type"] for c in landscape["candidates"])
    assert not any("Markt-Claim" in c["name"] for c in landscape["candidates"])

    judgment = view["competition_judgment"]
    assert judgment["status"] in (
        "direct_equivalent_found", "similar_solutions_found",
        "no_direct_equivalent_in_scope", "insufficient_evidence",
    )
    joined = " ".join(judgment["disallowed_formulations"])
    for phrase in ("weltweit einzigartig", "keine Konkurrenz", "patentierbar"):
        assert phrase in joined
    # An unreviewed source-backed candidate is plausible, never a confirmed claim.
    assert judgment["evidenced_differentiators"] == []
    # The flat items[] are enriched too (regression: previously dead code).
    assert any(item.get("candidate_type") for item in view["items"])


def test_view_exposes_the_project_idea_as_comparison_basis(client, db, web_enabled):
    """Ziel 1: die eigene Projektidee ist die sichtbare Vergleichsbasis."""
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    _seed_comparison_sources(db, project_id, project.workspace_id)
    body, op = _generate(client, csrf, project_id)
    assert op["status"] == "succeeded"
    view = client.get(f"/api/v1/market-comparisons/{body['resource_id']}").json()

    basis = view["comparison_basis"]
    assert basis is not None
    # idea = the confidential project description the user typed at intake.
    assert basis["idea"] == project.description
    assert basis["title"] == project.title
    # No approved research brief seeded → no public-safe search focus yet.
    assert basis["search_focus"] is None
    assert basis["search_aspects"] == []


def test_comparison_basis_adds_public_safe_search_focus_from_approved_brief(client, db, web_enabled):
    from app.db.models import ResearchBrief

    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    db.add(ResearchBrief(
        research_brief_id=str(uuid.uuid4()), project_id=project_id,
        workspace_id=project.workspace_id, version=1, status="approved",
        research_goal="Lösungen zur automatisierten Anomalieerkennung im Zielmarkt",
        application_domain="Qualitätssicherung", technology_class="Machine Learning",
        region="Schweiz", search_tags=["anomaly detection", "industrie"],
        content_hash="unit-test-hash", created_by="user-anna", approved_by="user-anna",
    ))
    db.commit()
    _seed_comparison_sources(db, project_id, project.workspace_id)
    body, op = _generate(client, csrf, project_id)
    assert op["status"] == "succeeded"
    view = client.get(f"/api/v1/market-comparisons/{body['resource_id']}").json()

    basis = view["comparison_basis"]
    assert basis["search_focus"] == "Lösungen zur automatisierten Anomalieerkennung im Zielmarkt"
    assert "Qualitätssicherung" in basis["search_aspects"]
    assert "Schweiz" in basis["search_aspects"]
    assert len(basis["search_aspects"]) <= 6


def test_market_size_and_customer_problem_categories(client, db, web_enabled):
    """R8 (Anforderung 11): die persistierte Zusammenfassung strukturiert auch
    Marktgrössen-Kandidaten und Kundenprobleme — nur mit verifiziertem Zitat,
    nie als gesicherte Tatsache (Anforderung 12)."""
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    _seed_comparison_sources(
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
    assert view["status"] == "insufficient_external_evidence"
    assert view["item_count"] == 0
    assert view["research_gaps"]  # rule 13: gaps instead of invented content
    assert "inhaltlich positiv geprüften" in view["research_gaps"][0]
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


def test_unsupported_item_quote_becomes_research_gap(client, db, web_enabled, monkeypatch):
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
    _seed_comparison_sources(db, project_id, project.workspace_id)
    body, op = _generate(client, csrf, project_id)
    assert op["status"] == "succeeded"
    view = client.get(f"/api/v1/market-comparisons/{body['resource_id']}").json()
    assert view["items"] == []
    assert any("exakte Fundstelle" in gap for gap in view["research_gaps"])


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
    _seed_comparison_sources(db, project_id, project.workspace_id)
    body, _ = _generate(client, csrf, project_id)
    view = client.get(f"/api/v1/market-comparisons/{body['resource_id']}").json()
    assert view["item_count"] == 1


def test_external_anchor_created_without_draft_or_assessment_mutation(client, db, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    _seed_comparison_sources(db, project_id, project.workspace_id)
    before_anchors = db.scalar(select(func.count(EvidenceAnchor.anchor_id))) or 0
    before_drafts = db.scalar(select(func.count(DraftVersion.draft_version_id))) or 0
    before_assess = db.scalar(select(func.count(RequirementAssessment.assessment_id))) or 0
    _generate(client, csrf, project_id)
    assert (db.scalar(select(func.count(EvidenceAnchor.anchor_id))) or 0) > before_anchors
    assert (db.scalar(select(func.count(DraftVersion.draft_version_id))) or 0) == before_drafts
    assert (db.scalar(select(func.count(RequirementAssessment.assessment_id))) or 0) == before_assess


def test_generation_guard_once_per_comparison(client, db, web_enabled):
    csrf = login(client, ANNA_EMAIL, ANNA_PASSWORD)
    project_id = _create_project(client, csrf)
    project = db.get(Project, project_id)
    _seed_comparison_sources(db, project_id, project.workspace_id)
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
    _seed_comparison_sources(db, project_id, project.workspace_id)
    body, _ = _generate(client, csrf, project_id)
    view = client.get(f"/api/v1/market-comparisons/{body['resource_id']}").json()
    item_id = view["items"][0]["item_id"]
    res = client.post(f"/api/v1/market-comparison-items/{item_id}/status",
                      json={"status": "accepted"}, headers=_headers(csrf))
    assert res.status_code == 409
    assert res.json()["code"] == "demo_comparison_not_acceptable"


def test_capability_reflects_market_comparison(client, db, web_enabled):
    """Live-Konfiguration allein reicht seit dem Live-Preflight-Vertrag nicht:
    ein Live-Provider gilt erst nach einem erfolgreichen, persistierten
    Preflight als betriebsbereit (kein stiller Übergang). Die Fixture seedet
    diesen Preflight realistisch über denselben Persistenzpfad wie der
    Admin-Endpoint — die Preflight-Pflicht selbst bleibt unangetastet."""
    from app.evaluation.preflight import (
        PASS,
        PreflightCheck,
        ProviderPreflight,
        persist_route_preflight,
    )

    login(client, ANNA_EMAIL, ANNA_PASSWORD)
    # Ohne persistierten Preflight: ehrlich nicht betriebsbereit.
    caps = client.get("/api/v1/capabilities").json()
    assert caps["features"]["market_comparison"] is False
    assert caps["features"]["web_research"] is False

    persist_route_preflight(
        db,
        ProviderPreflight(
            provider="firecrawl", mode="live", route_key="firecrawl",
            checks=[
                PreflightCheck(
                    "api_reachable", PASS, "Firecrawl-Suche hat geantwortet."
                )
            ],
            latency_ms=42,
        ),
        triggered_by="user-anna",
    )
    db.commit()

    caps = client.get("/api/v1/capabilities").json()
    assert caps["features"]["market_comparison"] is True
    assert caps["features"]["web_research"] is True
