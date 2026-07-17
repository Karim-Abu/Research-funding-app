"""Pure Scorer/Gates/Aggregation der Rollen-Modell-Evaluation (kein DB, kein Provider)."""
from __future__ import annotations

import pytest

from app.agents import allowed_facts
from app.agents.allowed_facts import build_manifest
from app.evaluation import role_model_scoring as scoring
from app.evaluation.model_quality import FAIL, NOT_RUN, PASS


# --- Gold-Dateien -----------------------------------------------------------------


@pytest.mark.parametrize("case_id,holdout", [("F1", False), ("F2", False), ("H1", True)])
def test_case_gold_and_fragments_load_and_validate(case_id, holdout):
    gold = scoring.load_case_gold(case_id)
    assert gold.case_id == case_id
    assert gold.holdout is holdout
    assert gold.required_terms and gold.entities and gold.gold_facts
    assert gold.gold_findings, "A3-Gold-Findings sind Pflicht"
    fragments = scoring.load_case_fragments(case_id)
    fragment_ids = {f["fragment_id"] for f in fragments}
    for fact in gold.gold_facts:
        assert set(fact["fragment_ids"]) <= fragment_ids, fact["gold_id"]


def test_case_gold_missing_file_raises(tmp_path):
    with pytest.raises(scoring.GoldError):
        scoring.load_case_gold("F1", cases_dir=tmp_path)


def test_case_gold_schema_violation_raises(tmp_path):
    (tmp_path / "X1_gold.json").write_text(
        '{"case_id": "X1", "title_de": "t", "title_en": "t", "required_terms": [],'
        ' "entities": [], "portal_boilerplate": [], "gold_facts": [{"gold_id": "a"}],'
        ' "gold_missing": []}',
        encoding="utf-8",
    )
    with pytest.raises(scoring.GoldError):
        scoring.load_case_gold("X1", cases_dir=tmp_path)


# --- A1 ---------------------------------------------------------------------------


def _gold(**overrides) -> scoring.CaseGold:
    base = dict(
        case_id="T", holdout=False, title_de="T-Titel", title_en="T-Title",
        required_terms=("TESTPROJ",),
        entities=("TESTPROJ", "Beispiel Institut"),
        portal_boilerplate=("Characters:", "Open Editor"),
        gold_facts=(
            {"gold_id": "G1", "fact_type": "budget", "target_ref": None,
             "normalized_value": "200000", "keywords": ["Projektkosten"],
             "fragment_ids": ["frag-1"]},
            {"gold_id": "G2", "fact_type": "title", "target_ref": "INTRO.APP.NAME",
             "normalized_value": "TESTPROJ Titel", "keywords": ["TESTPROJ", "Titel"],
             "fragment_ids": ["frag-2"]},
        ),
        gold_missing=(
            {"gold_id": "M1", "target_ref": "INTRO.APP.EXECUTIVE_SUMMARY",
             "keywords": ["Executive", "leer"]},
        ),
        gold_findings=(),
    )
    base.update(overrides)
    return scoring.CaseGold(**base)


def test_a1_precision_recall_and_field_accuracy():
    gold = _gold()
    result = {
        "facts": [
            {"statement": "Direkte Projektkosten: CHF 200'000",
             "normalized_value": "200'000", "target_ref": None,
             "source_fragment_ids": ["frag-1"]},
            {"statement": "Titel: TESTPROJ Titel",
             "normalized_value": "TESTPROJ Titel", "target_ref": "INTRO.APP.NAME",
             "source_fragment_ids": ["frag-2"]},
            {"statement": "Erfundener Fakt ohne Bezug",
             "normalized_value": "999", "target_ref": None,
             "source_fragment_ids": ["frag-1"]},
        ],
        "missing_information": [
            {"target_ref": "INTRO.APP.EXECUTIVE_SUMMARY", "description": "leer"},
        ],
    }
    scores = scoring.score_a1(result, gold)
    assert scores["fact_recall"] == 1.0
    assert scores["fact_precision"] == pytest.approx(2 / 3, abs=1e-3)
    assert scores["field_accuracy"] == 1.0
    assert scores["boundary_accuracy"] == 1.0
    assert scores["missing_recall"] == 1.0


def test_a1_boundary_fails_on_foreign_fragment_or_wrong_value():
    gold = _gold()
    result = {
        "facts": [
            # richtiger Wert, falsche Provenienz
            {"statement": "Projektkosten 200'000", "normalized_value": "200000",
             "target_ref": None, "source_fragment_ids": ["frag-9"]},
            # richtige Provenienz, Wert weicht ab
            {"statement": "TESTPROJ Titel", "normalized_value": "Anderer Titel",
             "target_ref": "INTRO.APP.NAME", "source_fragment_ids": ["frag-2"]},
        ],
        "missing_information": [],
    }
    scores = scoring.score_a1(result, gold)
    assert scores["fact_recall"] == 1.0
    assert scores["boundary_accuracy"] == 0.0


def test_a1_entity_preservation_flags_paraphrase():
    gold = _gold()
    result = {
        "facts": [
            {"statement": "Das beispiel institut liefert Modelle.",  # paraphrasiert
             "normalized_value": None, "target_ref": None,
             "source_fragment_ids": ["frag-1"]},
        ],
        "missing_information": [],
    }
    scores = scoring.score_a1(result, gold)
    assert scores["entity_preservation"] == 0.0


def test_a1_portal_text_adoption_detected():
    gold = _gold()
    result = {
        "facts": [
            {"statement": "Characters: 254/300", "normalized_value": None,
             "target_ref": None, "source_fragment_ids": ["frag-1"]},
            {"statement": "Projektkosten 200000", "normalized_value": "200000",
             "target_ref": None, "source_fragment_ids": ["frag-1"]},
        ],
        "missing_information": [],
    }
    scores = scoring.score_a1(result, gold)
    assert scores["portal_text_adoption_rate"] == 0.5


# --- A2-Gates ------------------------------------------------------------------------

_DE_TEXT = (
    "Das Projekt entwickelt eine adaptive Steuerung für städtische Anlagen und "
    "wird von den Partnern gemeinsam umgesetzt. Die Ziele sind messbar und die "
    "Ergebnisse werden im Pilotbetrieb validiert. Die Daten werden nicht ohne "
    "Prüfung übernommen und die offenen Punkte sind gekennzeichnet."
)
_EN_TEXT = (
    "The project develops an adaptive control system for urban facilities and "
    "the partners will implement it together. The goals are measurable and the "
    "results are validated in the pilot. The data is not adopted without a "
    "review and the open points are marked in this section."
)
_MIXED_TEXT = (
    "Das Projekt entwickelt eine adaptive Steuerung für die Anlagen der Stadt. "
    "The system will be deployed across all sites and the team is convinced "
    "that this approach is the best that has been proposed so far in the field."
)


def test_language_consistency_heuristic():
    assert scoring.language_consistent(_DE_TEXT, "de").status == PASS
    assert scoring.language_consistent(_MIXED_TEXT, "de").status == FAIL
    assert scoring.language_consistent("Kurz.", "de").status == NOT_RUN


def test_invented_partner_trl_legal_and_sources():
    manifest = build_manifest([
        ("current_field_text", "TESTPROJ mit Voltaris AG und TRL 4 laut Eingabe."),
    ])

    def _report(text):
        return allowed_facts.analyze_claims(text, manifest)

    assert scoring.no_invented_partners(_report("Die Voltaris AG liefert.")).status == PASS
    assert scoring.no_invented_partners(_report("Die Phantom GmbH liefert.")).status == FAIL
    assert scoring.no_invented_trl(_report("Start bei TRL 4.")).status == PASS
    assert scoring.no_invented_trl(_report("Wir erreichen TRL 8.")).status == FAIL
    assert scoring.no_legal_clearance_claims("Das Projekt ist spannend.").status == PASS
    assert scoring.no_legal_clearance_claims("Das Projekt ist förderfähig.").status == FAIL
    allowed = ("https://research.example.org/r/1",)
    assert scoring.sources_exist("Ohne Quellen.", allowed).status == PASS
    assert scoring.sources_exist(
        "Siehe https://research.example.org/r/1.", allowed
    ).status == PASS
    assert scoring.sources_exist(
        "Siehe https://erfunden.example.net/studie.", allowed
    ).status == FAIL


def test_foreign_portal_sections_marker():
    assert scoring.foreign_portal_sections("3.1 Ziele\nText", ("4.1",)).status == PASS
    assert scoring.foreign_portal_sections("4.1 SOTA\nText", ("4.1",)).status == FAIL


def _manifest(text: str = ""):
    return build_manifest([("current_field_text", text)])


def test_a2_gate_results_has_ten_gates_and_pass_logic():
    gates = scoring.a2_gate_results(
        _DE_TEXT + " TESTPROJ",
        schema_valid=True,
        required_terms=("TESTPROJ",),
        expected_markers=(),
        char_limit=5000,
        manifest=_manifest(_DE_TEXT + " TESTPROJ"),
        expected_language="de",
        missing_inputs_count=0,
        human_review_required=True,
        allowed_sources=(),
    )
    assert [row["gate"] for row in gates] == list(range(1, 11))
    assert scoring.gates_passed(gates)
    gates_fail = scoring.a2_gate_results(
        _MIXED_TEXT,  # ohne Gap-Marker («offen» etc.) — Gate 8 muss rot werden
        schema_valid=False,
        required_terms=("TESTPROJ",),
        expected_markers=("3.1",),
        char_limit=10,
        manifest=_manifest(""),
        expected_language="de",
        missing_inputs_count=2,
        human_review_required=False,
        allowed_sources=(),
    )
    assert not scoring.gates_passed(gates_fail)
    by_gate = {row["gate"]: row["status"] for row in gates_fail}
    assert by_gate[1] == FAIL      # Schema
    assert by_gate[2] == FAIL      # Pflichtunterabschnitte
    assert by_gate[3] == FAIL      # Zeichenlimit
    assert by_gate[5] == FAIL      # Pflichtbegriffe
    assert by_gate[8] == FAIL      # KPI-Lücken nicht gekennzeichnet
    assert by_gate[10] == FAIL     # Auto-Freigabe


def test_fatal_gates_every_detector():
    manifest = _manifest("TESTPROJ Eingabe mit Voltaris AG.")
    rows = scoring.fatal_gate_results(
        "Neue Zahl 987654 von der Phantom GmbH, Patent erteilt, förderfähig. "
        "Siehe https://erfunden.example.net/x.\n4.1 Fremdabschnitt",
        manifest=manifest,
        allowed_sources=(),
        evidence_ref_violations=1,
        silent_fake_detected=True,
        foreign_markers=("4.1",),
        confidential_terms=("GEHEIMBEGRIFF",),
        leak_scan_texts=("Log ohne GEHEIMBEGRIFF-Treffer... doch: GEHEIMBEGRIFF",),
    )
    by_name = {row["name"]: row for row in rows}
    for name in (
        "fatal_invented_number", "fatal_invented_source", "fatal_invented_partner",
        "fatal_invented_patent", "fatal_legal_clearance", "fatal_confidential_leak",
        "fatal_nonexistent_evidence_id", "fatal_silent_fake_switch",
        "fatal_foreign_portal_section",
    ):
        assert by_name[name]["status"] == FAIL, name
    assert scoring.fatal_candidate(rows)
    assert by_name["fatal_invented_number"]["requires_human_adjudication"] is True
    assert by_name["fatal_silent_fake_switch"]["requires_human_adjudication"] is False

    clean = scoring.fatal_gate_results(
        "TESTPROJ nutzt die Voltaris AG.", manifest=manifest,
        allowed_sources=(), evidence_ref_violations=0,
        silent_fake_detected=False, foreign_markers=("4.1",),
    )
    assert not scoring.fatal_candidate(clean)


# --- Kanonische Sprachquelle + gemeinsame Erfindungs-Detektoren ---------------


def test_expected_language_never_defaults_silently_to_german():
    gold_en = scoring.load_case_gold("F1")
    assert gold_en.case_language == "en"
    # 1. explizite Fallkonfiguration gewinnt
    assert scoring.resolve_expected_language(gold_en) == ("en", "case_language")
    assert scoring.resolve_expected_language(
        gold_en, draft_language="de"
    ) == ("en", "case_language")
    # 2. Draft-/Portalfeldsprache, 3. Projektsprache, 4. Erkennung
    assert scoring.resolve_expected_language(
        None, draft_language="en"
    ) == ("en", "draft_field_language")
    assert scoring.resolve_expected_language(
        None, project_language="de"
    ) == ("de", "project_application_language")
    assert scoring.resolve_expected_language(
        None, detected_language="en"
    ) == ("en", "language_detection_fallback")
    # Ohne jede Quelle: Fehler statt stillem «de».
    with pytest.raises(scoring.GoldError):
        scoring.resolve_expected_language(None)


@pytest.mark.parametrize(
    ("expected", "text", "status"),
    [
        ("en", _EN_TEXT, PASS),   # englisches Fixture + englischer Output
        ("en", _DE_TEXT, FAIL),   # englisches Fixture + deutscher Output
        ("de", _DE_TEXT, PASS),   # deutsches Fixture + deutscher Output
        ("de", _EN_TEXT, FAIL),
    ],
)
def test_language_gate_follows_the_canonical_case_language(expected, text, status):
    assert scoring.language_consistent(text, expected).status == status


def test_gate_uses_the_production_manifest_not_a_second_corpus():
    """Owner Block 4: bekannte Fixture-Angaben — auch typografisch anders
    geschrieben — sind keine Erfindung; echte Neuangaben bleiben eine DQ."""
    manifest = build_manifest([
        ("current_field_text", "TESTPROJ plant 10'000 Einheiten mit der Voltaris AG."),
    ])

    def _fatal(text):
        rows = scoring.fatal_gate_results(
            text, manifest=manifest, allowed_sources=(),
        )
        return {row["name"]: row["status"] for row in rows}

    # bekannte Zahl, andere Schreibweise → kein DQ
    assert _fatal("TESTPROJ plant 10 000 Einheiten.")["fatal_invented_number"] == PASS
    # bekannte Partnervariante → kein DQ
    assert _fatal("Die voltaris ag liefert.")["fatal_invented_partner"] == PASS
    # deterministisch abgeleitet (10'000 + 10'000) → kein DQ, aber ausgewiesen
    derived = scoring.no_invented_numbers(
        allowed_facts.analyze_claims("Zusammen 20'000 Einheiten.", manifest)
    )
    assert derived.status == PASS and "derived_numeric_claim" in derived.detail
    # tatsächlich neue Zahl / neuer Partner → DQ
    assert _fatal("Neu sind 87'321 Einheiten.")["fatal_invented_number"] == FAIL
    assert _fatal("Die Phantom GmbH liefert.")["fatal_invented_partner"] == FAIL


# --- Drei Statusdimensionen (Owner 2026-07-17, Option A) ---------------------

_OK_USAGE = {"cost_status": "priced", "input_tokens": 10, "output_tokens": 20}


def _dimensions(**overrides):
    base = dict(
        execution="real", silent_fake=False, schema_valid=True,
        routing_metadata_source="caller_bound", usage=_OK_USAGE,
        hard_dq=(), has_readable_output=True,
    )
    return scoring.sample_status_dimensions(**{**base, **overrides})


def test_clean_output_is_valid_eligible_and_evaluable():
    assert _dimensions() == {
        "technical_valid": True,
        "production_eligible": True,
        "human_evaluable": True,
    }


def test_unsupported_reference_is_a_model_finding_not_a_technical_failure():
    """Owner: technisch valide + nicht produktionsgeeignet + blind bewertbar."""
    assert _dimensions(hard_dq=("dq_unsupported_reference",)) == {
        "technical_valid": True,
        "production_eligible": False,
        "human_evaluable": True,
    }


@pytest.mark.parametrize("dq", [
    "dq_unsupported_numeric_claim", "dq_wrong_language", "dq_invented_fact",
    "dq_char_limit", "dq_review_notes_in_prose", "dq_wrong_section",
])
def test_content_dqs_never_break_technical_validity(dq):
    result = _dimensions(hard_dq=(dq,))
    assert result["technical_valid"] is True
    assert result["production_eligible"] is False
    assert result["human_evaluable"] is True


@pytest.mark.parametrize("dq", [
    "dq_schema_error", "dq_tool_contract_error", "dq_truncated_output",
    "dq_empty_output",
])
def test_technical_dqs_break_all_three_dimensions(dq):
    assert _dimensions(hard_dq=(dq,)) == {
        "technical_valid": False,
        "production_eligible": False,
        "human_evaluable": False,
    }


@pytest.mark.parametrize("broken", [
    {"execution": "fake_dryrun"},
    {"silent_fake": True},
    {"schema_valid": False},
    {"routing_metadata_source": "model_provided"},
    {"routing_metadata_source": None},
    {"usage": {"cost_status": "unknown_price", "input_tokens": 1, "output_tokens": 1}},
    {"usage": {"cost_status": "priced", "input_tokens": None, "output_tokens": 1}},
])
def test_technical_validity_requires_every_contract_condition(broken):
    assert _dimensions(**broken)["technical_valid"] is False


def test_empty_output_is_not_human_evaluable():
    assert _dimensions(has_readable_output=False) == {
        "technical_valid": True,
        "production_eligible": True,
        "human_evaluable": False,
    }


# --- Harte A2-Disqualifikationen (Auftrag) ------------------------------------------


def _dq_gate_rows(**failed: bool) -> list[dict]:
    names = {
        "valid_output_schema": failed.get("schema", False),
        "char_limit": failed.get("char", False),
        "language_consistent": failed.get("language", False),
        "no_review_notes_as_prose": failed.get("notes", False),
    }
    return [
        {"gate": i, "name": name, "status": FAIL if fail else PASS, "detail": ""}
        for i, (name, fail) in enumerate(names.items(), start=1)
    ]


def _dq_fatal_rows(*failed_names: str) -> list[dict]:
    all_names = (
        "fatal_invented_number", "fatal_invented_source",
        "fatal_invented_partner", "fatal_invented_patent",
    )
    return [
        {"name": name, "status": FAIL if name in failed_names else PASS,
         "detail": "", "requires_human_adjudication": True}
        for name in all_names
    ]


def test_a2_hard_disqualifications_mapping():
    # Alles sauber → keine DQ.
    assert scoring.a2_hard_disqualifications(_dq_gate_rows(), _dq_fatal_rows()) == []
    # Erfundene Organisation/Patent-ID zählen als dq_invented_fact …
    assert scoring.a2_hard_disqualifications(
        _dq_gate_rows(), _dq_fatal_rows("fatal_invented_partner")
    ) == ["dq_invented_fact"]
    assert scoring.a2_hard_disqualifications(
        _dq_gate_rows(), _dq_fatal_rows("fatal_invented_patent")
    ) == ["dq_invented_fact"]
    # … eine erfundene QUELLE dagegen nicht (bleibt fatal_candidate-Thema).
    assert scoring.a2_hard_disqualifications(
        _dq_gate_rows(), _dq_fatal_rows("fatal_invented_source")
    ) == []
    # Einzelne Gate-DQs mappen auf genau ein Kriterium.
    assert scoring.a2_hard_disqualifications(
        _dq_gate_rows(char=True), _dq_fatal_rows()
    ) == ["dq_char_limit"]
    assert scoring.a2_hard_disqualifications(
        _dq_gate_rows(language=True), _dq_fatal_rows()
    ) == ["dq_wrong_language"]


def test_dq_schema_error_only_for_real_schema_violations():
    """Owner 2026-07-16: dq_schema_error NUR bei echtem JSON-/Schema-Fehler;
    fachliche/kontextabhängige Gates bekommen eigene Codes — ein Gate-1-FAIL
    allein erzeugt KEIN dq_schema_error mehr."""
    # Gate 1 FAIL ohne Reason ⇒ keine Schema-DQ (Fehlklassifikations-Schutz).
    assert scoring.a2_hard_disqualifications(
        _dq_gate_rows(schema=True), _dq_fatal_rows()
    ) == []
    # Echte Schema-/JSON-/Tool-Fehler kommen NUR über den Reason-Code.
    cases = {
        "provider_output_schema_invalid": "dq_schema_error",
        "provider_output_not_json": "dq_tool_contract_error",
        "provider_output_truncated": "dq_truncated_output",
        "invented_numeric_token": "dq_unsupported_numeric_claim",
        "invented_partner_name": "dq_unsupported_partner_claim",
        "section_target_mismatch": "dq_wrong_field_id",
        "no_candidate_for_field": "dq_no_candidate_for_field",
        "mandatory_structure_missing": "dq_missing_structure",
        "unknown_evidence_anchor": "dq_unsupported_reference",
        "empty_suggested_text": "dq_empty_output",
    }
    for reason, expected in cases.items():
        assert scoring.a2_hard_disqualifications(
            _dq_gate_rows(), _dq_fatal_rows(), reject_reason=reason
        ) == [expected], reason
    assert scoring.a2_reject_reason_to_dq(None) is None
    assert scoring.a2_reject_reason_to_dq("all_findings_filtered") == (
        "dq_all_findings_filtered"
    )


# --- A3: kein Förderentscheid (Auftrag) ---------------------------------------------


def test_funding_decision_claims_detector():
    neutral = {
        "description": "Baseline fehlt für den KPI Ausschussquote.",
        "suggested_improvement": "Baseline und Messmethode ergänzen.",
        "recommended_next_action": "Quelle ergänzen.",
    }
    verdict_de = {
        "description": "Das Projekt ist förderfähig und sollte bewilligt werden.",
        "suggested_improvement": None,
        "recommended_next_action": None,
    }
    verdict_en = {
        "description": "Overall the proposal should be funded.",
        "suggested_improvement": None,
        "recommended_next_action": None,
    }
    assert scoring.funding_decision_claims([]) == 0
    assert scoring.funding_decision_claims([neutral]) == 0
    assert scoring.funding_decision_claims([neutral, verdict_de, verdict_en]) == 2
    # Der Zähler ist Teil des A3-Scorings.
    scores = scoring.score_a3([verdict_de], _gold())
    assert scores["funding_decision_claims"] == 1


# --- A3 ---------------------------------------------------------------------------


_A3_GOLD = _gold(gold_findings=(
    {"finding_id": "T-F-1", "field_id": "VC.BUSINESS_TARGETS_MODEL.EDITOR",
     "target_section": "3.1", "severity": "evidence_risk", "a3_scope": True,
     "keywords": ["Einsparung", "Beleg", "Annahme"]},
    {"finding_id": "T-F-2", "field_id": "SOL.INNOVATION_SOLUTION.EDITOR",
     "target_section": "4.5", "severity": "reviewer_risk", "a3_scope": True,
     "keywords": ["IPR", "FTO", "ungeklärt"]},
    {"finding_id": "T-F-3", "field_id": "SOL.INNOVATION_SOLUTION.EDITOR",
     "target_section": "4.1", "severity": "reviewer_risk", "a3_scope": False,
     "keywords": ["ausserhalb"]},
))


def test_a3_matching_uses_section_prefix_and_weights():
    findings = [
        {"field_id": "VC.BUSINESS_TARGETS_MODEL.EDITOR", "target_section": "3.1",
         "description": "Die Einsparungs-Annahme ist ohne Beleg.",
         "suggested_improvement": "Quelle ergänzen."},
        # Präfix-Match: Gold «4.5» trifft Vorhersage «4.5.2»
        {"field_id": "SOL.INNOVATION_SOLUTION.EDITOR", "target_section": "4.5.2",
         "description": "IPR und FTO sind ungeklärt.",
         "suggested_improvement": None},
    ]
    scores = scoring.score_a3(findings, _A3_GOLD)
    # Gewichte: evidence_risk=2, reviewer_risk=1 → 3/3 (nur a3_scope zählt)
    assert scores["finding_recall_weighted"] == 1.0
    assert scores["false_positive_rate"] == 0.0
    assert scores["counts"]["gold_findings_in_scope"] == 2
    assert scores["fixability_rate"] == 0.5


def test_a3_false_positive_and_grouping():
    findings = [
        {"field_id": "VC.BUSINESS_TARGETS_MODEL.EDITOR", "target_section": "3.1",
         "description": "Die Einsparungs-Annahme ist ohne Beleg dokumentiert."},
        {"field_id": "VC.BUSINESS_TARGETS_MODEL.EDITOR", "target_section": "3.1",
         "description": "Die Einsparungs-Annahme ist ohne Beleg dokumentiert!"},
        {"field_id": "VC.BUSINESS_TARGETS_MODEL.EDITOR", "target_section": "3.2",
         "description": "Etwas völlig anderes ohne Goldbezug."},
    ]
    scores = scoring.score_a3(findings, _A3_GOLD)
    assert scores["false_positive_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert scores["counts"]["near_duplicate_pairs"] == 1
    assert scores["grouping_quality"] < 1.0


def test_a3_false_consensus_only_with_flaw_keywords():
    findings = [{
        "field_id": "VC.BUSINESS_TARGETS_MODEL.EDITOR", "target_section": "3.1",
        "description": "Die Einsparungs-Annahme ist ohne Beleg.",
    }]
    no_flaw = scoring.score_a3(findings, _A3_GOLD)
    assert no_flaw["false_consensus"] is None
    missed = scoring.score_a3(
        findings, _A3_GOLD, flaw_keywords=("Marktanteil", "47", "9'750'000"),
    )
    assert missed["false_consensus"] is True
    found = scoring.score_a3(
        findings + [{
            "field_id": "VC.BUSINESS_TARGETS_MODEL.EDITOR", "target_section": "3.1",
            "description": "Der Marktanteil von 47 Prozent ist unbelegt.",
        }],
        _A3_GOLD, flaw_keywords=("Marktanteil", "47", "9'750'000"),
    )
    assert found["false_consensus"] is False


# --- Aggregation ---------------------------------------------------------------------


def test_mean_std_and_gate_share():
    assert scoring.mean_std([]) == (None, None)
    assert scoring.mean_std([2.0]) == (2.0, 0.0)
    mean, std = scoring.mean_std([1.0, 3.0])
    assert mean == 2.0 and std > 0
    rows = [
        {"status": PASS}, {"status": FAIL}, {"status": NOT_RUN}, {"status": PASS},
    ]
    assert scoring.deterministic_gate_share(rows) == pytest.approx(2 / 3)


def test_weighted_a2_score_weights_sum_and_pending():
    assert sum(scoring.A2_WEIGHTS.values()) == pytest.approx(1.0)
    human = {crit: 5.0 for crit in scoring.A2_RUBRIC_BUCKETS}
    full = scoring.weighted_a2_score(human, gate_share=1.0, cost_latency_score=1.0)
    assert full["score"] == 1.0
    assert not full["provisional"]

    provisional = scoring.weighted_a2_score(None, gate_share=1.0, cost_latency_score=None)
    assert provisional["provisional"]
    assert "factuality_evidence" in provisional["pending_buckets"]
    assert provisional["score"] == 1.0  # nur deterministischer Anteil gedeckt


def test_cost_latency_relative_handles_none():
    values = {"a": 10.0, "b": 20.0, "c": None}
    rel = scoring.cost_latency_relative(values)
    assert rel["a"] == 1.0 and rel["b"] == 0.0 and rel["c"] is None
    assert scoring.cost_latency_relative({"x": None}) == {"x": None}
    assert scoring.cost_latency_relative({"x": 5.0, "y": 5.0}) == {"x": 1.0, "y": 1.0}


def test_blind_assignment_deterministic_unique_and_nonce_sensitive():
    candidates = ["cand_a", "cand_b", "cand_c", "cand_d"]
    first = scoring.build_blind_assignment(candidates, "nonce-1")
    second = scoring.build_blind_assignment(candidates, "nonce-1")
    assert first == second
    assert sorted(first.values()) == ["Model A", "Model B", "Model C", "Model D"]
    order_a = scoring.shuffle_for_review([1, 2, 3, 4, 5], "nonce-1")
    order_b = scoring.shuffle_for_review([1, 2, 3, 4, 5], "nonce-1")
    assert order_a == order_b
    assert sorted(order_a) == [1, 2, 3, 4, 5]
