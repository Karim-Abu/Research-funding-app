"""EVAL.1 — Kostensemantik-Tests (pricing.resolve_cost / sum_priced_chf).

Rein lokal/deterministisch: keine DB, kein Netzwerk, keine echten Preise.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.evaluation import pricing
from app.evaluation.pricing import (
    COST_STATUS_NOT_APPLICABLE,
    COST_STATUS_PRICED,
    COST_STATUS_UNKNOWN,
    PRICE_TABLE,
    PRICE_TABLE_VERSION,
    PriceEntry,
    resolve_cost,
    sum_priced_chf,
)
from app.config.settings import get_settings


def test_missing_price_is_unknown_price():
    res = resolve_cost(
        provider="anthropic_direct", model_id="claude-haiku-4-5-20251001",
        input_tokens=100, output_tokens=200,
    )
    assert res.cost_status == COST_STATUS_UNKNOWN
    assert res.cost_chf == 0.0
    assert res.price_version is None


def test_fake_adapter_name_is_not_applicable():
    # Route sagt anthropic_direct, aber der Fake-Adapter hat den Call bedient:
    # kein externer Call ⇒ not_applicable, unabhängig von der Contract-Route.
    res = resolve_cost(
        provider="anthropic_direct", model_id="claude-haiku-4-5-20251001",
        input_tokens=10, output_tokens=20, adapter_name="fake",
    )
    assert res.cost_status == COST_STATUS_NOT_APPLICABLE
    assert res.cost_chf == 0.0
    assert res.price_version is None


def test_fake_provider_string_is_not_applicable():
    res = resolve_cost(provider="fake", model_id="x", input_tokens=1, output_tokens=1)
    assert res.cost_status == COST_STATUS_NOT_APPLICABLE


def test_priced_with_zero_cost_stays_priced(monkeypatch):
    # priced mit 0.0 ist NICHT unknown_price: der Status trägt die Semantik,
    # nicht der Betrag (cost_chf=0.0 heisst nie automatisch "kostenlos").
    monkeypatch.setitem(
        PRICE_TABLE,
        ("test_provider", "test-model"),
        PriceEntry(0.0, 0.0, "https://example.test/owner-todo", "2026-07-08"),
    )
    res = resolve_cost(
        provider="test_provider", model_id="test-model",
        input_tokens=1000, output_tokens=1000,
    )
    assert res.cost_status == COST_STATUS_PRICED
    assert res.cost_chf == 0.0
    assert res.price_version == PRICE_TABLE_VERSION


def test_priced_computation_per_1k_tokens(monkeypatch):
    monkeypatch.setitem(
        PRICE_TABLE,
        ("test_provider", "test-model"),
        PriceEntry(0.5, 1.5, "https://example.test/owner-todo", "2026-07-08"),
    )
    res = resolve_cost(
        provider="test_provider", model_id="test-model",
        input_tokens=2000, output_tokens=1000,
    )
    assert res.cost_status == COST_STATUS_PRICED
    assert res.cost_chf == pytest.approx(2 * 0.5 + 1 * 1.5)


def test_price_table_rows_carry_source_and_date():
    # CI-Guard gegen erfundene Preise: jede reale Zeile braucht Quelle + Datum.
    for key, entry in PRICE_TABLE.items():
        assert entry.source_url.strip(), f"PRICE_TABLE {key}: source_url fehlt"
        assert entry.last_checked.strip(), f"PRICE_TABLE {key}: last_checked fehlt"


def test_price_table_initially_empty_no_real_prices():
    # EVAL.1 Owner-Entscheid: noch keine Realpreise eingetragen.
    assert pricing.PRICE_TABLE == {}


def test_deployment_price_requires_version_and_evidence(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "agent_model_pricing_chf_per_million", {
        "evidenced-model": {
            "input_chf_per_million": 2.0,
            "output_chf_per_million": 8.0,
            "price_version": "2026-07-15.v1",
            "source_url": "https://provider.example.test/pricing",
            "checked_at": "2026-07-15",
        },
        "unversioned-model": {
            "input_chf_per_million": 2.0,
            "output_chf_per_million": 8.0,
        },
    })
    priced = resolve_cost(
        provider="openai_direct", model_id="evidenced-model",
        input_tokens=1_000_000, output_tokens=1_000_000,
    )
    assert priced.cost_status == COST_STATUS_PRICED
    assert priced.cost_chf == pytest.approx(10.0)
    assert priced.price_version == "2026-07-15.v1"
    unknown = resolve_cost(
        provider="openai_direct", model_id="unversioned-model",
        input_tokens=1, output_tokens=1,
    )
    assert unknown.cost_status == COST_STATUS_UNKNOWN


def test_sum_only_priced():
    @dataclass
    class Rec:
        cost_chf: float
        cost_status: str

    records = [
        Rec(1.25, COST_STATUS_PRICED),
        Rec(99.0, COST_STATUS_UNKNOWN),        # zählt nie
        Rec(50.0, COST_STATUS_NOT_APPLICABLE),  # zählt nie
        Rec(0.75, COST_STATUS_PRICED),
    ]
    assert sum_priced_chf(records) == pytest.approx(2.0)
    assert sum_priced_chf([]) == 0.0
