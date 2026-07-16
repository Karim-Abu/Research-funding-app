"""Web research provider resolution (Milestone 9I-A).

Selects the real Firecrawl provider or the deterministic fake based on settings, and
pairs it with the DNS resolver the SSRF gate should use. A module-global override
(``set_override``) lets tests inject a provider without monkeypatching settings.
"""
from __future__ import annotations

from typing import Callable

from app.config.settings import Settings
from app.research.providers.base import WebResearchProvider
from app.research.providers.fake import FakeWebProvider, fake_dns_resolver
from app.research.providers.firecrawl import FirecrawlProvider

DnsResolver = Callable[[str], list[str]]

# (provider, dns_resolver | None) — when set, returned verbatim by get_web_provider.
_OVERRIDE: tuple[WebResearchProvider, DnsResolver | None] | None = None


def set_override(value: tuple[WebResearchProvider, DnsResolver | None] | None) -> None:
    global _OVERRIDE
    _OVERRIDE = value


def get_web_provider(
    settings: Settings,
) -> tuple[WebResearchProvider, DnsResolver | None]:
    if _OVERRIDE is not None:
        return _OVERRIDE
    # The web fake has its OWN flag (binding correction 5) — never agent_fake_provider.
    if settings.web_research_fake_provider:
        return FakeWebProvider(), fake_dns_resolver
    provider = FirecrawlProvider(
        api_key=settings.firecrawl_api_key,
        timeout_seconds=settings.web_research_timeout_seconds,
        privacy_mode=settings.firecrawl_privacy_mode,
    )
    return provider, None  # real DNS resolution
