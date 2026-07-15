"""Dormant OpenAI adapter (Milestone 9A).

Uses the already-pinned ``httpx`` (no SDK dependency, no import at startup). Key
from backend env only; missing key ⇒ route unavailable. Used only by the
env-gated smoke test. No tool delegation, no request/response logging.

R5.5b: when the request carries an ``output_json_schema``, the adapter asks the
API for strict Structured Outputs (``response_format: json_schema``) so the
model must emit schema-shaped JSON (no markdown, no prose). This is transport-
level hardening only — the gateway's pydantic validation stays the sole
authority over what is accepted.
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
from app.config.settings import get_settings

_API_URL = "https://api.openai.com/v1/chat/completions"
# R5.5b: the structured-output path needs more room — gpt-5.x counts reasoning
# tokens against max_completion_tokens and the R5.5-REAL run showed cap
# truncation of the JSON. This higher default applies ONLY when a schema is
# requested (structured output); plain-text calls keep the original 1024 so we
# never raise the ceiling — and the possible cost — of every call pauschal.
_STRUCTURED_MAX_TOKENS = 4096
_LEGACY_MAX_TOKENS = 1024


def _strict_schema(schema: dict) -> dict:
    """Pydantic JSON Schema → OpenAI strict Structured Outputs shape.

    Deterministic, lossless for our models (mirrors the OpenAI SDK's
    ``to_strict_json_schema``): every object gets ``additionalProperties:
    false`` and ALL properties required; the unsupported ``default`` keyword is
    stripped. Optional fields stay expressible because pydantic renders
    ``T | None`` as ``anyOf: [T, null]`` and list defaults are simply sent as
    ``[]`` — both remain valid for the gateway's pydantic validation.
    """

    def walk(node: object) -> object:
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node
        out: dict = {}
        for key, value in node.items():
            if key == "default":  # schema keyword, not supported by strict mode
                continue
            if key in ("properties", "$defs"):
                # keys here are property/definition NAMES, values are schemas
                out[key] = {name: walk(sub) for name, sub in value.items()}
            else:
                out[key] = walk(value)
        if "properties" in out:
            out["additionalProperties"] = False
            out["required"] = list(out["properties"].keys())
        return out

    return walk(schema)  # type: ignore[return-value]


def _response_format(request: ProviderRequest) -> dict:
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", request.output_schema_id)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": _strict_schema(request.output_json_schema or {}),
        },
    }


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
            # gpt-5.x verlangt max_completion_tokens; "max_tokens"
            # wird mit HTTP 400 abgelehnt (EVAL.2, Owner-Ok).
            "max_completion_tokens": request.max_output_tokens or default_max,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if structured:
            payload["response_format"] = _response_format(request)
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
            # Vom Provider gemeldetes Modell (Alias-Auflösung) — Ebene E.
            model=body.get("model"),
        )
