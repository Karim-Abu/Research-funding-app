"""Dormant Anthropic adapter (Milestone 9A).

Uses the already-pinned ``httpx`` (no SDK dependency, no import at startup). The
key is read only from the backend environment; a missing key marks the route
unavailable (never a startup break). Used only by the env-gated smoke test —
never by mandatory tests. No tool delegation, no request/response logging.
"""
from __future__ import annotations

from app.agents.providers.base import (
    ProviderError,
    ProviderRequest,
    ProviderResult,
    ProviderTimeout,
    ProviderUsage,
)
from app.config.settings import get_settings

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"


class AnthropicProvider:
    name = "anthropic_direct"

    def available(self) -> bool:
        return bool(get_settings().anthropic_api_key)

    def generate(self, request: ProviderRequest) -> ProviderResult:
        key = get_settings().anthropic_api_key
        if not key:
            raise ProviderError("anthropic route unavailable: no API key")
        import httpx  # lazy — never imported at startup / in mandatory tests

        try:
            resp = httpx.post(
                _API_URL,
                headers={
                    "x-api-key": key,
                    "anthropic-version": _API_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": request.model_id,
                    "max_tokens": request.max_output_tokens or 1024,
                    "messages": [{"role": "user", "content": request.prompt}],
                },
                timeout=request.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeout("anthropic timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("anthropic request failed") from exc
        if resp.status_code >= 400:
            raise ProviderError(f"anthropic http {resp.status_code}")
        body = resp.json()
        text = "".join(
            block.get("text", "")
            for block in body.get("content", [])
            if block.get("type") == "text"
        )
        usage = body.get("usage", {})
        return ProviderResult(
            raw_output=text,
            usage=ProviderUsage(
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
            ),
        )
