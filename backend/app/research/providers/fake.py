"""Deterministic fake web research provider (Milestone 9I-A).

No network, no key. Drives ALL mandatory tests. Candidate hosts resolve (via the paired
``fake_dns_resolver``) to a fixed public IP so the SSRF gate passes deterministically for
the fake's own URLs while still blocking any unknown host.
"""
from __future__ import annotations

import hashlib

from app.research.providers.base import (
    CreditExceeded,
    FetchOutcome,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    SearchCandidate,
    SearchOutcome,
    SearchRequest,
)

# A public, non-private IPv4 (example.com's documented address range).
_FAKE_PUBLIC_IP = "93.184.216.34"
_FAKE_HOSTS = ("research.example.org", "publications.example.org", "profiles.example.org")


def fake_dns_resolver(host: str) -> list[str]:
    """Resolve only the fake provider's own hosts to a fixed public IP; anything else
    raises so an injected malicious host is still blocked by the SSRF gate."""
    if host.lower() in _FAKE_HOSTS:
        return [_FAKE_PUBLIC_IP]
    raise OSError(f"unknown host in fake resolver: {host}")


def _candidate(index: int, query: str) -> SearchCandidate:
    host = _FAKE_HOSTS[index % len(_FAKE_HOSTS)]
    return SearchCandidate(
        url=f"https://{host}/result/{index}",
        title=f"Öffentliche Quelle {index + 1} zu {query}",
        snippet=f"Öffentlich zugänglicher Auszug {index + 1} (Snippet ist kein Beleg).",
        rank=index + 1,
    )


class FakeWebProvider:
    """``mode`` ∈ success | timeout | error | credit | unavailable."""

    name = "fake"

    def __init__(self, *, mode: str = "success", result_count: int = 3) -> None:
        self._mode = mode
        self._result_count = result_count

    def available(self) -> bool:
        return self._mode != "unavailable"

    def _raise_for_mode(self) -> None:
        if self._mode == "unavailable":
            raise ProviderUnavailable("fake provider unavailable")
        if self._mode == "timeout":
            raise ProviderTimeout("fake provider timeout")
        if self._mode == "error":
            raise ProviderError("fake provider error")
        if self._mode == "credit":
            raise CreditExceeded("fake provider credit exceeded")

    def search(self, request: SearchRequest) -> SearchOutcome:
        self._raise_for_mode()
        n = max(0, min(request.max_results, self._result_count))
        candidates = [_candidate(i, request.query) for i in range(n)]
        return SearchOutcome(
            candidates=candidates, provider=self.name, latency_ms=1, credits_used=0.0
        )

    def fetch(self, url: str, *, max_bytes: int) -> FetchOutcome:
        self._raise_for_mode()
        body = (
            "Die Plattform dieser öffentlichen Quelle ist eine alternative Lösung für "
            "den Markt. Konkurrenten und Anbieter bieten ähnliche Produkte für Kunden "
            "an; im Vergleich unterscheidet sich das Angebot durch Differenzierung.\n\n"
            "Dieser Text stammt aus einer öffentlichen Webquelle und wird als normales "
            "Quellenmaterial importiert. Er ist erst nach der regulären, "
            "deterministischen Evidenzprüfung als Beleg verwendbar."
        )
        data = body.encode("utf-8")
        return FetchOutcome(
            text=body,
            final_url=url,
            content_type="text/html",
            byte_size=len(data),
            content_hash=hashlib.sha256(data).hexdigest(),
            provider=self.name,
            redirect_chain=[url],
            redirect_chain_verified=True,
            latency_ms=1,
            credits_used=0.0,
        )
