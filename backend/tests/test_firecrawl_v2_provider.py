from __future__ import annotations

import pytest

from app.config.settings import Settings
from app.evaluation.preflight import preflight_firecrawl
from app.provider_errors import classify_provider_failure
from app.research.providers.base import (
    ProviderError,
    SearchCandidate,
    SearchOutcome,
    SearchRequest,
)
from app.research.providers.firecrawl import FirecrawlProvider
from app.research.executor import _is_demo_url


class _Response:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class _Client:
    def __init__(self, responses: list[_Response]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def post(self, path: str, *, json: dict):
        self.calls.append((path, json))
        return self.responses.pop(0)


def test_v2_search_normalizes_web_metadata_and_never_scrapes(monkeypatch):
    client = _Client([_Response({
        "data": {"web": [{
            "url": "https://www.bfs.admin.ch/market",
            "title": "Swiss market statistics",
            "description": "Official market series and growth indicators.",
            "position": 2,
            "publisher": "Federal Statistical Office",
            "publishedDate": "2025-03-01T00:00:00Z",
            "category": "research",
        }]},
        "creditsUsed": 1.5,
    })])
    provider = FirecrawlProvider(api_key="test", timeout_seconds=5)
    monkeypatch.setattr(provider, "_client", lambda: client)

    outcome = provider.search(SearchRequest(
        query="Swiss industrial AI market growth",
        max_results=3,
        preferred_domains=("bfs.admin.ch",),
        excluded_domains=("blocked.example",),
        categories=("research",),
    ))

    assert client.calls == [("/search", {
        "query": "Swiss industrial AI market growth",
        "limit": 3,
        "sources": [{"type": "web"}],
        "ignoreInvalidURLs": True,
        "includeDomains": ["bfs.admin.ch"],
        "excludeDomains": ["blocked.example"],
        "categories": [{"type": "research"}],
    })]
    assert "scrapeOptions" not in client.calls[0][1]
    assert outcome.credits_used == 1.5
    assert outcome.candidates[0].publisher == "Federal Statistical Office"
    assert outcome.candidates[0].published_at == "2025-03-01T00:00:00Z"


def test_v2_search_uses_real_host_when_publisher_is_missing(monkeypatch):
    client = _Client([_Response({
        "data": {"web": [{
            "url": "https://www.bfs.admin.ch/market",
            "title": "Swiss market statistics",
        }]},
    })])
    provider = FirecrawlProvider(api_key="test", timeout_seconds=5)
    monkeypatch.setattr(provider, "_client", lambda: client)

    outcome = provider.search(SearchRequest(query="Swiss market", max_results=1))

    assert outcome.candidates[0].url == "https://www.bfs.admin.ch/market"
    assert outcome.candidates[0].title == "Swiss market statistics"
    assert outcome.candidates[0].publisher == "www.bfs.admin.ch"
    assert not _is_demo_url(outcome.candidates[0].url)


def test_v2_scrape_uses_privacy_cache_and_tls_guards(monkeypatch):
    client = _Client([_Response({
        "data": {
            "markdown": "# Public report\nConcrete public content.",
            "metadata": {
                "sourceURL": "https://www.bfs.admin.ch/report",
                "title": "Public report",
                "siteName": "BFS",
            },
        },
        "creditsUsed": 2,
    })])
    provider = FirecrawlProvider(
        api_key="test", timeout_seconds=5, privacy_mode="zdr"
    )
    monkeypatch.setattr(provider, "_client", lambda: client)

    fetched = provider.fetch("https://www.bfs.admin.ch/report", max_bytes=10_000)
    path, body = client.calls[0]
    assert path == "/scrape"
    assert body["onlyMainContent"] is True
    assert body["storeInCache"] is False
    assert body["skipTlsVerification"] is False
    assert body["removeBase64Images"] is True
    assert body["zeroDataRetention"] is True
    assert fetched.publisher == "BFS" and fetched.credits_used == 2


def test_configured_privacy_rejection_is_not_retried_without_privacy(monkeypatch):
    client = _Client([_Response({"error": "unsupported"}, status_code=400)])
    provider = FirecrawlProvider(
        api_key="test", timeout_seconds=5, privacy_mode="anon"
    )
    monkeypatch.setattr(provider, "_client", lambda: client)
    with pytest.raises(ProviderError):
        provider.search(SearchRequest(query="public market", max_results=1))
    assert len(client.calls) == 1
    assert client.calls[0][1]["privacy"] == "anon"


def test_reserved_demo_domains_are_recognized_for_live_mode():
    assert _is_demo_url("https://example.org/result")
    assert _is_demo_url("https://research.example.org/result")
    assert not _is_demo_url("https://www.bfs.admin.ch/result")


def test_live_preflight_rejects_example_org_without_demo_fallback():
    class _DemoLeak:
        def search(self, _request):
            return SearchOutcome(
                candidates=[
                    SearchCandidate(
                        url="https://research.example.org/result",
                        title="Reserved demo result",
                    )
                ],
                provider="firecrawl",
            )

    result = preflight_firecrawl(
        settings=Settings(
            web_research_enabled=True,
            web_research_fake_provider=False,
            firecrawl_api_key="fc-hermetic",
        ),
        provider=_DemoLeak(),
        execute_live=True,
    )
    assert result.status == "fail"
    assert result.error_class == "live_demo_domain_rejected"


def test_live_preflight_surfaces_provider_failure_without_demo_fallback():
    class _Outage:
        def search(self, _request):
            raise ProviderError("firecrawl search status 503")

    result = preflight_firecrawl(
        settings=Settings(
            web_research_enabled=True,
            web_research_fake_provider=False,
            firecrawl_api_key="fc-hermetic",
        ),
        provider=_Outage(),
        execute_live=True,
    )
    assert result.status == "fail"
    assert result.mode == "live"
    assert result.error_class == "provider_outage"


def test_firecrawl_429_retains_rate_limit_classification():
    response = type("Response", (), {"status_code": 429})()
    with pytest.raises(ProviderError) as caught:
        FirecrawlProvider._raise_for_status(response, "search")
    diagnosis = classify_provider_failure(
        str(caught.value), source_code=getattr(caught.value, "code", None)
    )
    assert (diagnosis.reason_code, diagnosis.retryable, diagnosis.http_status) == (
        "provider_rate_limited", True, 429,
    )
