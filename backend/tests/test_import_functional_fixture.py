"""Funktionale Abnahme (Ebene B) — On-Disk-Fixture «innolink_structured.pdf».

Beweist auf Mapping-Ebene, dass ein unfertiger Antrag im ÄLTEREN
Innolink-Schema korrekt ausgelesen wird: leere Executive Summary bleibt leer,
Titel/Dauer/Partner/Budget/Antworten entstehen als strukturierte Kandidaten
mit exakten Werten, und die Alt→Neu-Migration (IPR → 4.5.x, alt-4.5 → 4.6)
ist nachvollziehbar. Fixture: rein synthetisches Projekt «TERRAFLUX»
(spike/make_fixture.py, Testdaten-Policy R0.4). Der E2E-Durchstich dazu ist
e2e/import-functional.spec.ts.
"""
from __future__ import annotations

from pathlib import Path

from app.imports.mapping import (
    CONFIDENCE_FOUND,
    CONFIDENCE_UNCERTAIN,
    LEGACY_SCHEMA_MIGRATION_VERSION,
    map_document,
)

FIXTURES = Path(__file__).parent / "import_fixtures"
STRUCTURED_PDF = (FIXTURES / "innolink_structured.pdf").read_bytes()

EXPECTED_TITLE = "TERRAFLUX - Adaptive Bewässerungssteuerung für Stadtgrün"
EXPECTED_TITLE_EN = "TERRAFLUX - Adaptive Irrigation Control for Urban Green"
EXPECTED_PARTNERS = {
    "partner.research.01": ("Nordlicht Institut für Angewandte Forschung", "research_partner"),
    "partner.implementation.01": ("Voltaris AG", "implementation_partner"),
    "partner.implementation.02": ("Brimatec GmbH", "implementation_partner"),
}
EXPECTED_BUDGET = {
    "project.direct_total_project_costs_excluding_overhead": 200000,
    "project.implementation_own_contribution": 105000,
    "project.cash_contribution": 13000,
    "project.total_requested_funding": 82000,
    "project.total_requested_funding_including_overhead": 94300,
}


def _result():
    return map_document("pdf", STRUCTURED_PDF)


def _by_field(result) -> dict[str, object]:
    return {field.field_id: field for field in result.fields}


def _by_target(result) -> dict[str, object]:
    return {c.target_key: c for c in result.structured_candidates}


class TestNarrativeExtraction:
    def test_all_eight_fields_and_no_manual_input(self):
        result = _result()
        assert not result.needs_manual_input
        assert len(result.fields) == 8

    def test_title_and_abstract_have_exact_content(self):
        mapped = _by_field(_result())
        assert mapped["INTRO.APP.NAME"].extracted_text == EXPECTED_TITLE
        assert mapped["INTRO.APP.NAME"].confidence == CONFIDENCE_FOUND
        assert mapped["INTRO.APP.NAME_EN"].extracted_text == EXPECTED_TITLE_EN
        abstract = mapped["INTRO.APP.ABSTRACT"]
        assert abstract.extracted_text.startswith(
            "Das Projekt entwickelt eine adaptive Bewässerungssteuerung"
        )
        assert abstract.confidence == CONFIDENCE_FOUND

    def test_empty_executive_summary_stays_empty(self):
        summary = _by_field(_result())["INTRO.APP.EXECUTIVE_SUMMARY"]
        assert summary.extracted_text == ""
        assert summary.mapping_status == "empty"
        assert summary.confidence == CONFIDENCE_UNCERTAIN

    def test_empty_independence_comment_is_empty_not_invented(self):
        comment = _by_field(_result())[
            "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS"
        ]
        assert comment.extracted_text == ""
        assert comment.mapping_status == "empty"

    def test_zero_management_hours_seed_explanation_draft(self):
        explanation = _by_field(_result())[
            "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION"
        ]
        assert explanation.extracted_text == (
            "No project-management hours are planned (0 of 4000 hours)."
        )
        assert explanation.confidence == CONFIDENCE_UNCERTAIN


class TestLegacyMigration:
    def test_old_structure_3x_maps_directly(self):
        vc = _by_field(_result())["VC.BUSINESS_TARGETS_MODEL.EDITOR"]
        assert [s.target_sections for s in vc.sections] == [
            ("3.1",), ("3.2",), ("3.3",)
        ]
        assert vc.mapping_status == "content_detected"
        assert "Zielmodell ist ein Abo pro Grünfläche" in vc.extracted_text

    def test_legacy_ip_and_partner_suitability_migrate_to_new_structure(self):
        sol = _by_field(_result())["SOL.INNOVATION_SOLUTION.EDITOR"]
        assert sol.mapping_status == "legacy_migrated"
        by_target = {"/".join(s.target_sections): s for s in sol.sections}
        assert by_target["4.5.1"].migration_version == LEGACY_SCHEMA_MIGRATION_VERSION
        assert "synthetische Recherche" in by_target["4.5.1"].candidate_text
        shared = by_target["4.5.2/4.5.3"]
        assert shared.requires_manual_assignment is True
        assert shared.status == "uncertain"
        assert by_target["4.5.4"].migration_version == LEGACY_SCHEMA_MIGRATION_VERSION
        assert "Konsortialvertrag" in by_target["4.5.4"].candidate_text
        assert by_target["4.6"].migration_version == LEGACY_SCHEMA_MIGRATION_VERSION
        assert "ergänzen sich ohne Überschneidung" in by_target["4.6"].candidate_text


class TestStructuredCandidates:
    def test_exactly_fifteen_candidates(self):
        assert len(_result().structured_candidates) == 15

    def test_project_metadata_exact_values(self):
        by_target = _by_target(_result())
        assert by_target["project.title"].payload_json == {"title": EXPECTED_TITLE}
        assert by_target["project.title"].confidence == CONFIDENCE_FOUND
        assert by_target["project.title_en"].payload_json == {
            "title_en": EXPECTED_TITLE_EN
        }
        assert by_target["project.start_date"].payload_json == {
            "start_date": "2026-03-01"
        }
        assert by_target["project.end_date"].payload_json == {
            "end_date": "2027-08-31"
        }
        assert by_target["project.duration_months"].payload_json == {
            "duration_months": 18
        }

    def test_budget_exact_values_and_quotas(self):
        by_target = _by_target(_result())
        for target_key, amount in EXPECTED_BUDGET.items():
            candidate = by_target[target_key]
            field_name = target_key.removeprefix("project.")
            assert candidate.payload_json == {field_name: amount}
            assert candidate.confidence == CONFIDENCE_FOUND
        # Quoten wie im Budget-Precheck (_share): Eigenleistung 52.5 %,
        # Barbeitrag 6.5 % der direkten Projektkosten.
        direct = EXPECTED_BUDGET[
            "project.direct_total_project_costs_excluding_overhead"
        ]
        own = EXPECTED_BUDGET["project.implementation_own_contribution"]
        cash = EXPECTED_BUDGET["project.cash_contribution"]
        assert round(own / direct * 100, 2) == 52.5
        assert round(cash / direct * 100, 2) == 6.5

    def test_three_partners_with_confirmed_independence(self):
        by_target = _by_target(_result())
        for target_key, (name, partner_type) in EXPECTED_PARTNERS.items():
            payload = by_target[target_key].payload_json
            assert payload["name"] == name
            assert payload["partner_type"] == partner_type
            assert payload["country"] == "CH"
            assert payload["personnel_independence_status"] == "confirmed"
            assert payload["financial_independence_status"] == "confirmed"
            assert payload["personnel_answers"] == [False, False, False]
            assert payload["financial_confirmations"] == [True, True]
            assert by_target[target_key].confidence == CONFIDENCE_FOUND

    def test_scientific_integrity_answer_without_foreign_comment(self):
        candidate = _by_target(_result())["answer.scientific_integrity"]
        # Regression: Der leere Unabhängigkeits-Kommentar («Explanations and
        # Comments») darf nie als Integritätskommentar erscheinen.
        assert candidate.payload_json == {"sanction_answer": False, "comment": None}
        assert candidate.confidence == CONFIDENCE_FOUND

    def test_management_hours_zero_with_total(self):
        candidate = _by_target(_result())["answer.management_hours"]
        assert candidate.payload_json == {
            "management_hours": 0,
            "total_project_hours": 4000,
        }
        assert candidate.confidence == CONFIDENCE_FOUND
