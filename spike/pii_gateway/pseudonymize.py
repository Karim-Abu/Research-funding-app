"""Pseudonymisierung/Tokenisierung erkannter Entitäten (Spike, Tier-unabhängig).

WICHTIG: Dies ist **Pseudonymisierung/Tokenisierung**, KEINE garantierte
Anonymisierung. Erkannte Spans werden durch typisierte Platzhalter ersetzt
(``[PERSON_1]``, ``[EMAIL_1]``, …). Gleiche Rohwerte erhalten denselben
Platzhalter (konsistente Ersetzung).

Die Rückersetzungs-Tabelle (mapping) lebt AUSSCHLIESSLICH im Speicher und wird
von diesem Modul nie in Datei, Log, Audit oder Git geschrieben. Der Aufrufer ist
verantwortlich, die Map nach Gebrauch zu verwerfen (siehe evaluate.py
``--restore-demo``).

Spike-Regel: kein Import aus backend/app oder lib/.
"""
from __future__ import annotations

from dataclasses import dataclass

from detectors import Span


@dataclass
class PseudonymizationResult:
    text: str
    # placeholder -> Rohwert. NUR im Speicher. Nie persistieren.
    mapping: dict[str, str]


def pseudonymize(text: str, spans: list[Span]) -> PseudonymizationResult:
    """Ersetzt die Spans durch typisierte Platzhalter; liefert Text + Speicher-Map."""
    ordered = sorted(spans, key=lambda s: s.start)
    counters: dict[str, int] = {}
    value_to_placeholder: dict[tuple[str, str], str] = {}
    mapping: dict[str, str] = {}

    # Von rechts nach links ersetzen, damit vorherige Offsets gültig bleiben.
    result = text
    for span in sorted(ordered, key=lambda s: s.start, reverse=True):
        key = (span.type, span.value)
        placeholder = value_to_placeholder.get(key)
        if placeholder is None:
            counters[span.type] = counters.get(span.type, 0) + 1
            placeholder = f"[{span.type}_{counters[span.type]}]"
            value_to_placeholder[key] = placeholder
            mapping[placeholder] = span.value
        result = result[: span.start] + placeholder + result[span.end :]

    return PseudonymizationResult(text=result, mapping=mapping)


def restore(pseudo_text: str, mapping: dict[str, str]) -> str:
    """Rückersetzung rein aus der Speicher-Map (Demo). Map danach verwerfen."""
    restored = pseudo_text
    # Längere Platzhalter zuerst, damit z. B. [PERSON_11] vor [PERSON_1] greift.
    for placeholder in sorted(mapping, key=len, reverse=True):
        restored = restored.replace(placeholder, mapping[placeholder])
    return restored
