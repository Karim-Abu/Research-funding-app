"""Policy-gated Anthropic Messages adapter (Milestone 9A).

Uses the already-pinned ``httpx`` (no SDK dependency, no import at startup). The
key is read only from the backend environment; a missing key marks the route
unavailable (never a startup break). Used only by the env-gated smoke test —
never by mandatory tests. No tool delegation, no request/response logging.

When the request carries an ``output_json_schema``, the Messages adapter has two
schema surfaces:

* Default (Produktion): forced tool use über ein einzelnes Output-Tool
  (``emit_structured_output``); der tool_use-Input wird als JSON-Text
  zurückgegeben — der live in R5.5-REAL bewährte Mechanismus.
* ``structured_output_mode="native_json_schema"`` (per Route-Capability, aktuell
  nur im Evaluations-Pilotpfad): die dokumentierte native Structured-Output-
  Oberfläche ``output_config.format`` mit ``type: json_schema``. Kein Tool, kein
  Envelope, keine Wrapper-Normalisierung — die Antwort wird ausschliesslich aus
  dem strukturierten JSON-Textblock gelesen. Der frühere 4xx dieses Pfades
  (Diagnose 2026-07-16) entstand mit der überholten Feldform; die GA-Struktur
  verlangt zusätzlich ``additionalProperties: false`` + vollständige
  ``required``-Listen (siehe ``json_schema.strict_schema``).

``reasoning_effort`` wird für Anthropic bewusst NICHT übertragen (unsupported
knobs are never added; das Verhalten bleibt der adaptive Modell-Default). The
gateway's pydantic validation stays the sole authority over what is accepted.
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
from app.agents.providers.json_schema import strict_schema
from app.config.settings import get_settings

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_OUTPUT_TOOL = "emit_structured_output"
NATIVE_STRUCTURED_OUTPUT = "native_json_schema"
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
        native = request.structured_output_mode == NATIVE_STRUCTURED_OUTPUT
        default_max = _STRUCTURED_MAX_TOKENS if structured else _LEGACY_MAX_TOKENS
        payload: dict = {
            "model": request.model_id,
            "max_tokens": request.max_output_tokens or default_max,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if structured and native:
            # Dokumentierte GA-Struktur: output_config.format/json_schema.
            payload["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": strict_schema(request.output_json_schema),
                }
            }
        elif structured:
            payload["tools"] = [{
                "name": _OUTPUT_TOOL,
                "description": (
                    "Return the final structured output for schema "
                    f"{request.output_schema_id}. This is an output "
                    "container, not an action."
                ),
                "input_schema": request.output_json_schema,
            }]
            payload["tool_choice"] = {"type": "tool", "name": _OUTPUT_TOOL}
        # request.reasoning_effort wird hier bewusst ignoriert (siehe Docstring).
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
            headers = getattr(resp, "headers", None) or {}
            try:
                retry_after = float(headers.get("retry-after"))
            except (TypeError, ValueError):
                retry_after = None
            raise ProviderError(
                f"anthropic {code}", code=code,
                retryable=code in {"rate_limited", "provider_outage", "timeout"},
                retry_after_seconds=retry_after,
                request_id=headers.get("request-id"),
                status_code=status,
                error_type=provider_type or None,
                provider_message=error.get("message"),
            )
        body = resp.json()
        stop_reason = str(body.get("stop_reason") or "stop")
        if stop_reason == "refusal":
            raise ProviderError(
                "anthropic refusal", code="refusal", termination_reason="refusal"
            )
        def _text_blocks() -> str:
            return "".join(
                block.get("text", "")
                for block in body.get("content", [])
                if block.get("type") == "text"
            )

        if native:
            # Native Structured Outputs: die Antwort IST der JSON-Textblock —
            # kein Tool, kein Envelope, keine Normalisierung.
            text = _text_blocks()
            if structured and not text:
                raise ProviderError(
                    "anthropic structured output missing", code="schema_invalid",
                    retryable=True, termination_reason=stop_reason,
                )
            usage = body.get("usage", {})
            return ProviderResult(
                raw_output=text,
                usage=ProviderUsage(
                    input_tokens=int(usage.get("input_tokens", 0)),
                    output_tokens=int(usage.get("output_tokens", 0)),
                ),
                model=body.get("model"),
                termination_reason=stop_reason,
                request_id=(getattr(resp, "headers", None) or {}).get("request-id"),
            )

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
        # Enge Envelope-Normalisierung (Live-Befund 2026-07-16): manche
        # Modelle liefern den Tool-Input exakt als {"parameters": {...}}.
        # NUR dieser bekannte Wrapper wird entpackt (genau 1 Key, dict-Wert);
        # die inhaltliche Validierung bleibt allein beim Gateway (pydantic).
        # Kein rekursives Unwrapping, keine Best-effort-Reparatur — andere
        # Wrapper bleiben unverändert und scheitern dort ehrlich.
        tool_wrapper_normalized = False
        if (
            isinstance(tool_input, dict)
            and set(tool_input.keys()) == {"parameters"}
            and isinstance(tool_input["parameters"], dict)
        ):
            tool_input = tool_input["parameters"]
            tool_wrapper_normalized = True
        if tool_input is not None:
            text = json.dumps(tool_input, ensure_ascii=False)
        else:
            text = _text_blocks()
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
            request_id=(getattr(resp, "headers", None) or {}).get("request-id"),
            tool_wrapper_normalized=tool_wrapper_normalized,
        )
