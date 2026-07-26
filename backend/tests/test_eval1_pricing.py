"""EVAL.1 — Kostensemantik-Tests (pricing.resolve_cost / sum_priced_chf).

Rein lokal/deterministisch: keine DB, kein Netzwerk, keine echten Preise.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

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
    # Bewusst eine Id, die im USD-Katalog NICHT vorkommt und dort auch nie
    # auftauchen soll. Vorher stand hier claude-haiku-4-5-20251001; seit die
    # Id am 2026-07-26 katalogisiert wurde, pruefte der Test das Gegenteil
    # seiner Absicht. Der Name macht die Rolle jetzt explizit.
    res = resolve_cost(
        provider="anthropic_direct", model_id="model-without-catalogue-entry",
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


def test_legacy_chf_row_is_not_treated_as_an_exact_usd_price(monkeypatch):
    monkeypatch.setitem(
        PRICE_TABLE,
        ("test_provider", "test-model"),
        PriceEntry(0.0, 0.0, "https://example.test/owner-todo", "2026-07-08"),
    )
    res = resolve_cost(
        provider="test_provider", model_id="test-model",
        input_tokens=1000, output_tokens=1000,
    )
    assert res.cost_status == COST_STATUS_UNKNOWN
    assert res.cost_chf == 0.0
    assert res.price_version is None


def test_legacy_chf_computation_is_not_used_for_new_usage(monkeypatch):
    monkeypatch.setitem(
        PRICE_TABLE,
        ("test_provider", "test-model"),
        PriceEntry(0.5, 1.5, "https://example.test/owner-todo", "2026-07-08"),
    )
    res = resolve_cost(
        provider="test_provider", model_id="test-model",
        input_tokens=2000, output_tokens=1000,
    )
    assert res.cost_status == COST_STATUS_UNKNOWN
    assert res.cost_usd is None


def test_price_table_rows_carry_source_and_date():
    # CI-Guard gegen erfundene Preise: jede reale Zeile braucht Quelle + Datum.
    for key, entry in PRICE_TABLE.items():
        assert entry.source_url.strip(), f"PRICE_TABLE {key}: source_url fehlt"
        assert entry.last_checked.strip(), f"PRICE_TABLE {key}: last_checked fehlt"


def test_price_table_initially_empty_no_real_prices():
    # EVAL.1 Owner-Entscheid: noch keine Realpreise eingetragen.
    assert pricing.PRICE_TABLE == {}


def test_chf_only_deployment_configuration_is_not_used(monkeypatch):
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
    assert priced.cost_status == COST_STATUS_UNKNOWN
    assert priced.cost_usd is None
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


def test_public_usd_price_uses_cache_read_tokens():
    res = resolve_cost(
        provider="openai_direct",
        model_id="gpt-5.6-luna",
        input_tokens=20_000,
        cached_input_tokens=5_000,
        output_tokens=3_000,
        occurred_at=date(2026, 7, 24),
    )
    # (15k * $1 + 5k * $0.10 + 3k * $6) / 1M
    assert res.cost_status == COST_STATUS_PRICED
    assert res.cost_usd == pytest.approx(0.0335)
    assert res.cost_chf == pytest.approx(0.0335 * pricing.SNB_USD_CHF_REFERENCE_RATE)
    assert res.price_version == "2026-07-24.gpt56-luna"


def test_sonnet_five_price_changes_on_first_september():
    intro = resolve_cost(
        provider="anthropic_direct", model_id="claude-sonnet-5",
        input_tokens=20_000, output_tokens=3_000,
        occurred_at=date(2026, 8, 31),
    )
    standard = resolve_cost(
        provider="anthropic_direct", model_id="claude-sonnet-5",
        input_tokens=20_000, output_tokens=3_000,
        occurred_at=date(2026, 9, 1),
    )
    assert intro.cost_usd == pytest.approx(0.07)
    assert standard.cost_usd == pytest.approx(0.105)
    assert intro.price_version != standard.price_version


def test_cache_write_is_never_guessed_as_cache_read_price():
    res = resolve_cost(
        provider="anthropic_direct", model_id="claude-sonnet-5",
        input_tokens=100, cached_input_tokens=10, cache_write_input_tokens=5,
        output_tokens=20, occurred_at=date(2026, 7, 24),
    )
    assert res.cost_status == COST_STATUS_UNKNOWN
    assert res.cost_usd is None


def test_pilot_run_before_catalogue_documentation_date_is_priced():
    # The catalogue was documented on 2026-07-24, but the models already served
    # the live pilot from 2026-07-23 at the same published rates. A pilot call on
    # 2026-07-23 must therefore price (not stay fail-closed unknown).
    for model_id in ("gpt-5.6-luna", "gpt-5.6-terra", "claude-sonnet-5"):
        res = resolve_cost(
            provider="openai_direct", model_id=model_id,
            input_tokens=20_000, output_tokens=3_000,
            occurred_at=date(2026, 7, 23),
        )
        assert res.cost_status == COST_STATUS_PRICED, model_id
        assert res.cost_usd is not None and res.cost_usd > 0
