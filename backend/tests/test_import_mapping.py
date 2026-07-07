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
    MappingResult,
    map_document,
    map_parse_result,
)
from app.ingestion.parsers import ParseResult, ParserError

FIXTURES = Path(__file__).parent / "import_fixtures"
CLEAN_PDF = (FIXTURES / "innolink_sample.pdf").read_bytes()
DEGRADED_PDF = (FIXTURES / "innolink_sample_degraded.pdf").read_bytes()


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

    def test_editor_fields_keep_numbered_questions_and_are_found(self):
        mapped = _by_field(map_document("pdf", CLEAN_PDF))
        vc = mapped["VC.BUSINESS_TARGETS_MODEL.EDITOR"]
        sol = mapped["SOL.INNOVATION_SOLUTION.EDITOR"]
        assert vc.confidence == CONFIDENCE_FOUND
        assert sol.confidence == CONFIDENCE_FOUND
        assert "3.1 Which business targets" in vc.extracted_text
        assert "4.1 What is the innovation" in sol.extracted_text

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
