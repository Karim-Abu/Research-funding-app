"""Dormant Anthropic adapter (Milestone 9A).

Uses the already-pinned ``httpx`` (no SDK dependency, no import at startup). The
key is read only from the backend environment; a missing key marks the route
unavailable (never a startup break). Used only by the env-gated smoke test —
never by mandatory tests. No tool delegation, no request/response logging.

R5.5b: when the request carries an ``output_json_schema``, the adapter forces
tool use (``tool_choice: {"type": "tool"}``) with the schema as the single
tool's ``input_schema`` — the model must answer with schema-shaped JSON instead
of prose. GA API, no beta header. The tool is an output container only (nothing
is executed); the gateway's pydantic validation stays the sole authority.
"""
from __future__ import annotations

import json

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
_OUTPUT_TOOL = "emit_structured_output"
# R5.5b: the structured-output path needs more room — the R5.5-REAL run hit the
# cap exactly (2×1024 output tokens ⇒ JSON truncated mid-stream). This higher
# default applies ONLY when a schema is requested (forced tool use); plain-text
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
            payload["tools"] = [
                {
                    "name": _OUTPUT_TOOL,
                    "description": (
                        "Return the final structured output for schema "
                        f"{request.output_schema_id}. This is an output "
                        "container, not an action."
                    ),
                    "input_schema": request.output_json_schema,
                }
            ]
            payload["tool_choice"] = {"type": "tool", "name": _OUTPUT_TOOL}
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
            raise ProviderError("anthropic request failed") from exc
        if resp.status_code >= 400:
            raise ProviderError(f"anthropic http {resp.status_code}")
        body = resp.json()
        # Forced tool use ⇒ the structured output is the tool_use block's input.
        # Serialize it back to JSON text: ProviderResult.raw_output stays "the
        # model's unparsed output" and the gateway keeps validating it.
        tool_input = next(
            (
                block.get("input")
                for block in body.get("content", [])
                if block.get("type") == "tool_use"
            ),
            None,
        )
        if tool_input is not None:
            text = json.dumps(tool_input, ensure_ascii=False)
        else:
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
            # Vom Provider gemeldetes Modell (Alias-Auflösung) — Ebene E.
            model=body.get("model"),
        )
