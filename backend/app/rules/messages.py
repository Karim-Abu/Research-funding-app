"""Katalog-Meldungen für Regel-Ergebnisse (R2.6).

Einzige Quelle der Texte ist der Owner-approvte Message-Katalog
``docs/repair/message-catalog.md`` (Freigabe 2026-07-07; drei Texte wörtlich
aus dem Prompt-Pack). Dieses Modul VERDRAHTET nur — es erfindet keine Texte
und ändert keine Zweig-Semantik: der Schlüssel ist ``(rule_id, mapping_key)``,
die Zweige selbst entscheiden weiterhin die Handler. Für Regeln/Zweige ohne
Katalogeintrag bleibt der bestehende Handler-Text unverändert (``default``).
"""
from __future__ import annotations

# (rule_id, mapping_key) -> Katalogtext (source_ref = rule_id im Katalog).
_MESSAGES: dict[tuple[str, str], str] = {
    ("INNO.PARTNER.IMPLEMENTATION.MIN1_CH", "false"):
        "Kein Umsetzungspartner mit Schweiz-Bezug erfasst.",
    ("INNO.PARTNER.IMPLEMENTATION.MIN1_CH", "missing"):
        "Angaben zum Umsetzungspartner unvollständig (Schweiz-Bezug/"
        "Wertschöpfung offen) — Prüfung nicht abschliessend.",
    ("INNO.PARTNER.IMPLEMENTATION.MIN1_CH", "true"):
        "Umsetzungspartner mit Schweiz-Bezug erfasst.",
    ("INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE", "false"):
        "Kein beitragsberechtigter Schweizer Forschungspartner erfasst.",
    ("INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE", "missing"):
        "Beitragsberechtigung des Forschungspartners noch nicht bestätigt — "
        "Prüfung nicht abschliessend.",
    ("INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE", "true"):
        "Beitragsberechtigter Schweizer Forschungspartner erfasst.",
    ("INNO.PARTNER.INDEPENDENCE.FINANCIAL_20", "missing"):
        "Finanzielle Unabhängigkeit benötigt menschliche Prüfung.",
    ("INNO.PARTNER.INDEPENDENCE.FINANCIAL_20", "at_or_above_threshold"):
        "Beteiligung erreicht oder überschreitet die 20-Prozent-Schwelle — "
        "menschliche Prüfung erforderlich.",
    ("INNO.PARTNER.INDEPENDENCE.FINANCIAL_20", "below_threshold_and_confirmed"):
        "Finanzielle Unabhängigkeit bestätigt; Beteiligungen unter der Schwelle.",
}


def rule_message(rule_id: str, mapping_key: str, default: str) -> str:
    """Katalogtext für (rule_id, Zweig); ohne Eintrag der bisherige Text."""
    return _MESSAGES.get((rule_id, mapping_key), default)
