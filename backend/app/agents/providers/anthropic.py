"""Policy-gated Anthropic Messages adapter (Milestone 9A).

Uses the already-pinned ``httpx`` (no SDK dependency, no import at startup). The
key is read only from the backend environment; a missing key marks the route
unavailable (never a startup break). Used only by the env-gated smoke test —
never by mandatory tests. No tool delegation, no request/response logging.

When the request carries an ``output_json_schema``, the Messages adapter uses
``output_config.format: json_schema``. The gateway's pydantic validation stays
the sole authority over what is accepted.
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
# R5.5b: the structured-output path needs more room — the R5.5-REAL run hit the
# cap exactly (2×1024 output tokens ⇒ JSON truncated mid-stream). This higher
# default applies ONLY when a schema is requested; plain-text
# calls keep the original 1024 so we never raise the ceiling — and the possible
# cost — of every call pauschal.
_STRUCTURED_MAX_TOKENS = 4096
_LEGACY_MAX_TOKENS = 1024


class AnthropicProvider:
    name = "anthropic_direct"

    def available(self) -> bool:
        return bool(get_settings().anthropic_api_key)

    def generate(self, request: ProviderRequest) -> ProviderResult:
        key = get_settings().anthropic_api_key
        if not key:
            raise ProviderError("anthropic route unavailable: no API key")
        import httpx  # lazy — never imported at startup / in mandatory tests

        structured = request.output_json_schema is not None
        default_max = _STRUCTURED_MAX_TOKENS if structured else _LEGACY_MAX_TOKENS
        payload: dict = {
            "model": request.model_id,
            "max_tokens": request.max_output_tokens or default_max,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if structured:
            payload["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": request.output_json_schema,
                }
            }
        if request.reasoning_effort:
            payload.setdefault("output_config", {})["effort"] = request.reasoning_effort
        try:
            resp = httpx.post(
                _API_URL,
                headers={
                    "x-api-key": key,
                    "anthropic-version": _API_VERSION,
                    "content-type": "application/json",
                },
                json=payload,
                timeout=request.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeout("anthropic timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                "anthropic request failed", code="provider_outage", retryable=True
            ) from exc
        if resp.status_code >= 400:
            status = int(resp.status_code)
            try:
                error = (resp.json() or {}).get("error") or {}
            except Exception:  # noqa: BLE001 - never expose malformed bodies
                error = {}
            provider_type = str(error.get("type") or "")
            code = (
                "timeout" if status in (408, 504) or provider_type == "timeout_error"
                else "auth_failed" if status in (401, 403)
                else "quota_exceeded" if status == 402
                else "model_unavailable" if status == 404 or provider_type == "not_found_error"
                else "rate_limited" if status == 429
                else "provider_outage" if status >= 500 or provider_type == "overloaded_error"
                else "provider_error"
            )
            raise ProviderError(
                f"anthropic {code}", code=code,
                retryable=code in {"rate_limited", "provider_outage", "timeout"},
            )
        body = resp.json()
        stop_reason = str(body.get("stop_reason") or "stop")
        if stop_reason == "refusal":
            raise ProviderError(
                "anthropic refusal", code="refusal", termination_reason="refusal"
            )
        text = "".join(
            block.get("text", "")
            for block in body.get("content", [])
            if block.get("type") == "text"
        )
        if structured and not text:
            raise ProviderError(
                "anthropic structured output missing", code="schema_invalid",
                retryable=True,
                termination_reason=stop_reason,
            )
        usage = body.get("usage", {})
        return ProviderResult(
            raw_output=text,
            usage=ProviderUsage(
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
            ),
            # Vom Provider gemeldetes Modell (Alias-Auflösung) — Ebene E.
            model=body.get("model"),
            termination_reason=stop_reason,
        )
