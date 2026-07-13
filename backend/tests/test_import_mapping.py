"""R3.1 — deterministisches Import-Mapping (Portierung des Gate-Spikes).

Fixtures: ausschliesslich synthetische PDFs (fiktives Projekt «SmartGrid
Optimizer», siehe spike/make_fixture.py; Testdaten-Policy). Das anonymisierte
Gate-PDF folgt erst nach E-12-Owner-Review als drittes Fixture.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.exports.generators.common import EXPORT_FIELD_LABELS
from app.imports.mapping import (
    CONFIDENCE_FOUND,
    CONFIDENCE_UNCERTAIN,
    FIELDS,
    LEGACY_SCHEMA_MIGRATION_VERSION,
    MAPPING_VERSION,
    MappingResult,
    map_document,
    map_parse_result,
)
from app.ingestion.parsers import ParseResult, ParserError
from tests.fixtures import make_text_pages_pdf

FIXTURES = Path(__file__).parent / "import_fixtures"
CLEAN_PDF = (FIXTURES / "innolink_sample.pdf").read_bytes()
DEGRADED_PDF = (FIXTURES / "innolink_sample_degraded.pdf").read_bytes()

STRUCTURED_LEGACY_PDF = make_text_pages_pdf(
    [
        [
            "AURORA",
            "Application",
            "Title in English:",
            "AURORA",
            "Project Duration:",
            "24 months",
        ],
        [
            "1. Introduction",
            "Abstract",
            "Please note, the abstract will be published.",
            "A synthetic abstract with a strict boundary.",
            "Management Summary",
            "Please note, the executive summary is internal.",
            "Context",
            "This context must never become a management summary.",
            "Scientific Integrity",
            "A separate portal answer.",
            "Intellectual Property Rights",
        ],
        [
            "Was a patent search performed with or without IPI (Swiss Federal Institute for Intellectual",
            "Property)?",
            "Yes",
            "A synthetic search found two potentially related documents.",
            "Have the project partners concluded a prior written agreement regarding the assignement or",
            "exploitation of any research findings or patents?",
            "No",
            "Does the project require (patent-)licencense(s)? If yes, please explain which background IP is",
            "needed for the project and the ownership of that background IP.",
            "Yes",
            "2. Organisations and People",
        ],
        [
            "3. Value Creation",
            "3.1 Describe the business targets and the business model.",
            "Three pilot customers are planned.",
            "3.2 Describe potential customers and how they are to be reached",
            "Hospitals are reached through existing channels.",
        ],
        [
            "3.3 Does the planned project have a particular relevance to energy or ecological or social topics?",
            "The synthetic project improves access to services.",
            "4. Solution",
        ],
        [
            "4.1 Describe the state of the art that you intend to advance.",
            "Existing systems lack the planned interface.",
            "4.2 Describe the novelty of your solution (technology, product, business model or process, service)",
            "The synthetic interface is new in this test case.",
            "4.3 Describe the quantifiable goals to reach.",
            "Latency below one second is the target.",
            "4.4 Describe the preliminary work already performed.",
            "A laboratory prototype was tested.",
            "4.5 Describe how the selected partners are suited for the planned project.",
            "The partners provide complementary synthetic capabilities.",
            "5. Project Setup",
            "Risk Management",
            "A separate risk answer.",
        ],
    ]
)


def _by_field(result: MappingResult) -> dict[str, object]:
    return {m.field_id: m for m in result.fields}


class TestFieldCoverage:
    def test_import_fields_match_export_labels_exactly(self):
        assert {fp.field_id for fp in FIELDS} == set(EXPORT_FIELD_LABELS)

    def test_labels_come_from_export_label_map(self):
        mapped = _by_field(map_document("pdf", CLEAN_PDF))
        for field_id, m in mapped.items():
            assert m.label == EXPORT_FIELD_LABELS[field_id]


class TestCleanFixture:
    """Spike-Regression: das saubere Fixture mappt alle 8 Felder korrekt."""

    def test_all_eight_fields_are_mapped(self):
        result = map_document("pdf", CLEAN_PDF)
        assert not result.needs_manual_input
        assert {m.field_id for m in result.fields} == set(EXPORT_FIELD_LABELS)

    def test_expected_content_prefixes(self):
        mapped = _by_field(map_document("pdf", CLEAN_PDF))
        assert mapped["INTRO.APP.NAME"].extracted_text.startswith("SmartGrid Optimizer")
        assert mapped["INTRO.APP.ABSTRACT"].extracted_text.startswith(
            "Das Projekt entwickelt eine adaptive Lastprognose"
        )
        assert mapped["INTRO.APP.EXECUTIVE_SUMMARY"].extracted_text.startswith(
            "Verteilnetzbetreiber stehen vor stark schwankenden"
        )
        assert mapped[
            "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS"
        ].extracted_text.startswith("Die Netzwerk Stadt AG hält eine Minderheitsbeteiligung")
        assert mapped["PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION"].extracted_text.startswith(
            "Die Management-Stunden verteilen sich"
        )

    def test_editor_fields_keep_markers_but_remove_portal_questions(self):
        mapped = _by_field(map_document("pdf", CLEAN_PDF))
        vc = mapped["VC.BUSINESS_TARGETS_MODEL.EDITOR"]
        sol = mapped["SOL.INNOVATION_SOLUTION.EDITOR"]
        assert vc.confidence == CONFIDENCE_FOUND
        assert sol.confidence == CONFIDENCE_FOUND
        assert vc.extracted_text.startswith("3.1\n")
        assert sol.extracted_text.startswith("4.1\n")
        assert "Which business targets" not in vc.extracted_text
        assert "What is the innovation" not in sol.extracted_text

    def test_empty_started_field_is_uncertain_not_filled(self):
        # NAME_EN existiert im Fixture als Label ohne Inhalt (nur Zeichenzähler).
        mapped = _by_field(map_document("pdf", CLEAN_PDF))
        name_en = mapped["INTRO.APP.NAME_EN"]
        assert name_en.extracted_text == ""
        assert name_en.confidence == CONFIDENCE_UNCERTAIN

    def test_source_location_carries_page_numbers(self):
        result = map_document("pdf", CLEAN_PDF)
        assert all(
            m.source_location and m.source_location.startswith("Seite ")
            for m in result.fields
        )

    def test_noise_lines_never_reach_extracted_text(self):
        result = map_document("pdf", CLEAN_PDF)
        joined = "\n".join(m.extracted_text for m in result.fields)
        assert "Characters:" not in joined
        assert "Open Editor" not in joined
        assert "Innosuisse Innolink" not in joined


class TestDegradedFixture:
    """Zeilenverschmelzung ⇒ uncertain statt falschem Mapping (Gate-Messlatte)."""

    def test_no_field_is_confidently_mapped(self):
        result = map_document("pdf", DEGRADED_PDF)
        assert not result.needs_manual_input
        assert all(m.confidence == CONFIDENCE_UNCERTAIN for m in result.fields)

    def test_short_fields_are_not_falsely_filled(self):
        mapped = _by_field(map_document("pdf", DEGRADED_PDF))
        for field_id in (
            "INTRO.APP.NAME",
            "INTRO.APP.NAME_EN",
            "INTRO.APP.ABSTRACT",
            "INTRO.APP.EXECUTIVE_SUMMARY",
        ):
            assert field_id not in mapped or mapped[field_id].confidence == CONFIDENCE_UNCERTAIN


class TestStructuredLegacyFixture:
    def test_empty_management_summary_never_inherits_following_sections(self):
        mapped = _by_field(map_document("pdf", STRUCTURED_LEGACY_PDF))
        summary = mapped["INTRO.APP.EXECUTIVE_SUMMARY"]
        assert summary.extracted_text == ""
        assert summary.mapping_status == "empty"
        assert "Management Summary" in summary.sections[0].original_excerpt
        assert "Context" not in summary.sections[0].original_excerpt

    def test_abstract_is_exactly_bounded_and_help_is_removed(self):
        mapped = _by_field(map_document("pdf", STRUCTURED_LEGACY_PDF))
        abstract = mapped["INTRO.APP.ABSTRACT"]
        assert abstract.extracted_text == "A synthetic abstract with a strict boundary."
        assert "Please note" not in abstract.extracted_text
        assert "Management Summary" not in abstract.extracted_text

    def test_unlabelled_header_title_is_conservative(self):
        mapped = _by_field(map_document("pdf", STRUCTURED_LEGACY_PDF))
        title = mapped["INTRO.APP.NAME"]
        assert title.extracted_text == "AURORA"
        assert title.confidence == CONFIDENCE_UNCERTAIN
        assert title.mapping_status == "uncertain"
        assert title.mapping_version == MAPPING_VERSION
        assert "Dokumentkopf" in (title.sections[0].review_note or "")

    def test_composite_sections_are_separate_and_question_free(self):
        mapped = _by_field(map_document("pdf", STRUCTURED_LEGACY_PDF))
        vc = mapped["VC.BUSINESS_TARGETS_MODEL.EDITOR"]
        sol = mapped["SOL.INNOVATION_SOLUTION.EDITOR"]
        assert [s.target_sections for s in vc.sections] == [
            ("3.1",), ("3.2",), ("3.3",)
        ]
        assert [s.target_sections for s in sol.sections if not s.migration_version][:4] == [
            ("4.1",), ("4.2",), ("4.3",), ("4.4",)
        ]
        joined = vc.extracted_text + "\n" + sol.extracted_text
        for portal_text in (
            "Describe the business targets",
            "Describe potential customers",
            "Describe the state of the art",
            "Describe the novelty",
        ):
            assert portal_text not in joined

    def test_legacy_ip_and_partner_are_migrated_without_legal_inference(self):
        sol = _by_field(map_document("pdf", STRUCTURED_LEGACY_PDF))[
            "SOL.INNOVATION_SOLUTION.EDITOR"
        ]
        by_target = {"/".join(s.target_sections): s for s in sol.sections}
        assert by_target["4.5.1"].migration_version == LEGACY_SCHEMA_MIGRATION_VERSION
        assert "potentially related documents" in by_target["4.5.1"].candidate_text
        shared = by_target["4.5.2/4.5.3"]
        assert shared.status == "uncertain"
        assert shared.requires_manual_assignment is True
        assert shared.candidate_text == "Yes"
        assert "4.5.2\nYes" not in sol.extracted_text
        assert by_target["4.5.4"].candidate_text == "No"
        assert "complementary synthetic capabilities" in by_target["4.6"].candidate_text
        assert "freedom-to-operate" not in sol.extracted_text.lower()

    def test_portal_questions_remain_only_in_original_excerpts(self):
        result = map_document("pdf", STRUCTURED_LEGACY_PDF)
        exported = "\n".join(field.extracted_text for field in result.fields)
        originals = "\n".join(
            section.original_excerpt
            for field in result.fields
            for section in field.sections
        )
        assert "Was a patent search performed" not in exported
        assert "Was a patent search performed" in originals
        assert "Please note" not in exported


class TestFailClosed:
    def test_needs_manual_input_yields_no_candidates(self):
        # Verschlüsselte/gescannte PDFs kommen aus parse() genau so zurück.
        result = map_parse_result(
            ParseResult(blocks=[], warnings=["encrypted_pdf"], needs_manual_input=True)
        )
        assert result.needs_manual_input
        assert result.fields == []
        assert "encrypted_pdf" in result.warnings

    def test_corrupted_pdf_raises_instead_of_empty_result(self):
        with pytest.raises(ParserError):
            map_document("pdf", b"not a pdf at all")

    def test_txt_source_is_supported_without_page_numbers(self):
        text = (
            "Abstract\n"
            "Ein synthetischer Kurzabstract ohne echte Antragsdaten.\n"
        ).encode("utf-8")
        mapped = _by_field(map_document("txt", text))
        abstract = mapped["INTRO.APP.ABSTRACT"]
        assert abstract.extracted_text.startswith("Ein synthetischer Kurzabstract")
        assert abstract.source_location is None
