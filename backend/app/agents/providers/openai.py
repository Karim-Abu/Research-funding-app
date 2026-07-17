"""Policy-gated OpenAI Responses adapter (Milestone 9A).

Uses the already-pinned ``httpx`` (no SDK dependency, no import at startup). Key
from backend env only; missing key ⇒ route unavailable. Used only by the
env-gated smoke test. No tool delegation, no request/response logging.

When the request carries an ``output_json_schema``, the Responses adapter asks
for strict Structured Outputs (``text.format: json_schema``) so the model must
emit schema-shaped JSON (no markdown, no prose). Die Schema-Form liefert
``providers.json_schema.strict_schema`` (geteilt mit dem Anthropic-Pfad). This
is transport-level hardening only — the gateway's pydantic validation stays the
sole authority over what is accepted.
"""
from __future__ import annotations

import re

from app.agents.providers.base import (
    ProviderError,
    ProviderRequest,
    ProviderResult,
    ProviderTimeout,
    ProviderUsage,
)
from app.agents.providers.json_schema import strict_schema as _strict_schema
from app.config.settings import get_settings

_API_URL = "https://api.openai.com/v1/responses"
# R5.5b: the structured-output path needs more room — gpt-5.x counts reasoning
# tokens against the output budget and the R5.5-REAL run showed cap
# truncation of the JSON. This higher default applies ONLY when a schema is
# requested (structured output); plain-text calls keep the original 1024 so we
# never raise the ceiling — and the possible cost — of every call pauschal.
_STRUCTURED_MAX_TOKENS = 4096
_LEGACY_MAX_TOKENS = 1024


def _response_format(request: ProviderRequest) -> dict:
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", request.output_schema_id)
    return {
        "type": "json_schema",
        "name": name,
        "strict": True,
        "schema": _strict_schema(request.output_json_schema or {}),
    }


def _error_for(resp) -> ProviderError:
    status = int(getattr(resp, "status_code", 0) or 0)
    try:
        body = resp.json() or {}
    except Exception:  # noqa: BLE001 - never expose malformed/raw bodies
        body = {}
    error = body.get("error") or {}
    provider_code = str(error.get("code") or "")
    provider_type = str(error.get("type") or "")
    if status in (408, 504):
        code = "timeout"
    elif status in (401, 403):
        code = "auth_failed"
    elif status == 404 or provider_code in {"model_not_found", "invalid_model"}:
        code = "model_unavailable"
    elif status == 429 and (
        provider_code in {"insufficient_quota", "billing_hard_limit_reached"}
        or provider_type == "insufficient_quota"
    ):
        code = "quota_exceeded"
    elif status == 429:
        code = "rate_limited"
    elif status >= 500:
        code = "provider_outage"
    else:
        code = "provider_error"
    headers = getattr(resp, "headers", None) or {}
    try:
        retry_after = float(headers.get("retry-after"))
    except (TypeError, ValueError):
        retry_after = None
    return ProviderError(
        f"openai {code}", code=code,
        retryable=code in {"rate_limited", "provider_outage", "timeout"},
        retry_after_seconds=retry_after,
        request_id=headers.get("x-request-id"),
        status_code=status or None,
        error_type=provider_type or provider_code or None,
        provider_message=error.get("message"),
    )


def _response_text(body: dict) -> str:
    parts: list[str] = []
    for item in body.get("output", []) or []:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []) or []:
            if content.get("type") == "refusal":
                raise ProviderError(
                    "openai refusal", code="refusal", termination_reason="refusal"
                )
            if content.get("type") == "output_text":
                parts.append(str(content.get("text") or ""))
    return "".join(parts)


class OpenAIProvider:
    name = "openai_direct"

    def available(self) -> bool:
        return bool(get_settings().openai_api_key)

    def generate(self, request: ProviderRequest) -> ProviderResult:
        key = get_settings().openai_api_key
        if not key:
            raise ProviderError("openai route unavailable: no API key")
        import httpx  # lazy — never imported at startup / in mandatory tests

        structured = request.output_json_schema is not None
        default_max = _STRUCTURED_MAX_TOKENS if structured else _LEGACY_MAX_TOKENS
        payload: dict = {
            "model": request.model_id,
            "max_output_tokens": request.max_output_tokens or default_max,
            "input": [{"role": "user", "content": request.prompt}],
            "store": False,
        }
        if structured:
            payload["text"] = {"format": _response_format(request)}
        if request.reasoning_effort:
            payload["reasoning"] = {"effort": request.reasoning_effort}
        try:
            resp = httpx.post(
                _API_URL,
                headers={
                    "authorization": f"Bearer {key}",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=request.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeout("openai timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                "openai request failed", code="provider_outage", retryable=True
            ) from exc
        if resp.status_code >= 400:
            raise _error_for(resp)
        body = resp.json()
        if body.get("status") == "failed":
            raise ProviderError(
                "openai response failed", code="provider_error",
                termination_reason=str((body.get("error") or {}).get("code") or "failed"),
            )
        text = _response_text(body)
        if structured and not text:
            raise ProviderError(
                "openai structured output missing", code="schema_invalid",
                retryable=True,
                termination_reason=str(
                    (body.get("incomplete_details") or {}).get("reason")
                    or "schema_invalid"
                ),
            )
        usage = body.get("usage", {})
        return ProviderResult(
            raw_output=text,
            usage=ProviderUsage(
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
                reasoning_tokens=int(
                    (usage.get("output_tokens_details") or {}).get(
                        "reasoning_tokens", 0
                    )
                ),
            ),
            # Vom Provider gemeldetes Modell (Alias-Auflösung) — Ebene E.
            model=body.get("model"),
            termination_reason=(
                str((body.get("incomplete_details") or {}).get("reason"))
                if body.get("status") == "incomplete"
                else "stop"
            ),
            request_id=(getattr(resp, "headers", None) or {}).get("x-request-id"),
        )
