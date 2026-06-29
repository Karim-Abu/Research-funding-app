"""Provider protocol + transport types for public web research (Milestone 9I-A)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class ProviderUnavailable(Exception):
    """Provider not configured / not reachable (safe, expected)."""


class ProviderTimeout(Exception):
    """Provider exceeded the configured timeout."""


class ProviderError(Exception):
    """Provider returned an error response."""


class CreditExceeded(Exception):
    """Provider credit / budget limit reached."""


@dataclass(frozen=True)
class SearchRequest:
    query: str
    max_results: int
    preferred_domains: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchCandidate:
    url: str
    title: str
    snippet: str | None = None
    rank: int | None = None


@dataclass(frozen=True)
class SearchOutcome:
    candidates: list[SearchCandidate]
    provider: str
    latency_ms: int = 0
    credits_used: float | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FetchOutcome:
    text: str
    final_url: str
    content_type: str
    byte_size: int
    content_hash: str
    provider: str
    redirect_chain: list[str] = field(default_factory=list)
    latency_ms: int = 0
    credits_used: float | None = None


@runtime_checkable
class WebResearchProvider(Protocol):
    """Backend-only web research provider. Implementations must NOT leak API keys and
    must raise the typed exceptions above for any failure (never a bare Exception)."""

    name: str

    def available(self) -> bool: ...

    def search(self, request: SearchRequest) -> SearchOutcome: ...

    def fetch(self, url: str, *, max_bytes: int) -> FetchOutcome: ...
