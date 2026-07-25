"""Versioned, fail-closed provider-cost resolution.

Provider list prices are stored in USD because that is the billable currency.
CHF is an explicitly recorded SNB reference conversion, never an invented
provider price. A price is returned only for an exact model id and a fully
known set of billed token categories.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone


PRICE_TABLE_VERSION = "2026-07-25.1"
COST_STATUS_PRICED = "priced"
COST_STATUS_UNKNOWN = "unknown_price"
COST_STATUS_NOT_APPLICABLE = "not_applicable"

# Reference conversion for UI orientation. It is intentionally persisted on
# each UsageRecord; changing this value never rewrites historical costs.
SNB_USD_CHF_REFERENCE_RATE = 0.8065
SNB_USD_CHF_REFERENCE_DATE = "2026-07-17"
SNB_USD_CHF_SOURCE_URL = (
    "https://www.snb.ch/en/the-snb/mandates-goals/statistics/"
    "statistics-pub/current_interest_exchange_rates"
)


@dataclass(frozen=True)
class PriceEntry:
    """Legacy CHF entry retained for deployment-specific, verified mappings.

    The public catalogue below is USD-first. This type remains compatible with
    existing deployment overrides and tests while unknown cache categories stay
    fail-closed.
    """

    input_chf_per_1k: float
    output_chf_per_1k: float
    source_url: str
    last_checked: str


@dataclass(frozen=True)
class UsdPriceEntry:
    model_id: str
    input_usd_per_million: float
    cached_input_usd_per_million: float
    output_usd_per_million: float
    effective_from: date
    source_url: str
    last_checked: str
    version: str


OPENAI_PRICE_SOURCE = "https://openai.com/index/gpt-5-6/"
ANTHROPIC_PRICE_SOURCE = "https://www.anthropic.com/news/claude-sonnet-5"
_CHECKED_AT = "2026-07-24"

# The catalogue above was documented on 2026-07-24, but that is the check date,
# not a price change: these models already served the live pilot at the same
# published rates from its start (2026-07-23). We therefore make the catalogue
# effective from a pilot-covering floor so real pilot calls price at the exact
# published rate rather than staying fail-closed unknown. The only genuine
# promotional rate (Claude Sonnet 5 intro) is applied to earlier dates too,
# which is conservative (it is the cheaper rate). The dated standard Sonnet 5
# rate (2026-09-01) is a real future change and keeps its own effective date.
_PILOT_EFFECTIVE_FROM = date(2026, 7, 1)

# Exact, public model ids. Deployments that use a provider-specific dated id
# must add that id explicitly to their verified configuration; aliases are not
# guessed. Sonnet 5 has two effective dates by provider announcement.
USD_PRICE_TABLE: dict[str, tuple[UsdPriceEntry, ...]] = {
    "claude-sonnet-5": (
        UsdPriceEntry("claude-sonnet-5", 2.0, 0.2, 10.0, _PILOT_EFFECTIVE_FROM, ANTHROPIC_PRICE_SOURCE, _CHECKED_AT, "2026-07-24.sonnet5-intro"),
        UsdPriceEntry("claude-sonnet-5", 3.0, 0.3, 15.0, date(2026, 9, 1), ANTHROPIC_PRICE_SOURCE, _CHECKED_AT, "2026-09-01.sonnet5-standard"),
    ),
    "claude-sonnet-4-6": (
        UsdPriceEntry("claude-sonnet-4-6", 3.0, 0.3, 15.0, _PILOT_EFFECTIVE_FROM, ANTHROPIC_PRICE_SOURCE, _CHECKED_AT, "2026-07-24.sonnet46"),
    ),
    "gpt-5.6-luna": (
        UsdPriceEntry("gpt-5.6-luna", 1.0, 0.1, 6.0, _PILOT_EFFECTIVE_FROM, OPENAI_PRICE_SOURCE, _CHECKED_AT, "2026-07-24.gpt56-luna"),
    ),
    "gpt-5.6-terra": (
        UsdPriceEntry("gpt-5.6-terra", 2.5, 0.25, 15.0, _PILOT_EFFECTIVE_FROM, OPENAI_PRICE_SOURCE, _CHECKED_AT, "2026-07-24.gpt56-terra"),
    ),
    "gpt-5.6-sol": (
        UsdPriceEntry("gpt-5.6-sol", 5.0, 0.5, 30.0, _PILOT_EFFECTIVE_FROM, OPENAI_PRICE_SOURCE, _CHECKED_AT, "2026-07-24.gpt56-sol"),
    ),
    "gpt-5.4": (
        UsdPriceEntry("gpt-5.4", 2.5, 0.25, 15.0, _PILOT_EFFECTIVE_FROM, OPENAI_PRICE_SOURCE, _CHECKED_AT, "2026-07-24.gpt54"),
    ),
    "gpt-5.4-mini": (
        UsdPriceEntry("gpt-5.4-mini", 0.75, 0.075, 4.5, _PILOT_EFFECTIVE_FROM, OPENAI_PRICE_SOURCE, _CHECKED_AT, "2026-07-24.gpt54-mini"),
    ),
}

# Compatibility surface for historic test/configuration readers. It is never
# used to price a new provider call: a CHF-only rule cannot prove the exact USD
# amount billed by a provider.
PRICE_TABLE: dict[tuple[str, str], PriceEntry] = {}
_NOT_APPLICABLE_NAMES = frozenset({"fake"})


@dataclass(frozen=True)
class CostResolution:
    cost_chf: float
    cost_status: str
    price_version: str | None
    cost_usd: float | None = None
    fx_chf_per_usd: float | None = None
    price_source_url: str | None = None


def _as_date(value: date | datetime | None) -> date:
    if value is None:
        return datetime.now(timezone.utc).date()
    return value.date() if isinstance(value, datetime) else value


def _public_entry(model_id: str, occurred_at: date) -> UsdPriceEntry | None:
    entries = USD_PRICE_TABLE.get(model_id, ())
    applicable = [entry for entry in entries if entry.effective_from <= occurred_at]
    return max(applicable, key=lambda entry: entry.effective_from) if applicable else None


def _configured_chf_entry(model_id: str, settings) -> tuple[PriceEntry | None, str | None]:
    if settings is None:
        try:
            from app.config.settings import get_settings
            settings = get_settings()
        except Exception:  # pragma: no cover - fail closed
            return None, None
    configured = getattr(settings, "agent_model_pricing_chf_per_million", {}).get(model_id)
    required = {
        "input_chf_per_million", "output_chf_per_million", "price_version",
        "source_url", "checked_at",
    }
    if not isinstance(configured, dict) or not required <= set(configured):
        return None, None
    try:
        entry = PriceEntry(
            input_chf_per_1k=float(configured["input_chf_per_million"]) / 1000,
            output_chf_per_1k=float(configured["output_chf_per_million"]) / 1000,
            source_url=str(configured["source_url"]).strip(),
            last_checked=str(configured["checked_at"]).strip(),
        )
        version = str(configured["price_version"]).strip()
    except (TypeError, ValueError):
        return None, None
    if not (entry.source_url and entry.last_checked and version):
        return None, None
    return entry, version


def resolve_cost(
    *,
    provider: str | None,
    model_id: str | None,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
    cache_write_input_tokens: int = 0,
    occurred_at: date | datetime | None = None,
    adapter_name: str | None = None,
    settings=None,
) -> CostResolution:
    """Resolve one provider call without ever treating unknown data as free."""
    if (adapter_name or "") in _NOT_APPLICABLE_NAMES or (provider or "") in _NOT_APPLICABLE_NAMES:
        return CostResolution(0.0, COST_STATUS_NOT_APPLICABLE, None)
    if not model_id or min(input_tokens, output_tokens, cached_input_tokens, cache_write_input_tokens) < 0:
        return CostResolution(0.0, COST_STATUS_UNKNOWN, None)
    # A cache write has a distinct provider price. Our agreed public catalogue
    # contains cache-read prices only, therefore it must remain visibly unknown.
    if cache_write_input_tokens > 0 or cached_input_tokens > input_tokens:
        return CostResolution(0.0, COST_STATUS_UNKNOWN, None)

    when = _as_date(occurred_at)
    usd_entry = _public_entry(model_id, when)
    if usd_entry is not None:
        standard_input = input_tokens - cached_input_tokens
        cost_usd = (
            standard_input * usd_entry.input_usd_per_million
            + cached_input_tokens * usd_entry.cached_input_usd_per_million
            + output_tokens * usd_entry.output_usd_per_million
        ) / 1_000_000
        cost_usd = round(cost_usd, 8)
        cost_chf = round(cost_usd * SNB_USD_CHF_REFERENCE_RATE, 8)
        return CostResolution(
            cost_chf, COST_STATUS_PRICED, usd_entry.version,
            cost_usd=cost_usd,
            fx_chf_per_usd=SNB_USD_CHF_REFERENCE_RATE,
            price_source_url=usd_entry.source_url,
        )

    # A CHF-only legacy/configured row has no provider-billed USD amount and
    # therefore cannot be shown as exact. New model ids must be added to the
    # versioned USD catalogue above.
    return CostResolution(0.0, COST_STATUS_UNKNOWN, None)


def sum_priced_chf(records) -> float:
    return round(
        sum(float(r.cost_chf) for r in records if getattr(r, "cost_status", None) == COST_STATUS_PRICED),
        6,
    )


def sum_priced_usd(records) -> float:
    return round(
        sum(
            float(r.cost_usd or 0.0)
            for r in records
            if getattr(r, "cost_status", None) == COST_STATUS_PRICED
            and getattr(r, "cost_usd", None) is not None
        ),
        8,
    )
