"""EVAL.1 — Preistabelle und Kostensemantik-Auflösung (Messgrundlage).

Pure Modul ohne App-Imports. Preise werden NIE erfunden: die Tabelle ist
initial leer; jede künftige echte Zeile braucht ``source_url`` und
``last_checked`` (Owner-Entscheid EVAL.0 D4). Fehlender Eintrag ⇒
``unknown_price``; Fake-/Local-Adapter ⇒ ``not_applicable`` (kein externer
Call). ``cost_chf=0.0`` darf nie als "kostenlos" interpretiert werden —
Summen sind nur über ``cost_status='priced'`` zulässig.
"""
from __future__ import annotations

from dataclasses import dataclass

# Version der Preistabelle (Datum + Laufnummer). Wird als price_version nur
# auf 'priced'-Records gestempelt (Reproduzierbarkeit, EVAL.0 D3).
PRICE_TABLE_VERSION = "2026-07-08.0"

COST_STATUS_PRICED = "priced"
COST_STATUS_UNKNOWN = "unknown_price"
COST_STATUS_NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class PriceEntry:
    input_chf_per_1k: float
    output_chf_per_1k: float
    # Pflicht für jede echte Zeile: belegbare Quelle + Prüfdatum (ISO).
    source_url: str
    last_checked: str


# Bewusst LEER (EVAL.1, Owner-Entscheid: keine Realpreise eintragen).
# Schlüssel: (provider, model_id) wie in UsageRecord persistiert.
# TODO(Owner, EVAL.0 D4): reale (provider, model_id)-Preiszeilen mit
# source_url + last_checked ergänzen, PRICE_TABLE_VERSION anheben.
PRICE_TABLE: dict[tuple[str, str], PriceEntry] = {}

# Adapter-/Provider-Kennungen, die "kein externer Call" bedeuten.
_NOT_APPLICABLE_NAMES = frozenset({"fake"})


@dataclass(frozen=True)
class CostResolution:
    cost_chf: float
    cost_status: str
    price_version: str | None


def resolve_cost(
    *,
    provider: str | None,
    model_id: str | None,
    input_tokens: int,
    output_tokens: int,
    adapter_name: str | None = None,
) -> CostResolution:
    """Kostensemantik pro Call: fake/local ⇒ not_applicable; Tabellen-Miss ⇒
    unknown_price (cost_chf bleibt 0.0, nie summieren); Hit ⇒ priced."""
    if (adapter_name or "") in _NOT_APPLICABLE_NAMES or (
        provider or ""
    ) in _NOT_APPLICABLE_NAMES:
        return CostResolution(0.0, COST_STATUS_NOT_APPLICABLE, None)
    entry = PRICE_TABLE.get((provider or "", model_id or ""))
    if entry is None:
        return CostResolution(0.0, COST_STATUS_UNKNOWN, None)
    cost = (input_tokens / 1000) * entry.input_chf_per_1k + (
        output_tokens / 1000
    ) * entry.output_chf_per_1k
    return CostResolution(round(cost, 6), COST_STATUS_PRICED, PRICE_TABLE_VERSION)


def sum_priced_chf(records) -> float:
    """Summiert cost_chf NUR über Records mit cost_status='priced'.

    Nimmt beliebige Objekte mit ``cost_chf``/``cost_status`` (z. B. UsageRecord).
    unknown_price/not_applicable tragen nie zu einer Summe bei.
    """
    return round(
        sum(
            float(r.cost_chf)
            for r in records
            if getattr(r, "cost_status", None) == COST_STATUS_PRICED
        ),
        6,
    )
