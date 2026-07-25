"""Deterministic market judgment (Marktbild / Lösungslandschaft / Gesamturteil).

Pure, DB-free unit tests over app.market.judgment. Encodes the hard rules:
market statistics are never candidates, an exact quote is not a confirmed claim,
not_checked is never "absent"/"not supported", no overclaim/percent, and the four
judgment states are chosen deterministically.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.contracts.market import MarketComparison as Cmp, MarketComparisonItem as Item
from app.market import judgment

_HARD_PHRASES = ["weltweit einzigartig", "keine Konkurrenz", "Es existiert keine solche Lösung"]
_PATENT_PHRASES = ["patentierbar", "Freedom to Operate"]


def item(**over) -> Item:
    base = dict(
        item_id="i-" + over.get("name", "x"),
        name="Acme",
        category="competitor",
        relation_to_project="competing",
        confidence_label="source_backed",
        status="proposed",
        support_status="unreviewed",
        relevant_functions=[],
        differentiation_relevance=None,
    )
    base.update(over)
    return Item(**base)


def cmp(**over) -> Cmp:
    base = dict(
        comparison_id="c1", project_id="p1", workspace_id="w1",
        status="ready_for_review", comparison_version=1,
        source_version_ids=["v1", "v2"], research_gaps=[], warnings=[],
        created_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
        updated_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
    )
    base.update(over)
    return Cmp(**base)


# --- candidate_type mapping -------------------------------------------------

def test_legacy_category_maps_to_candidate_type():
    assert judgment.candidate_type_for(item(category="competitor")) == "direct_competitor"
    assert judgment.candidate_type_for(item(category="alternative_solution")) == "adjacent_solution"
    assert judgment.candidate_type_for(item(category="reference_solution")) == "reference_infrastructure"
    assert judgment.candidate_type_for(item(category="incumbent_process")) == "manual_or_internal_alternative"
    assert judgment.candidate_type_for(item(category="substitute")) == "substitute"


def test_market_statistics_are_never_candidates():
    for category in ("market_size_claim", "customer_problem", "unknown"):
        assert judgment.candidate_type_for(item(category=category)) is None


def test_open_source_detection():
    assert judgment.candidate_type_for(
        item(category="alternative_solution", name="ToolX", offering_summary="An open source library")
    ) == "open_source_solution"


def test_market_statistics_never_enter_the_landscape():
    items = [
        item(name="A", category="competitor", relevant_functions=["f1"]),
        item(name="M", category="market_size_claim"),
        item(name="P", category="customer_problem"),
    ]
    landscape = judgment.build_solution_landscape(items, scope_ok=True)
    assert [c.name for c in landscape.candidates] == ["A"]
    assert "market_size_claim" not in {c.candidate_type for c in landscape.candidates}


# --- evidenced vs plausible-but-unverified ----------------------------------

def test_unreviewed_quote_is_plausible_not_evidenced():
    it = item(confidence_label="source_backed", support_status="unreviewed",
              differentiation_relevance="Zentrale Architektur unterscheidet sich")
    evidenced, unverified = judgment.split_differentiators(it)
    assert evidenced == []
    assert unverified and "Zentrale Architektur" in unverified[0]


def test_confirmed_quote_is_evidenced():
    it = item(confidence_label="source_backed", support_status="supports",
              differentiation_relevance="Zentrale Architektur unterscheidet sich")
    evidenced, unverified = judgment.split_differentiators(it)
    assert evidenced and unverified == []


def test_does_not_support_is_dropped_not_treated_as_missing():
    it = item(support_status="does_not_support", differentiation_relevance="Etwas")
    assert judgment.split_differentiators(it) == ([], [])


# --- four judgment states ---------------------------------------------------

def test_direct_equivalent_found():
    items = [item(name="Rival", category="competitor", confidence_label="source_backed",
                  support_status="supports", relation_to_project="competing",
                  relevant_functions=["Erkennung", "Meldung"])]
    landscape = judgment.build_solution_landscape(items, scope_ok=True)
    j = judgment.build_competition_judgment(cmp(), items, landscape, scope_stale=False)
    assert j.status == "direct_equivalent_found"
    assert j.can_insert_into_application is True


def test_similar_solutions_found():
    items = [item(name="Adj", category="alternative_solution", confidence_label="source_backed",
                  support_status="supports", relation_to_project="similar",
                  relevant_functions=["Erkennung"])]
    landscape = judgment.build_solution_landscape(items, scope_ok=True)
    j = judgment.build_competition_judgment(cmp(), items, landscape, scope_stale=False)
    assert j.status == "similar_solutions_found"


def test_no_direct_equivalent_in_scope_when_only_peripheral_or_no_overlap():
    items = [item(name="Ref", category="reference_solution", confidence_label="source_backed",
                  support_status="supports", relation_to_project="reference",
                  relevant_functions=["Infrastruktur"])]
    landscape = judgment.build_solution_landscape(items, scope_ok=True)
    j = judgment.build_competition_judgment(cmp(), items, landscape, scope_stale=False)
    assert j.status == "no_direct_equivalent_in_scope"
    assert "Im definierten Suchumfang" in j.rationale


def test_insufficient_evidence_without_source_backed_candidate():
    items = [item(name="Weak", confidence_label="needs_review", status="needs_human_review")]
    landscape = judgment.build_solution_landscape(items, scope_ok=True)
    j = judgment.build_competition_judgment(cmp(), items, landscape, scope_stale=False)
    assert j.status == "insufficient_evidence"
    assert j.can_insert_into_application is False
    assert j.allowed_formulations == []


def test_runtime_limited_forces_insufficient_evidence():
    items = [item(name="Rival", category="competitor", confidence_label="source_backed",
                  support_status="supports", relevant_functions=["a", "b"])]
    landscape = judgment.build_solution_landscape(items, scope_ok=True)
    j = judgment.build_competition_judgment(cmp(status="limited"), items, landscape, scope_stale=False)
    assert j.status == "insufficient_evidence"


# --- not_checked never becomes "absent" -------------------------------------

def test_unreviewed_candidate_is_open_gap_not_absent():
    items = [item(name="Maybe", category="competitor", confidence_label="source_backed",
                  support_status="unreviewed", relevant_functions=["a", "b"])]
    landscape = judgment.build_solution_landscape(items, scope_ok=True)
    j = judgment.build_competition_judgment(cmp(), items, landscape, scope_stale=False)
    # A found-but-unconfirmed competitor still establishes a similar solution;
    # it is flagged as an open gap, never as "no solution exists".
    assert j.status in ("direct_equivalent_found", "similar_solutions_found")
    assert any("noch nicht bestätigt" in g for g in j.open_evidence_gaps)


# --- overclaim guard + no percentages ---------------------------------------

def test_disallowed_formulations_present_in_every_status():
    scenarios = [
        [item(name="R", category="competitor", confidence_label="source_backed",
              support_status="supports", relevant_functions=["a", "b"])],
        [item(name="A", category="alternative_solution", confidence_label="source_backed",
              support_status="supports", relevant_functions=["a"])],
        [item(name="Ref", category="reference_solution", confidence_label="source_backed",
              support_status="supports")],
        [item(name="W", confidence_label="needs_review", status="needs_human_review")],
    ]
    for items in scenarios:
        landscape = judgment.build_solution_landscape(items, scope_ok=True)
        j = judgment.build_competition_judgment(cmp(), items, landscape, scope_stale=False)
        joined = " ".join(j.disallowed_formulations)
        for phrase in _HARD_PHRASES + _PATENT_PHRASES:
            assert phrase in joined
        # No opaque percentages or forbidden phrases in what may be inserted.
        allowed = " ".join(j.allowed_formulations)
        assert "%" not in allowed
        for phrase in _HARD_PHRASES + _PATENT_PHRASES:
            assert phrase not in allowed


def test_scope_stale_blocks_insertion_without_touching_status():
    items = [item(name="Rival", category="competitor", confidence_label="source_backed",
                  support_status="supports", relevant_functions=["a", "b"])]
    landscape = judgment.build_solution_landscape(items, scope_ok=False)
    j = judgment.build_competition_judgment(cmp(), items, landscape, scope_stale=True)
    assert j.status == "direct_equivalent_found"  # runtime judgment unchanged
    assert j.can_insert_into_application is False
    assert any("Suchraum" in g for g in j.open_evidence_gaps)


def test_determinism_same_input_same_output():
    items = [item(name="Rival", category="competitor", confidence_label="source_backed",
                  support_status="supports", relevant_functions=["a", "b"])]
    a = judgment.build_competition_judgment(
        cmp(), items, judgment.build_solution_landscape(items, scope_ok=True), scope_stale=False
    )
    b = judgment.build_competition_judgment(
        cmp(), items, judgment.build_solution_landscape(items, scope_ok=True), scope_stale=False
    )
    assert a.model_dump() == b.model_dump()
