"""Public web research provider boundary (Milestone 9I-A).

A backend-only service boundary: Firecrawl (real, env-gated) or a deterministic fake
for tests. API keys live only in the backend env and are never logged, audited or
exported. The web fake provider is gated by its OWN setting
(``web_research_fake_provider``) and is never implied by ``agent_fake_provider``.
"""
from app.research.providers.base import (  # noqa: F401
    CreditExceeded,
    FetchOutcome,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    SearchCandidate,
    SearchOutcome,
    SearchRequest,
    WebResearchProvider,
)
from app.research.providers.resolver import get_web_provider  # noqa: F401
