"""Dormant OpenAI adapter (Milestone 9A).

Uses the already-pinned ``httpx`` (no SDK dependency, no import at startup). Key
from backend env only; missing key ⇒ route unavailable. Used only by the
env-gated smoke test. No tool delegation, no request/response logging.
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

_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider:
    name = "openai_direct"

    def available(self) -> bool:
        return bool(get_settings().openai_api_key)

    def generate(self, request: ProviderRequest) -> ProviderResult:
        key = get_settings().openai_api_key
        if not key:
            raise ProviderError("openai route unavailable: no API key")
        import httpx  # lazy — never imported at startup / in mandatory tests

        try:
            resp = httpx.post(
                _API_URL,
                headers={
                    "authorization": f"Bearer {key}",
                    "content-type": "application/json",
                },
                json={
                    "model": request.model_id,
                    # gpt-5.x verlangt max_completion_tokens; "max_tokens"
                    # wird mit HTTP 400 abgelehnt (EVAL.2, Owner-Ok).
                    "max_completion_tokens": request.max_output_tokens or 1024,
                    "messages": [{"role": "user", "content": request.prompt}],
                },
                timeout=request.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeout("openai timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("openai request failed") from exc
        if resp.status_code >= 400:
            raise ProviderError(f"openai http {resp.status_code}")
        body = resp.json()
        choices = body.get("choices", [])
        text = choices[0]["message"]["content"] if choices else ""
        usage = body.get("usage", {})
        return ProviderResult(
            raw_output=text,
            usage=ProviderUsage(
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
            ),
        )
