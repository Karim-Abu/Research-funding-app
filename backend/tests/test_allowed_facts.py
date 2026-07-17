"""AllowedFactsManifest: Normalisierung, Erlaubt-Basis, derived claims.

Pflichtfälle des Auftrags (2026-07-17): bekannte Fixture-Angaben dürfen NIE als
erfunden gelten (identische wie abweichende Schreibweise, Partnervarianten),
echte Neuangaben bleiben eine DQ, ein wegen Kontextbudget entfallenes Fragment
macht seine Zahlen NICHT erlaubt, und deterministisch abgeleitete Zahlen sind
weder Beleg noch Erfindung.
"""
from __future__ import annotations

import pytest

from app.agents.allowed_facts import build_manifest, check_claims

FIXTURE = (
    "Das Konsortium plant 10'000 Messungen pro Jahr. Der Zielmarkt wächst um "
    "45.5 % jährlich. Das Budget beträgt CHF 100'000. Partner ist die "
    "Muster Technologies AG in Zürich. Die Patentfamilie EP1234567 ist "
    "angemeldet. Die Linie umfasst 12 Stationen."
)


def _manifest(text: str = FIXTURE):
    return build_manifest([("current_field_text", text)])


# --- bekannte Angaben: nie eine Erfindung ------------------------------------


def test_known_number_identical_notation_is_not_invented():
    check = check_claims("Wir erwarten 10'000 Messungen.", _manifest())
    assert check.ok
    assert check.derived_numbers == ()


@pytest.mark.parametrize("notation", [
    "10000", "10 000", "10’000", "10'000",
])
def test_known_number_other_notation_is_not_invented(notation):
    assert check_claims(f"Rund {notation} Messungen.", _manifest()).ok


@pytest.mark.parametrize("notation", [
    "45.5 %", "45,5 %", "45.5%", "45,5 Prozent", "45.50 %",
])
def test_known_percentage_notation_variants_are_not_invented(notation):
    assert check_claims(f"Wachstum von {notation}.", _manifest()).ok


@pytest.mark.parametrize("notation", ["CHF 100'000", "100000 CHF", "100 000"])
def test_known_budget_notation_variants_are_not_invented(notation):
    assert check_claims(f"Das Budget umfasst {notation}.", _manifest()).ok


@pytest.mark.parametrize("variant", [
    "Muster Technologies AG",
    "muster technologies ag",
    "Muster  Technologies  AG",
])
def test_known_partner_name_variants_are_not_invented(variant):
    assert check_claims(f"Der Partner {variant} liefert Daten.", _manifest()).ok


def test_known_partner_umlaut_variant_is_not_invented():
    manifest = build_manifest([
        ("current_field_text", "Beteiligt ist die Zürcher Hochschule."),
    ])
    for variant in ("Zürcher Hochschule", "Zurcher Hochschule", "Zuercher Hochschule"):
        assert check_claims(f"Die {variant} forscht mit.", manifest).ok


def test_structured_partner_name_without_legal_suffix_is_known():
    """Strukturierte Partnerangaben tragen den blossen Namen — die Regex allein
    fände ihn nicht; ``add_known_organisations`` schliesst die Lücke."""
    from app.agents.allowed_facts import add_known_organisations

    manifest = add_known_organisations(
        build_manifest([("structured_input_payload", '{"partners": ["Fraunhofer"]}')]),
        ["Fraunhofer"],
    )
    assert check_claims("Das Fraunhofer Institut unterstützt.", manifest).ok


# --- echte Neuangaben: bleiben eine Disqualifikation --------------------------


def test_genuinely_new_number_is_disqualified():
    check = check_claims("Wir erreichen 87'321 Messungen.", _manifest())
    assert check.reason == "invented_numeric_token"


def test_genuinely_new_partner_is_disqualified():
    check = check_claims("Die Neuerfundene Systeme GmbH liefert zu.", _manifest())
    assert check.reason == "invented_partner_name"


def test_genuinely_new_patent_is_disqualified():
    check = check_claims("Siehe Patent EP9999999.", _manifest())
    assert check.reason == "invented_patent_identifier"


def test_number_from_budget_truncated_fragment_is_not_allowed():
    """Eine Zahl aus einem Fragment, das wegen Kontextbudget NICHT im finalen
    Request steht, gilt nicht als bekannt — auch wenn sie im Fall existiert."""
    visible = "Der Zielmarkt wächst. "  # das Fragment mit 77'000 fiel weg
    manifest = build_manifest([("source_fragment", visible)])
    assert check_claims("Es sind 77'000 Einheiten.", manifest).reason == (
        "invented_numeric_token"
    )


# --- deterministisch abgeleitete Zahlen --------------------------------------


def test_derived_number_is_marked_not_invented():
    manifest = build_manifest([
        ("current_field_text", "Kosten von 60'000 und 40'000 Franken."),
    ])
    check = check_claims("Zusammen 100'000 Franken.", manifest)
    assert check.ok, "Summe bekannter Werte ist keine Erfindung"
    assert check.derived_numbers == ("100'000",)


def test_derived_percentage_share_is_marked_not_invented():
    manifest = build_manifest([
        ("current_field_text", "25 von 50 Linien sind ausgerüstet."),
    ])
    check = check_claims("Das entspricht 50 %.", manifest)
    assert check.ok and check.derived_numbers == ()  # 50 ist selbst bekannt
    check = check_claims("Der Anteil liegt bei 200 %.", manifest)
    assert check.ok and check.derived_numbers == ("200",)  # 50/25*100


# --- Manifest-Metadaten -------------------------------------------------------


def test_manifest_meta_is_counts_only():
    manifest = _manifest()
    meta = manifest.meta()
    assert meta["number_count"] > 0
    assert meta["components"] == [{
        "kind": "current_field_text",
        "character_count": len(FIXTURE),
        # 10'000 · 45.5 · 100'000 · 12 (die Patentnummer ist kein Zahl-Token)
        "number_count": 4,
    }]
    assert len(meta["manifest_sha256"]) == 64
    # Keine Rohinhalte in den Metadaten.
    assert "Muster" not in str(meta) and "10'000" not in str(meta)


def test_manifest_sha_is_stable_across_notation():
    """Dieselben Fakten in anderer Schreibweise ⇒ identische Erlaubt-Basis."""
    a = build_manifest([("k", "10'000 Stück zu 45.5 %")])
    b = build_manifest([("k", "10 000 Stück zu 45,5 %")])
    assert a.sha256 == b.sha256
