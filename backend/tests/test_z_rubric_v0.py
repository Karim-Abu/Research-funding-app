"""R6 — Rubric v0: sieben deterministische Reviewer-Heuristiken.

Regeln: qualitative Heuristiken sind IMMER reviewer_risk (nie Blocker, nie
Förderentscheid); idempotent über mehrere Läufe; per Flag abschaltbar.

NOTE: Dateiname sortiert bewusst NACH test_demo_seed.py.
"""
from __future__ import annotations

from sqlalchemy import select

from app.db.models import ReviewFinding
from app.db.session import SessionLocal
from app.review.fingerprint import classify_severity_class, finding_code_family
from app.review.rubric import (
    RUBRIC_CODES,
    check_kpi_chain,
    check_methodology_how,
    check_risk_scope,
    check_sota,
    find_cross_section_conflicts,
    find_partner_without_role,
    find_unsourced_market_claim,
)
from tests.review_helpers import clean_field, get_review, run_recheck, setup_completed_run

VC = "VC.BUSINESS_TARGETS_MODEL.EDITOR"


class TestHeuristics:
    def test_kpi_chain_missing_parts(self) -> None:
        text = "Wir wollen den Ausschuss um 30 % reduzieren."
        missing = check_kpi_chain(text)
        assert missing is not None
        assert "Baseline" in missing
        assert "Messmethode" in missing

    def test_kpi_chain_complete_is_silent(self) -> None:
        text = (
            "Ausgehend von einer Baseline von 12 % wollen wir den Ausschuss um "
            "30 % reduzieren; die Messung erfolgt monatlich über die "
            "Produktionsdatenbank (Datenquelle MES), validiert im Pilotbetrieb."
        )
        assert check_kpi_chain(text) is None

    def test_sota_requires_comparison(self) -> None:
        assert check_sota("Unsere Lösung ist hochinnovativ und einzigartig.")
        assert not check_sota(
            "Unsere Lösung ist innovativ, weil sie sich gegenüber dem Stand der "
            "Technik durch eine tiefere Prozesstemperatur abgrenzt."
        )

    def test_methodology_how(self) -> None:
        what_only = ("Das Projekt erreicht grosse Wirkung und Nutzen. " * 8)
        assert check_methodology_how(what_only)
        with_how = what_only + " Das Vorgehen umfasst drei Schritte mit Prototyp."
        assert not check_methodology_how(with_how)

    def test_market_claim_unsourced(self) -> None:
        text = "Der Markt wächst auf 500 Mio CHF. Unser Team ist erfahren."
        snippet = find_unsourced_market_claim(text, has_evidence_link=False)
        assert snippet is not None and "500" in snippet
        # Beleg am Feld oder Quellensignal im Satz → kein Hinweis.
        assert find_unsourced_market_claim(text, has_evidence_link=True) is None
        sourced = "Laut BFS-Studie wächst der Markt auf 500 Mio CHF."
        assert find_unsourced_market_claim(sourced, has_evidence_link=False) is None

    def test_partner_fit(self) -> None:
        names = ["Industrie AG"]
        unjustified = "Die Industrie AG ist Teil des Projekts."
        assert find_partner_without_role(unjustified, names) == "Industrie AG"
        justified = (
            "Die Industrie AG übernimmt die Rolle der Pilotfertigung und bringt "
            "Kompetenz in der Prozesstechnik ein."
        )
        assert find_partner_without_role(justified, names) is None

    def test_risk_scope(self) -> None:
        assert check_risk_scope("Risiken: Die Sensorik könnte ausfallen.")
        assert not check_risk_scope(
            "Risiken: Sensorik-Ausfall sowie Marktrisiko bei verzögerter Nachfrage."
        )

    def test_cross_section_numbers(self) -> None:
        conflicts = find_cross_section_conflicts(
            {
                "INTRO.APP.EXECUTIVE_SUMMARY": "Wir erwarten Umsatz von 2 Mio CHF.",
                VC: "Der Umsatz beträgt 5 Mio CHF im Jahr drei.",
            }
        )
        assert ("umsatz", "INTRO.APP.EXECUTIVE_SUMMARY", VC) in conflicts
        # Konsistente Zahlen → kein Konflikt.
        assert not find_cross_section_conflicts(
            {
                "INTRO.APP.EXECUTIVE_SUMMARY": "Wir erwarten Umsatz von 2 Mio CHF.",
                VC: "Der Umsatz beträgt 2 Mio CHF im Jahr drei.",
            }
        )


class TestClassification:
    def test_rubric_is_always_reviewer_risk_never_blocker(self) -> None:
        for code in RUBRIC_CODES:
            finding_code = f"rubric:{code}:{VC}"
            assert finding_code_family(finding_code) == f"rubric:{code}"
            assert classify_severity_class(finding_code) == "reviewer_risk"


def _open_rubric_findings(run_id: str) -> list[ReviewFinding]:
    db = SessionLocal()
    try:
        return list(
            db.scalars(
                select(ReviewFinding).where(
                    ReviewFinding.run_id == run_id,
                    ReviewFinding.finding_code.like("rubric:%"),
                    ReviewFinding.status == "open",
                )
            )
        )
    finally:
        db.close()


def test_rubric_findings_over_api_idempotent_and_never_blocking(client):
    csrf, _, run_id = setup_completed_run(client, title="Rubric v0 Flow")
    # Inhaltlicher Text mit SOTA-Schwäche + unbelegter Marktzahl (kein Template).
    clean_field(
        client, csrf, run_id, VC,
        "Unsere Lösung ist hochinnovativ und einzigartig. "
        "Der Markt wächst auf 500 Mio CHF pro Jahr.",
    )
    res = run_recheck(client, csrf, run_id)
    assert res.status_code in (200, 202), res.text

    first = _open_rubric_findings(run_id)
    assert first, "Rubric-Findings erwartet"
    assert all(f.severity == "warning" for f in first)
    assert all(f.severity_class == "reviewer_risk" for f in first)
    assert all(f.advisory for f in first)
    codes = {finding_code_family(f.finding_code) for f in first}
    assert "rubric:market_claim_unsourced" in codes

    # Rubric-Hinweise blocken nie: kein Blocker-Zuwachs durch die Rubric.
    review = get_review(client, run_id)
    rubric_ids = {f.finding_id for f in first}
    blocking = [
        f for f in review["findings"]
        if f["finding_id"] in rubric_ids and f["severity"] == "blocker"
    ]
    assert blocking == []

    # Idempotenz: zweiter Recheck ändert weder Anzahl noch finding_codes.
    res = run_recheck(client, csrf, run_id)
    assert res.status_code in (200, 202), res.text
    second = _open_rubric_findings(run_id)
    assert {f.finding_code for f in second} == {f.finding_code for f in first}
    assert len(second) == len(first)

    # Fix Queue gruppiert mit menschenlesbarem Titel (kein raw code).
    queue = client.get(f"/api/v1/runs/{run_id}/review/fix-queue").json()
    titles = [g["title"] for g in queue["grouped_findings"]]
    assert "Marktzahl ohne Quelle" in titles
    rubric_groups = [
        g for g in queue["grouped_findings"]
        if g["severity_class"] == "reviewer_risk"
    ]
    assert rubric_groups and all(g["severity"] != "blocker" for g in rubric_groups)
