"""Firecrawl web research provider (Milestone 9I-A).

Real, env-gated. The API key is read from settings (backend env only) and is NEVER
logged, audited or exported. Disabled (``available()`` is False) when no key is
configured — the feature then simply reports unavailable; the backend never crashes.

Not exercised by any mandatory test; the deterministic fake drives CI. The network
calls below are guarded and only reached when a key is configured.
"""
from __future__ import annotations

import hashlib
import time

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

_BASE_URL = "https://api.firecrawl.dev/v1"


class FirecrawlProvider:
    name = "firecrawl"

    def __init__(self, *, api_key: str | None, timeout_seconds: int) -> None:
        self._api_key = api_key
        self._timeout = timeout_seconds

    def available(self) -> bool:
        return bool(self._api_key)

    def _client(self):
        if not self._api_key:
            raise ProviderUnavailable("firecrawl api key not configured")
        try:
            import httpx  # local import; optional dependency
        except ImportError as exc:  # pragma: no cover — httpx is installed in this app
            raise ProviderUnavailable("httpx not available") from exc
        # Authorization header carries the key; it must never be logged.
        return httpx.Client(
            base_url=_BASE_URL,
            timeout=self._timeout,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )

    def search(self, request: SearchRequest) -> SearchOutcome:  # pragma: no cover — network
        start = time.monotonic()
        try:
            with self._client() as client:
                resp = client.post(
                    "/search",
                    json={"query": request.query, "limit": request.max_results},
                )
        except Exception as exc:  # noqa: BLE001
            raise ProviderTimeout("firecrawl search failed") from exc
        if resp.status_code in (402, 429):
            raise CreditExceeded("firecrawl credit/budget limit")
        if resp.status_code >= 400:
            raise ProviderError(f"firecrawl search status {resp.status_code}")
        payload = resp.json()
        candidates: list[SearchCandidate] = []
        for i, item in enumerate(payload.get("data", []) or []):
            url = item.get("url")
            if not url:
                continue
            candidates.append(
                SearchCandidate(
                    url=url,
                    title=item.get("title") or url,
                    snippet=item.get("description"),
                    rank=i + 1,
                )
            )
        latency = int((time.monotonic() - start) * 1000)
        return SearchOutcome(candidates=candidates, provider=self.name, latency_ms=latency)

    def fetch(self, url: str, *, max_bytes: int) -> FetchOutcome:  # pragma: no cover — network
        start = time.monotonic()
        try:
            with self._client() as client:
                resp = client.post("/scrape", json={"url": url, "formats": ["markdown"]})
        except Exception as exc:  # noqa: BLE001
            raise ProviderTimeout("firecrawl scrape failed") from exc
        if resp.status_code in (402, 429):
            raise CreditExceeded("firecrawl credit/budget limit")
        if resp.status_code >= 400:
            raise ProviderError(f"firecrawl scrape status {resp.status_code}")
        payload = resp.json().get("data", {}) or {}
        text = (payload.get("markdown") or payload.get("content") or "")[: max_bytes]
        meta = payload.get("metadata", {}) or {}
        final_url = meta.get("sourceURL") or meta.get("url") or url
        data = text.encode("utf-8")
        latency = int((time.monotonic() - start) * 1000)
        return FetchOutcome(
            text=text,
            final_url=final_url,
            content_type="text/html",
            byte_size=len(data),
            content_hash=hashlib.sha256(data).hexdigest(),
            provider=self.name,
            redirect_chain=[url, final_url],
            latency_ms=latency,
        )
