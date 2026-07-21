from __future__ import annotations

from app.agents.suggestion_grounding import extract_concrete_claims, validate_grounding


def test_independent_extractor_finds_undeclared_number_and_organisation():
    claims = extract_concrete_claims(
        "Die Musterwerke AG erreicht 27 Prozent Marktanteil im Jahr 2025."
    )
    assert {item.claim_type for item in claims} >= {"number", "organization"}
    assert any(item.value == "27 Prozent" for item in claims)
    assert any("Musterwerke AG" in item.value for item in claims)


def test_grounding_accepts_original_and_selected_anchor_only():
    result = validate_grounding(
        "Das Projekt dauert 18 Monate. Die Musterwerke AG ist Vergleichsanbieterin.",
        original_text="Die geplante Dauer beträgt 18 Monate.",
        structured_project_data={},
        anchors=[{"anchor_id": "anchor-1", "quote": "Musterwerke AG bietet die Referenzlösung an."}],
    )
    assert result.unsupported_critical == []
    assert result.anchor_ids_by_claim["18 Monate"] == []
    assert result.anchor_ids_by_claim["Musterwerke AG"] == ["anchor-1"]


def test_grounding_rejects_claim_missing_from_model_claim_map_and_context():
    result = validate_grounding(
        "Die erfundene Marktgrösse beträgt CHF 42 Mio.",
        original_text="Noch keine Marktgrösse bekannt.",
        structured_project_data={},
        anchors=[],
    )
    assert result.unsupported_critical
    assert "unsupported_concrete_claim" in result.warnings


def test_section_numbers_are_not_treated_as_factual_numbers():
    claims = extract_concrete_claims("4.2 Neuheit: klare Abgrenzung. 4.3 Ziele: messbar.")
    assert claims == []

