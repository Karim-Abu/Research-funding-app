"""Firecrawl v2 provider for public-safe research.

Search only returns candidate metadata. Full markdown is fetched through ``fetch``
after a user explicitly imports a candidate. API keys and page contents are never
logged by this adapter.
"""
from __future__ import annotations

import hashlib
import time
from urllib.parse import urlparse

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

_BASE_URL = "https://api.firecrawl.dev/v2"


class FirecrawlProvider:
    name = "firecrawl"

    def __init__(
        self, *, api_key: str | None, timeout_seconds: int,
        privacy_mode: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._privacy_mode = privacy_mode if privacy_mode in ("anon", "zdr") else None

    def available(self) -> bool:
        return bool(self._api_key)

    def _client(self):
        if not self._api_key:
            raise ProviderUnavailable("firecrawl api key not configured")
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover
            raise ProviderUnavailable("httpx not available") from exc
        return httpx.Client(
            base_url=_BASE_URL,
            timeout=self._timeout,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )

    def _transport_error(self, exc: Exception, operation: str) -> Exception:
        """Map a transport failure to the narrowest honest error.

        Every transport variant used to collapse into ``ProviderTimeout``, so a
        refused connection was reported as «Zeitlimit überschritten» — a claim
        the data contradicted (the failing calls returned after 0.4 s). Only a
        real httpx timeout keeps that code; anything else is a transport error
        and carries its exception class name. The class name is safe: it holds
        no URL, no key and no page content.
        """
        try:
            import httpx
        except ImportError:  # pragma: no cover - httpx is a hard dependency
            return ProviderError(f"firecrawl {operation} transport failure")
        if isinstance(exc, httpx.TimeoutException):
            return ProviderTimeout(
                f"firecrawl {operation} timeout after {self._timeout}s"
            )
        return ProviderError(
            f"firecrawl {operation} transport failure ({type(exc).__name__})"
        )

    @staticmethod
    def _raise_for_status(resp, operation: str) -> None:
        if resp.status_code == 402:
            raise CreditExceeded("firecrawl credit/budget limit")
        if resp.status_code >= 400:
            raise ProviderError(f"firecrawl {operation} status {resp.status_code}")

    @staticmethod
    def _payload(resp, operation: str) -> dict:
        try:
            payload = resp.json()
        except (TypeError, ValueError) as exc:
            raise ProviderError(f"firecrawl {operation} returned invalid json") from exc
        if not isinstance(payload, dict):
            raise ProviderError(f"firecrawl {operation} returned invalid payload")
        return payload

    def search(self, request: SearchRequest) -> SearchOutcome:  # pragma: no cover - network
        start = time.monotonic()
        body: dict = {
            "query": request.query,
            "limit": request.max_results,
            "sources": [{"type": "web"}],
            "ignoreInvalidURLs": True,
        }
        if request.preferred_domains:
            body["includeDomains"] = list(request.preferred_domains)
        if request.excluded_domains:
            body["excludeDomains"] = list(request.excluded_domains)
        if request.categories:
            body["categories"] = [{"type": value} for value in request.categories]
        if self._privacy_mode:
            body["privacy"] = self._privacy_mode
        try:
            with self._client() as client:
                resp = client.post("/search", json=body)
        except (ProviderUnavailable, CreditExceeded, ProviderError):
            raise
        except Exception as exc:  # noqa: BLE001 - httpx transport variants
            raise self._transport_error(exc, "search") from exc
        self._raise_for_status(resp, "search")
        payload = self._payload(resp, "search")
        data = payload.get("data") or {}
        if not isinstance(data, dict) or not isinstance(data.get("web", []), list):
            raise ProviderError("firecrawl search returned invalid data.web")

        candidates: list[SearchCandidate] = []
        for index, item in enumerate(data.get("web", [])):
            if not isinstance(item, dict) or not item.get("url"):
                continue
            candidates.append(SearchCandidate(
                url=item["url"],
                title=item.get("title") or item["url"],
                snippet=item.get("description"),
                rank=item.get("position") or index + 1,
                publisher=(
                    item.get("publisher") or item.get("siteName")
                    or urlparse(item["url"]).hostname
                ),
                published_at=(
                    item.get("publishedDate") or item.get("publishedTime")
                    or item.get("date")
                ),
                source_category=item.get("category"),
            ))
        return SearchOutcome(
            candidates=candidates,
            provider=self.name,
            latency_ms=int((time.monotonic() - start) * 1000),
            credits_used=payload.get("creditsUsed"),
            warnings=list(payload.get("warnings") or []),
        )

    def fetch(self, url: str, *, max_bytes: int) -> FetchOutcome:  # pragma: no cover - network
        start = time.monotonic()
        body: dict = {
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True,
            "storeInCache": False,
            "skipTlsVerification": False,
            "removeBase64Images": True,
        }
        if self._privacy_mode == "zdr":
            body["zeroDataRetention"] = True
        elif self._privacy_mode == "anon":
            body["privacy"] = "anon"
        try:
            with self._client() as client:
                resp = client.post("/scrape", json=body)
        except (ProviderUnavailable, CreditExceeded, ProviderError):
            raise
        except Exception as exc:  # noqa: BLE001 - httpx transport variants
            raise self._transport_error(exc, "scrape") from exc
        self._raise_for_status(resp, "scrape")
        response_payload = self._payload(resp, "scrape")
        payload = response_payload.get("data") or {}
        if not isinstance(payload, dict):
            raise ProviderError("firecrawl scrape returned invalid data")
        text = payload.get("markdown") or payload.get("content") or ""
        if not text.strip():
            raise ProviderError("firecrawl scrape returned no content")
        meta = payload.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        final_url = meta.get("sourceURL") or meta.get("url") or url
        data = text.encode("utf-8")
        if len(data) > max_bytes:
            raise ProviderError("firecrawl scrape content exceeds size limit")
        supplied_chain = meta.get("redirectChain")
        redirect_chain = (
            [str(value) for value in supplied_chain if value]
            if isinstance(supplied_chain, list) else [url]
        )
        chain_verified = bool(
            isinstance(supplied_chain, list)
            and redirect_chain
            and redirect_chain[0] == url
        )
        if chain_verified and redirect_chain[-1] != final_url:
            redirect_chain.append(final_url)
        return FetchOutcome(
            text=text,
            final_url=final_url,
            content_type=str(meta.get("contentType") or "text/html"),
            byte_size=len(data),
            content_hash=hashlib.sha256(data).hexdigest(),
            provider=self.name,
            redirect_chain=redirect_chain,
            redirect_chain_verified=chain_verified,
            latency_ms=int((time.monotonic() - start) * 1000),
            credits_used=response_payload.get("creditsUsed"),
            title=meta.get("title"),
            publisher=(
                meta.get("publisher") or meta.get("siteName")
                or urlparse(final_url).hostname
            ),
            published_at=(
                meta.get("publishedDate") or meta.get("publishedTime") or meta.get("date")
            ),
        )
