"""SPIKE-Werkzeug (pii_gateway): erzeugt synthetische DE/CH-Fixtures mit exakten
Gold-Spans für den PII-Detektor-Benchmark.

AUSSCHLIESSLICH SYNTHETISCHE DATEN. Alle Namen, Adressen, E-Mails, Telefon-
nummern, Geburtsdaten, IBANs und Benutzernamen sind frei erfunden und referenzieren
keine reale Person und keine reale Organisation. Die IBANs sind gültig nach
Mod-97-Prüfsumme (für den Recognizer-Test), aber keiner echten Bank/Person
zugeordnet.

Spike-Regel: kein Import aus backend/app oder lib/. Reines Python-Stdlib.

Die Spans werden beim Zusammenbauen des Textes mitgezählt (kein manuelles
Offset-Rechnen). Aufruf:
    backend\\.venv\\Scripts\\python.exe spike\\pii_gateway\\make_fixtures.py
schreibt spike/pii_gateway/fixtures/cases.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Windows-Konsole ist häufig cp1252 — UTF-8 erzwingen, damit Umlaute/Pfeile in
# der Ausgabe nicht crashen (rein kosmetisch; die Dateien sind ohnehin UTF-8).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(__file__).parent / "fixtures" / "cases.json"

# Die 7 unterstützten Entitätstypen (Requirement 1).
ENTITY_TYPES = ("PERSON", "EMAIL", "PHONE", "ADDRESS", "DOB", "IBAN", "USERNAME")


class CaseBuilder:
    """Baut einen Text aus Fragmenten und zählt Entitäts-Spans exakt mit."""

    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        self.parts: list[str] = []
        self.entities: list[dict] = []
        self._len = 0

    def text(self, s: str) -> "CaseBuilder":
        self.parts.append(s)
        self._len += len(s)
        return self

    def ent(self, entity_type: str, value: str) -> "CaseBuilder":
        assert entity_type in ENTITY_TYPES, entity_type
        start = self._len
        self.parts.append(value)
        self._len += len(value)
        self.entities.append(
            {"type": entity_type, "start": start, "end": self._len, "value": value}
        )
        return self

    def build(self) -> dict:
        return {
            "id": self.case_id,
            "text": "".join(self.parts),
            "entities": self.entities,
        }


def _cases() -> list[dict]:
    cases: list[dict] = []

    # 1) Klar formatierte Werte, kompakt beisammen (formatierte PII).
    c = CaseBuilder("formatted-contact")
    (
        c.text("Kontakt: ")
        .ent("PERSON", "Anna Meier")
        .text(", E-Mail ")
        .ent("EMAIL", "anna.meier@example.ch")
        .text(", Tel. ")
        .ent("PHONE", "+41 79 123 45 67")
        .text(".")
    )
    cases.append(c.build())

    # 2) Schweizer IBAN mit Gruppierung + Benutzername (@handle).
    c = CaseBuilder("iban-username")
    (
        c.text("Bitte überweisen Sie auf ")
        .ent("IBAN", "CH93 0076 2011 6238 5295 7")
        .text(". Benutzername im Portal: ")
        .ent("USERNAME", "@a_meier")
        .text(".")
    )
    cases.append(c.build())

    # 3) Geburtsdatum in Ziffern + Adresse mit PLZ/Ort.
    c = CaseBuilder("dob-address")
    (
        c.text("Die Patientin, geboren am ")
        .ent("DOB", "14.03.1987")
        .text(", wohnt an der ")
        .ent("ADDRESS", "Bahnhofstrasse 12, 4051 Basel")
        .text(".")
    )
    cases.append(c.build())

    # 4) Freitext mit eingebettetem Namen + Adresse (schwer für Regex/Gazetteer).
    c = CaseBuilder("freeform-name-address")
    (
        c.text("Im letzten Meeting hat ")
        .ent("PERSON", "Tobias Frei")
        .text(
            " vorgeschlagen, den Prototyp bei einem Pilotkunden zu testen; "
            "die Lieferung geht an die "
        )
        .ent("ADDRESS", "Kornhausgasse 2, 4051 Basel")
        .text(".")
    )
    cases.append(c.build())

    # 5) DOB in Wortform + zweite E-Mail-Domain-Variante.
    c = CaseBuilder("dob-words-email")
    (
        c.text("Herr ")
        .ent("PERSON", "Claude Rothen")
        .text(" (geb. ")
        .ent("DOB", "3. Februar 1975")
        .text(") erreichen Sie unter ")
        .ent("EMAIL", "c.rothen@labor-example.ch")
        .text(".")
    )
    cases.append(c.build())

    # 6) Schweizer Festnetznummer im 0XX-Format + Benutzername als Feld.
    c = CaseBuilder("phone-local-username-field")
    (
        c.text("Rückruf erbeten unter ")
        .ent("PHONE", "061 279 17 17")
        .text(". Benutzername: ")
        .ent("USERNAME", "p.moriggl")
        .text(".")
    )
    cases.append(c.build())

    # 7) Mehrere Personen + IBAN (DE) ohne Leerzeichen.
    c = CaseBuilder("multi-person-iban")
    (
        c.text("Die Rechnung von ")
        .ent("PERSON", "Marco Oberli")
        .text(" und ")
        .ent("PERSON", "Pascal Moriggl")
        .text(" wird auf ")
        .ent("IBAN", "DE89370400440532013000")
        .text(" beglichen.")
    )
    cases.append(c.build())

    # 8) ISO-Datum + E-Mail + Telefon international.
    c = CaseBuilder("iso-date-mixed")
    (
        c.text("Termin bestätigt für ")
        .ent("PERSON", "Sarah Koch")
        .text(", Vertrag vom ")
        .ent("DOB", "1990-11-22")
        .text(", Kontakt ")
        .ent("EMAIL", "sarah.koch@example.org")
        .text(" oder ")
        .ent("PHONE", "+41-61-555-88-99")
        .text(".")
    )
    cases.append(c.build())

    # 9–12) NICHT-PII-Geheimnisfälle: enthalten Rohidee, Methodik, Partner-
    # strategie und Budgetlogik — ABER keine PII-Entitäten. Zeigt, dass der
    # Detektor Geschäftsgeheimnisse NICHT entfernt (Requirement 7). Keine Spans.
    cases.append(
        {
            "id": "secret-idea",
            "text": (
                "Unsere Kernidee ist ein dezentrales Zugriffs- und "
                "Kontrollmanagement für Gesundheitsdaten auf einem öffentlichen "
                "Distributed Ledger, das bestehende APIs ergänzt."
            ),
            "entities": [],
        }
    )
    cases.append(
        {
            "id": "secret-methodology",
            "text": (
                "Die proprietäre Methodik kombiniert ein morphologisches "
                "Bewertungsraster mit Lasttests, um die optimale Konfiguration "
                "aus Validatoren, Smart Contracts und Konsensparametern zu "
                "bestimmen."
            ),
            "entities": [],
        }
    )
    cases.append(
        {
            "id": "secret-partner-strategy",
            "text": (
                "Strategisch gewinnen wir zuerst ein Referenzlabor, danach die "
                "bestehende Kundenbasis, und erst im dritten Schritt den "
                "unerschlossenen Markt — dieser Fahrplan ist vertraulich."
            ),
            "entities": [],
        }
    )
    cases.append(
        {
            "id": "secret-budget-logic",
            "text": (
                "Die Kalkulation setzt einen Umsatz von fünfzig Rappen pro "
                "Datensatz und Jahr an, davon dreissig Prozent Marge; die "
                "genaue Herleitung bleibt intern."
            ),
            "entities": [],
        }
    )

    # 13) Adresse ohne PLZ (nur Strasse+Nr.) + Benutzername mit Ziffern.
    c = CaseBuilder("address-nozip")
    (
        c.text("Abholung an der ")
        .ent("ADDRESS", "Pfeffingerstrasse 19")
        .text(" durch Benutzer ")
        .ent("USERNAME", "@lab_user42")
        .text(".")
    )
    cases.append(c.build())

    # 14) Nur Personennamen im Fliesstext (Gazetteer-Grenzfall).
    c = CaseBuilder("names-only")
    (
        c.text("Anwesend waren ")
        .ent("PERSON", "Beat Dobmann")
        .text(" sowie ")
        .ent("PERSON", "Anna Meier")
        .text(" als Protokollführerin.")
    )
    cases.append(c.build())

    # --- Bewusst SCHWIERIGE Fälle: Generalisierungsgrenzen des deterministischen
    # Tiers (unbekannte Vornamen ausserhalb des Gazetteers, nicht-deutsche
    # Adressformate). Hier ist der ML-Tier voraussichtlich stärker; genau das
    # macht den Benchmark aussagekräftig. -----------------------------------
    # 15) Personenname ohne Gazetteer-Treffer (nicht-deutscher Vorname).
    c = CaseBuilder("hard-person-foreign")
    (
        c.text("Die Studie wurde von ")
        .ent("PERSON", "Ravi Subramaniam")
        .text(" geleitet; Kontakt ")
        .ent("EMAIL", "ravi.s@example.net")
        .text(".")
    )
    cases.append(c.build())

    # 16) Zweiter unbekannter Name im Fliesstext.
    c = CaseBuilder("hard-person-foreign-2")
    (
        c.text("Als Gutachterin fungierte ")
        .ent("PERSON", "Amara Okonkwo")
        .text(", erreichbar unter ")
        .ent("PHONE", "+41 44 000 11 22")
        .text(".")
    )
    cases.append(c.build())

    # 17) Adresse im französischen Format (kein deutsches Strassensuffix).
    c = CaseBuilder("hard-address-french")
    (
        c.text("Der Versand erfolgt an die ")
        .ent("ADDRESS", "Rue du Marché 8, 1204 Genève")
        .text(".")
    )
    cases.append(c.build())

    return cases


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cases = _cases()
    payload = {
        "_comment": (
            "Synthetische DE/CH-Fixtures für den PII-Detektor-Spike. Nur "
            "erfundene Daten. Spans sind [start, end) in Zeichen (Python-Slice). "
            "Fälle mit id-Präfix 'secret-' enthalten bewusst KEINE PII, sondern "
            "Geschäftsgeheimnisse/Methodik/Strategie/Budgetlogik (Requirement 7)."
        ),
        "entity_types": list(ENTITY_TYPES),
        "cases": cases,
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    n_ent = sum(len(c["entities"]) for c in cases)
    print(f"cases.json geschrieben: {len(cases)} Fälle, {n_ent} Gold-Entitäten → {OUT}")


if __name__ == "__main__":
    main()
