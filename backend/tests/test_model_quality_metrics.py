"""Ebene C — deterministische Qualitätsmetriken (CI-fähig, kein Provider).

Pins der puren Metrikfunktionen aus ``app.evaluation.model_quality`` und der
Report-Wahrheit («not_run» erscheint nie als bestanden/durchgeführt).
"""
from __future__ import annotations

from app.evaluation.model_quality import (
    FAIL,
    NOT_RUN,
    PASS,
    char_limit_respected,
    extract_numbers,
    kpi_gaps_marked_open,
    mandatory_subsections_present,
    no_invented_numbers,
    no_invented_patents,
    no_review_notes_as_prose,
    render_quality_report,
    summarize_status,
    terms_preserved,
)

INPUT = (
    "F1 QUALIMON — KI-gestützte Qualitätsüberwachung. Prognosefehler sinken "
    "um bis zu 30 Prozent; Budgetrahmen CHF 250'000."
)


class TestTermsAndSections:
    def test_terms_preserved_pass_and_fail(self):
        assert terms_preserved("QUALIMON verbessert X.", ("QUALIMON",)).status == PASS
        result = terms_preserved("Ein generischer Text.", ("QUALIMON",))
        assert result.status == FAIL
        assert "fehlend: 1" in result.detail

    def test_without_required_terms_is_not_run(self):
        assert terms_preserved("Text", ()).status == NOT_RUN

    def test_mandatory_subsections(self):
        text = "3.1 Ziele\nInhalt\n3.2 Modell\nInhalt"
        assert mandatory_subsections_present(text, ("3.1", "3.2")).status == PASS
        result = mandatory_subsections_present(text, ("3.1", "3.2", "3.3"))
        assert result.status == FAIL
        assert "3.3" in result.detail


class TestLimitsAndFacts:
    def test_char_limit(self):
        assert char_limit_respected("abc", 5).status == PASS
        assert char_limit_respected("abcdef", 5).status == FAIL
        assert char_limit_respected("abc", None).status == NOT_RUN

    def test_extract_numbers_ignores_section_markers_and_small_ints(self):
        numbers = extract_numbers("3.1 hat 2 Ziele; 30 Prozent; CHF 250'000; 4.5.1")
        assert numbers == {"30", "250000"}

    def test_no_invented_numbers(self):
        ok = no_invented_numbers("Reduktion um 30 Prozent (CHF 250'000).", INPUT)
        assert ok.status == PASS
        invented = no_invented_numbers("Der Markt wächst auf CHF 87 Mio. (87'000'000).", INPUT)
        assert invented.status == FAIL

    def test_no_invented_patents(self):
        assert no_invented_patents("Zwei Patente sind angemeldet.", INPUT).status == FAIL
        assert no_invented_patents("Keine Schutzrechte erwähnt.", INPUT).status == PASS
        assert (
            no_invented_patents(
                "Die Patentrecherche ist dokumentiert.",
                INPUT + " Patentrecherche vorhanden.",
            ).status
            == PASS
        )


class TestHonestyOfProse:
    def test_review_notes_and_portal_questions_fail(self):
        assert no_review_notes_as_prose("TODO: Zahlen prüfen").status == FAIL
        assert (
            no_review_notes_as_prose(
                "3.1 What is your business model?\n"
            ).status
            == FAIL
        )
        assert no_review_notes_as_prose("Ein sauberer Fliesstext.").status == PASS

    def test_kpi_gaps_must_be_marked_open(self):
        assert kpi_gaps_marked_open("Alles belegt.", 0).status == PASS
        assert (
            kpi_gaps_marked_open("Baseline: [[Angabe ergänzen: Messwert]]", 2).status
            == PASS
        )
        assert kpi_gaps_marked_open("Wir erreichen Weltklasse.", 2).status == FAIL


class TestReportTruth:
    def test_not_run_is_never_reported_as_passed(self):
        report = render_quality_report(
            {"openai": None, "anthropic": None},
            generated_at="2026-07-15T00:00:00+00:00",
            not_run_reasons={"openai": "kein Ergebnis", "anthropic": "kein Ergebnis"},
        )
        assert report.count("Status: not_run") == 2
        assert "durchgeführt" not in report.split("`not_run`", 1)[1].split("##")[1]
        assert summarize_status({"openai": None, "anthropic": None}) == "not_run"

    def test_mixed_results_report_each_provider_separately(self):
        rows = [{
            "field_id": "INTRO.APP.ABSTRACT", "status": "generated",
            "model": "gpt-test",
            "metrics": [
                {"name": "char_limit", "status": PASS, "detail": "10/300 Zeichen"}
            ],
        }]
        report = render_quality_report(
            {"openai": rows, "anthropic": None},
            generated_at="2026-07-15T00:00:00+00:00",
            not_run_reasons={"anthropic": "Provider nicht verfügbar"},
        )
        assert "## Provider: openai — Status: durchgeführt" in report
        assert "## Provider: anthropic — Status: not_run" in report
        # Human-Rubric bleibt manuell (TODO), nie automatisch bewertet.
        assert "_TODO_" in report
        assert summarize_status({"openai": rows, "anthropic": None}) == "durchgeführt"
