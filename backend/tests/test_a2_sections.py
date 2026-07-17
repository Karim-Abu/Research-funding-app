"""Section-wise A2 context, validation and deterministic merge guards."""
from __future__ import annotations

import pytest

from app.agents import a2_fields, field_drafting
from app.agents import field_drafting_context as context
from app.drafts.sections import SectionStructureError, merge_section
from app.db.session import SessionLocal
from tests.a2_helpers import (
    FIELD_ID,
    GOOD_TEXT,
    VC_FIELD_ID,
    VC_GOOD_TEXT,
    build_run_with_draft,
    fake_resolver,
    section_bundle,
    success_fake,
)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.mark.parametrize(
    ("field_id", "profile_id", "text", "markers"),
    [
        (
            VC_FIELD_ID,
            "A2.value_creation_market_logic",
            VC_GOOD_TEXT,
            ("3.1", "3.2", "3.3"),
        ),
        (
            FIELD_ID,
            "A2.solution_innovation",
            GOOD_TEXT,
            ("4.1", "4.2", "4.3", "4.4", "4.5.1", "4.5.2", "4.5.3", "4.5.4", "4.6"),
        ),
    ],
)
def test_all_twelve_registry_sections_are_individually_addressable(
    db, field_id, profile_id, text, markers
):
    run, _draft, _base = build_run_with_draft(
        db, field_id=field_id, draft_text=text,
        character_limit=15000 if field_id == VC_FIELD_ID else 25000,
    )
    for marker in markers:
        assembled = context.assemble_a2_context(
            db, run, field_id=field_id, profile_id=profile_id,
            target_section=marker, section_markers=markers,
        )
        assert assembled.current_draft_text.lstrip().startswith(marker)
        assert assembled.target_section == marker


def test_complete_target_section_is_preserved_when_adjacent_content_is_long(db):
    markers = ("4.1", "4.2", "4.3", "4.4", "4.5.1", "4.5.2", "4.5.3", "4.5.4", "4.6")
    target_tail = "TARGET_SECTION_END_SENTINEL"
    text = GOOD_TEXT
    text = merge_section(text, markers, "4.1", "4.1 " + ("Nachbartext " * 3000))
    text = merge_section(
        text, markers, "4.2",
        "4.2 Die SEDATE-Sensorplattform nutzt photonische Messketten. "
        + ("Projektbezug " * 1300)
        + target_tail,
    )
    run, _draft, _base = build_run_with_draft(db, draft_text=text)
    assembled = context.assemble_a2_context(
        db, run, field_id=FIELD_ID, profile_id="A2.solution_innovation",
        target_section="4.2", section_markers=markers,
    )
    assert target_tail in assembled.current_draft_text
    assert target_tail in assembled.context_text
    assert len(assembled.context_text) <= assembled.meta["char_budget"]
    assert next(
        part for part in assembled.meta["components"]
        if part["kind"] == "imported_applicant_text"
    )["truncated"] is False
    assert any(part["truncated"] for part in assembled.meta["components"][1:])


@pytest.mark.parametrize(
    ("suggested_text", "reason"),
    [
        ("4.2 Die Lösung erreicht neu 777 Einheiten.", "invented_numeric_token"),
        ("4.2 Ein neuer Treffer ist EP999999.", "invented_patent_identifier"),
        ("4.2 Example Ventures AG übernimmt die Validierung.", "invented_partner_name"),
    ],
)
def test_section_output_rejects_new_numbers_patents_and_partners(
    db, suggested_text, reason
):
    run, draft, base = build_run_with_draft(db)
    outcome = field_drafting.run_a2_field_drafting(
        db, run, field_id=FIELD_ID, draft_id=draft.draft_id,
        base_version_id=base, operation_id=f"op-{reason}", target_section="4.2",
        provider_resolver=fake_resolver(
            success_fake(section_bundle(suggested_text=suggested_text))
        ),
    )
    assert outcome.status == "failed"
    assert outcome.reason == reason


_FIXTURE_WITH_FACTS = GOOD_TEXT.replace(
    "4.2 Neuheit: klare Abgrenzung.",
    "4.2 Neuheit: klare Abgrenzung gegenüber 10'000 bestehenden Messpunkten "
    "bei 45.5 % Abdeckung; Budget CHF 100'000; Partner ist die Muster "
    "Technologies AG.",
)


@pytest.mark.parametrize("claim", [
    # identische Schreibweise
    "4.2 Neuheit: 10'000 Messpunkte bei 45.5 % Abdeckung.",
    # typografisch andere Schreibweise derselben Fixture-Angaben
    "4.2 Neuheit: 10 000 Messpunkte bei 45,5 % Abdeckung.",
    "4.2 Neuheit: 10000 Messpunkte bei 45,5 Prozent Abdeckung.",
    # bekannte Partnernamensvariante
    "4.2 Neuheit: die Muster Technologies AG liefert die Abgrenzung.",
])
def test_known_fixture_facts_are_not_flagged_as_invented(db, claim):
    """Regression der Kalibrierung 2026-07-16: bekannte Angaben aus dem
    sichtbaren Request wurden als Erfindung markiert, weil die Erlaubt-Basis
    der gekürzte Kontextstring war."""
    run, draft, base = build_run_with_draft(db, draft_text=_FIXTURE_WITH_FACTS)
    outcome = field_drafting.run_a2_field_drafting(
        db, run, field_id=FIELD_ID, draft_id=draft.draft_id,
        base_version_id=base, operation_id=f"op-known-{hash(claim)}",
        target_section="4.2",
        provider_resolver=fake_resolver(
            success_fake(section_bundle(suggested_text=claim))
        ),
    )
    assert outcome.status == "succeeded", outcome.reason
    assert outcome.claim_check["routing_metadata_source"] == "caller_bound"
    assert outcome.claim_check["derived_numeric_claims"] == []


def test_derived_number_is_flagged_for_review_not_rejected(db):
    """Aus bekannten Werten berechenbar ⇒ derived-Status + Human Review."""
    run, draft, base = build_run_with_draft(db, draft_text=_FIXTURE_WITH_FACTS)
    outcome = field_drafting.run_a2_field_drafting(
        db, run, field_id=FIELD_ID, draft_id=draft.draft_id,
        base_version_id=base, operation_id="op-derived", target_section="4.2",
        provider_resolver=fake_resolver(success_fake(section_bundle(
            # 10'000 + 100'000 = 110'000 (deterministisch ableitbar)
            suggested_text="4.2 Neuheit: in Summe 110'000 Einheiten.",
        ))),
    )
    assert outcome.status == "succeeded", outcome.reason
    assert outcome.claim_check["derived_numeric_claims"] == ["110'000"]
    assert "contains_derived_numeric_claims" in outcome.view["warnings"]
    contract = outcome.view["section_result"]["role_skill_contract_v2"]
    assert contract["requires_human_review"] is True


def test_new_number_next_to_known_ones_is_still_rejected(db):
    """Keine pauschale Abschwächung: eine wirklich neue Zahl bleibt eine DQ."""
    run, draft, base = build_run_with_draft(db, draft_text=_FIXTURE_WITH_FACTS)
    outcome = field_drafting.run_a2_field_drafting(
        db, run, field_id=FIELD_ID, draft_id=draft.draft_id,
        base_version_id=base, operation_id="op-new-number", target_section="4.2",
        provider_resolver=fake_resolver(success_fake(section_bundle(
            suggested_text="4.2 Neuheit: 10'000 Messpunkte und neu 87'321 Kunden.",
        ))),
    )
    assert outcome.status == "failed"
    assert outcome.reason == "invented_numeric_token"


def test_routing_metadata_is_caller_bound_and_mismatch_is_reported(db):
    """Owner Block 2: der Caller setzt field_id/target_section. Das Modell
    liefert hier beides falsch — das Ergebnis wird nicht am Routing verworfen,
    der Widerspruch aber ausgewiesen (nie still als korrekt überschrieben)."""
    run, draft, base = build_run_with_draft(db)
    payload = section_bundle(
        suggested_text="4.2 Neuheit: klare Abgrenzung für den Testfall.",
        field_id="VC.BUSINESS_TARGETS_MODEL.EDITOR",  # falsches Feld
        target_section="4.1",                          # falscher Abschnitt
    )
    outcome = field_drafting.run_a2_field_drafting(
        db, run, field_id=FIELD_ID, draft_id=draft.draft_id,
        base_version_id=base, operation_id="op-routing", target_section="4.2",
        provider_resolver=fake_resolver(success_fake(payload)),
    )
    assert outcome.status == "succeeded", outcome.reason
    assert outcome.claim_check["routing_metadata_mismatch"] is True
    assert "model_routing_metadata_mismatch" in outcome.view["warnings"]
    section = outcome.view["section_result"]
    assert section["field_id"] == FIELD_ID
    assert section["target_section"] == "4.2"


def test_wrong_section_content_still_fails_structurally(db):
    """Technische Routing-Bindung ≠ fachliche Abschnittstreue: Text für einen
    anderen Abschnitt scheitert weiterhin an der Strukturprüfung."""
    run, draft, base = build_run_with_draft(db)
    outcome = field_drafting.run_a2_field_drafting(
        db, run, field_id=FIELD_ID, draft_id=draft.draft_id,
        base_version_id=base, operation_id="op-wrong-content",
        target_section="4.2",
        provider_resolver=fake_resolver(success_fake(section_bundle(
            suggested_text="4.1 Stand der Technik: Inhalt des Nachbarabschnitts.",
        ))),
    )
    assert outcome.status == "failed"
    assert "section" in outcome.reason or "structure" in outcome.reason


def test_clear_language_change_is_rejected(db):
    english = GOOD_TEXT.replace(
        "4.2 Neuheit: klare Abgrenzung.",
        "4.2 The SEDATE platform is compared with the existing baseline and the project keeps its scope.",
    )
    run, draft, base = build_run_with_draft(db, draft_text=english)
    outcome = field_drafting.run_a2_field_drafting(
        db, run, field_id=FIELD_ID, draft_id=draft.draft_id,
        base_version_id=base, operation_id="op-language", target_section="4.2",
        provider_resolver=fake_resolver(success_fake(section_bundle(
            suggested_text="4.2 Die Lösung wird mit dem bestehenden Stand verglichen und das Projekt bleibt erhalten."
        ))),
    )
    assert outcome.status == "failed"
    assert outcome.reason == "application_language_changed"


def _trigrams(text: str) -> set[str]:
    normalized = " ".join(text.casefold().split())
    return {normalized[index:index + 3] for index in range(max(0, len(normalized) - 2))}


def _trigram_similarity(left: str, right: str) -> float:
    a, b = _trigrams(left), _trigrams(right)
    return len(a & b) / len(a | b) if a or b else 1.0


def test_project_specific_42_is_distinct_from_every_fake_template(db):
    source = GOOD_TEXT.replace(
        "4.2 Neuheit: klare Abgrenzung.",
        "4.2 Die SEDATE-Sensorplattform kombiniert photonische Messketten mit einer modularen Auswertung.",
    )
    suggested = (
        "4.2 Die SEDATE-Sensorplattform grenzt sich durch die gekoppelte "
        "photonische Messkette und modulare Auswertung vom vorhandenen Ansatz ab."
    )
    run, draft, base = build_run_with_draft(db, draft_text=source)
    outcome = field_drafting.run_a2_field_drafting(
        db, run, field_id=FIELD_ID, draft_id=draft.draft_id,
        base_version_id=base, operation_id="op-project-specific", target_section="4.2",
        provider_resolver=fake_resolver(
            success_fake(section_bundle(suggested_text=suggested))
        ),
    )
    assert outcome.status == "succeeded"
    assert "SEDATE" in outcome.view["suggested_text"]
    assert "photonische" in outcome.view["suggested_text"]
    assert all(
        _trigram_similarity(suggested, template) < 0.70
        for template in a2_fields._FAKE_TEXTS.values()
    )


def test_43_surfaces_complete_kpi_chain_as_open_inputs_without_values(db):
    run, draft, base = build_run_with_draft(db)
    missing = [
        {"label": "Baseline", "reason": "nicht angegeben"},
        {"label": "Ziel", "reason": "nicht angegeben"},
        {"label": "Messmethode/Datenquelle", "reason": "nicht angegeben"},
        {"label": "Validierungsmoment", "reason": "nicht angegeben"},
    ]
    outcome = field_drafting.run_a2_field_drafting(
        db, run, field_id=FIELD_ID, draft_id=draft.draft_id,
        base_version_id=base, operation_id="op-kpi-gaps", target_section="4.3",
        provider_resolver=fake_resolver(success_fake(section_bundle(
            target_section="4.3", suggested_text=(
                "4.3 Die KPI-Kette bleibt bis zur fachlichen Ergänzung offen; "
                "Baseline, Ziel, Messmethode oder Datenquelle und Validierungsmoment sind zu klären."
            ), missing_inputs=missing,
        ))),
    )
    assert outcome.status == "succeeded"
    assert [item["label"] for item in outcome.view["section_result"]["missing_inputs"]] == [
        item["label"] for item in missing
    ]
    contract = outcome.view["section_result"]["role_skill_contract_v2"]
    assert contract["section_id"] == "4.3"
    assert contract["requires_human_review"] is True
    assert [item["label"] for item in contract["missing_inputs"]] == [
        item["label"] for item in missing
    ]


def test_merge_fails_closed_for_missing_or_duplicate_markers():
    markers = ("3.1", "3.2", "3.3")
    with pytest.raises(SectionStructureError, match="section_marker_missing"):
        merge_section("3.1 A\n3.3 C", markers, "3.1", "3.1 Neu")
    with pytest.raises(SectionStructureError, match="section_marker_ambiguous"):
        merge_section("3.1 A\n3.2 B\n3.2 B2\n3.3 C", markers, "3.2", "3.2 Neu")
