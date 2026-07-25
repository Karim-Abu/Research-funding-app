"""Hermetische Contract-Tests für die realen Provider-Adapter.

Kein Netz: ``httpx.post`` wird gemonkeypatcht (die Adapter importieren httpx
lazy in ``generate``). Prüft, dass ein schema-tragender ``ProviderRequest``
die korrekten provider-nativen Structured-Output-Request-Felder erzeugt
(OpenAI Responses / Anthropic Messages) und keine Sampling-Parameter erfindet.
"""
from __future__ import annotations

import json

import pytest

from app.agents.providers.anthropic import (
    NATIVE_STRUCTURED_OUTPUT,
    AnthropicProvider,
)
from app.agents.providers.base import ProviderError, ProviderRequest
from app.agents.providers.json_schema import unsupported_keywords_in
from app.agents.providers.openai import OpenAIProvider, _strict_schema
from app.agents.schemas import json_schema_for
from app.config.settings import get_settings

SCHEMA_ID = "PortalFieldDraftBundle@v1"


class _Resp:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload


def _capture_post(monkeypatch, payload: dict, status_code: int = 200) -> dict:
    """httpx.post ersetzen; gibt das dict zurück, in dem der Request landet."""
    captured: dict = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, body=json, timeout=timeout)
        return _Resp(payload, status_code)

    monkeypatch.setattr("httpx.post", fake_post)
    return captured


def _request(
    schema: dict | None, *, schema_id: str = SCHEMA_ID, mode: str | None = None
) -> ProviderRequest:
    return ProviderRequest(
        model_id="test-model",
        prompt="hermetic prompt",
        output_schema_id=schema_id,
        timeout_seconds=5,
        output_json_schema=schema,
        structured_output_mode=mode,
    )


@pytest.fixture
def openai_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "openai_api_key", "hermetic-test-key")


@pytest.fixture
def anthropic_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "hermetic-test-key")


_OPENAI_RESP = {
    "status": "completed",
    "model": "actual-openai-model",
    "output": [{
        "type": "message",
        "content": [{"type": "output_text", "text": "{}"}],
    }],
    "usage": {"input_tokens": 3, "output_tokens": 4},
}


# --- _strict_schema ----------------------------------------------------------


def _walk_objects(node):
    if isinstance(node, dict):
        if "properties" in node:
            yield node
        for value in node.values():
            yield from _walk_objects(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_objects(item)


def test_strict_schema_transforms_bundle_schema():
    strict = _strict_schema(json_schema_for(SCHEMA_ID))
    objects = list(_walk_objects(strict))
    assert objects, "kein Objekt-Schema gefunden"
    for obj in objects:
        # strict-Modus: alles required, keine Zusatz-Keys, kein default-Keyword
        assert obj["additionalProperties"] is False
        assert sorted(obj["required"]) == sorted(obj["properties"].keys())
    assert '"default"' not in json.dumps(strict)
    # Optionale Felder bleiben als anyOf[...,null] ausdrückbar (pydantic-kompatibel).
    candidate = strict["$defs"]["DraftCandidateRecord"]
    assert "rationale" in candidate["required"]
    assert {"type": "null"} in candidate["properties"]["rationale"]["anyOf"]


# --- OpenAI ------------------------------------------------------------------


def test_openai_structured_output_request(openai_key, monkeypatch):
    captured = _capture_post(monkeypatch, _OPENAI_RESP)
    request = _request(json_schema_for(SCHEMA_ID))
    request = ProviderRequest(**{**request.__dict__, "reasoning_effort": "low"})
    result = OpenAIProvider().generate(request)
    body = captured["body"]
    rf = body["text"]["format"]
    assert rf["type"] == "json_schema"
    assert rf["strict"] is True
    assert rf["name"] == "PortalFieldDraftBundle_v1"  # sanitisiert
    assert rf["schema"]["additionalProperties"] is False
    assert body["max_output_tokens"] == 4096
    assert body["store"] is False
    assert body["reasoning"] == {"effort": "low"}
    assert "temperature" not in body and "top_p" not in body
    assert captured["url"].endswith("/v1/responses")
    assert result.usage.input_tokens == 3 and result.usage.output_tokens == 4
    assert result.model == "actual-openai-model"


def test_openai_without_schema_keeps_legacy_wire_format(openai_key, monkeypatch):
    captured = _capture_post(monkeypatch, _OPENAI_RESP)
    OpenAIProvider().generate(_request(None))
    assert "text" not in captured["body"]
    assert "reasoning" not in captured["body"]
    assert captured["body"]["max_output_tokens"] == 1024


def test_openai_captures_provider_reported_cached_input(openai_key, monkeypatch):
    payload = {
        **_OPENAI_RESP,
        "usage": {
            "input_tokens": 100,
            "output_tokens": 4,
            "input_tokens_details": {"cached_tokens": 25},
        },
    }
    _capture_post(monkeypatch, payload)
    result = OpenAIProvider().generate(_request(None))
    assert result.usage.input_tokens == 100
    assert result.usage.cached_input_tokens == 25
    assert result.usage.cache_write_input_tokens == 0


# --- Anthropic ---------------------------------------------------------------


def test_anthropic_structured_output_request_and_parsing(anthropic_key, monkeypatch):
    # Live-verifizierter Contract (R5.5-REAL + Diagnose 2026-07-16): forced
    # tool use; das frühere output_config wurde von der API mit 4xx abgelehnt.
    bundle_input = {"draft_candidates": [], "placeholders": []}
    captured = _capture_post(
        monkeypatch,
        {
            "model": "actual-anthropic-model",
            "stop_reason": "tool_use",
            "content": [{
                "type": "tool_use", "name": "emit_structured_output",
                "input": bundle_input,
            }],
            "usage": {"input_tokens": 5, "output_tokens": 6},
        },
    )
    schema = json_schema_for(SCHEMA_ID)
    request = _request(schema)
    request = ProviderRequest(**{**request.__dict__, "reasoning_effort": "medium"})
    result = AnthropicProvider().generate(request)
    body = captured["body"]
    assert body["tools"][0]["name"] == "emit_structured_output"
    assert body["tools"][0]["input_schema"] == schema
    assert body["tool_choice"] == {"type": "tool", "name": "emit_structured_output"}
    # effort/output_config werden für Anthropic bewusst NICHT gesendet.
    assert "output_config" not in body
    assert "effort" not in body
    assert "temperature" not in body and "top_p" not in body
    assert body["max_tokens"] == 4096
    assert json.loads(result.raw_output) == bundle_input
    assert result.usage.input_tokens == 5 and result.usage.output_tokens == 6
    assert result.model == "actual-anthropic-model"
    assert result.termination_reason == "tool_use"
    assert result.tool_wrapper_normalized is False


def test_anthropic_captures_cache_read_and_write_tokens(anthropic_key, monkeypatch):
    _capture_post(monkeypatch, {
        "model": "actual-anthropic-model",
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "{}"}],
        "usage": {
            "input_tokens": 10,
            "cache_read_input_tokens": 20,
            "cache_creation_input_tokens": 30,
            "output_tokens": 4,
        },
    })
    result = AnthropicProvider().generate(_request(None))
    assert result.usage.input_tokens == 60
    assert result.usage.cached_input_tokens == 20
    assert result.usage.cache_write_input_tokens == 30


# --- Anthropic: native Structured Outputs (output_config.format) -------------

_PILOT_SCHEMA_IDS = ("PortalSectionDraftBundle@v1", "ReviewFindingBundle@v1")


@pytest.mark.parametrize("schema_id", _PILOT_SCHEMA_IDS)
def test_pilot_schemas_carry_no_unsupported_structured_output_keywords(schema_id):
    """Guard: die Kalibrierungs-Schemata müssen provider-tauglich sein.

    Structured Outputs lehnen Keywords wie minLength/maxItems ab — ein 4xx wäre
    dann selbstverschuldet. Das fällt hier auf, nicht erst im Live-Lauf.
    """
    strict = _strict_schema(json_schema_for(schema_id))
    assert unsupported_keywords_in(strict) == set()


@pytest.mark.parametrize("schema_id", _PILOT_SCHEMA_IDS)
def test_anthropic_native_structured_output_request(
    anthropic_key, monkeypatch, schema_id
):
    """Dokumentierte GA-Struktur: output_config.format/json_schema, kein Tool,
    kein Envelope, Antwort direkt aus dem JSON-Textblock."""
    payload_text = '{"findings": []}'
    captured = _capture_post(monkeypatch, {
        "model": "actual-anthropic-model",
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": payload_text}],
        "usage": {"input_tokens": 7, "output_tokens": 8},
    })
    request = _request(
        json_schema_for(schema_id), schema_id=schema_id,
        mode=NATIVE_STRUCTURED_OUTPUT,
    )
    request = ProviderRequest(**{**request.__dict__, "reasoning_effort": "high"})
    result = AnthropicProvider().generate(request)
    body = captured["body"]
    fmt = body["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["schema"]["additionalProperties"] is False
    assert sorted(fmt["schema"]["required"]) == sorted(fmt["schema"]["properties"])
    # Kein Tool-Umweg, kein Prefill, keine erfundenen Sampling-Parameter.
    assert "tools" not in body and "tool_choice" not in body
    assert "effort" not in body and "thinking" not in body
    assert "temperature" not in body and "top_p" not in body
    assert body["messages"] == [{"role": "user", "content": "hermetic prompt"}]
    assert result.raw_output == payload_text
    assert result.model == "actual-anthropic-model"
    assert result.tool_wrapper_normalized is False


def test_anthropic_native_mode_never_unwraps_a_wrapper(anthropic_key, monkeypatch):
    """Im nativen Modus gibt es keine Envelope-Normalisierung: der Textblock
    ist die Antwort — auch wenn er wie ein Wrapper aussieht."""
    wrapped = '{"parameters": {"findings": []}}'
    _capture_post(monkeypatch, {
        "model": "actual-anthropic-model", "stop_reason": "end_turn",
        "content": [{"type": "text", "text": wrapped}],
        "usage": {"input_tokens": 1, "output_tokens": 2},
    })
    result = AnthropicProvider().generate(
        _request(json_schema_for(SCHEMA_ID), mode=NATIVE_STRUCTURED_OUTPUT)
    )
    assert result.raw_output == wrapped
    assert result.tool_wrapper_normalized is False


def test_anthropic_native_mode_4xx_carries_diagnosis(anthropic_key, monkeypatch):
    """Ein 4xx muss STOPP-fähig berichtet werden: HTTP-Status, Error-Type,
    Request-ID und die (gekürzte) Providermeldung."""
    class _RespWithHeaders(_Resp):
        headers = {"request-id": "req_abc123"}

    def fake_post(url, headers=None, json=None, timeout=None):
        return _RespWithHeaders({"error": {
            "type": "invalid_request_error",
            "message": "output_config.format.schema: unsupported keyword",
        }}, 400)

    monkeypatch.setattr("httpx.post", fake_post)
    with pytest.raises(ProviderError) as caught:
        AnthropicProvider().generate(
            _request(json_schema_for(SCHEMA_ID), mode=NATIVE_STRUCTURED_OUTPUT)
        )
    error = caught.value
    assert error.code == "provider_error" and error.retryable is False
    assert error.status_code == 400
    assert error.error_type == "invalid_request_error"
    assert "unsupported keyword" in error.provider_message
    assert error.request_id == "req_abc123"


def test_anthropic_default_mode_still_uses_forced_tool_use(anthropic_key, monkeypatch):
    """Ohne Route-Capability bleibt der Produktionspfad unverändert."""
    captured = _capture_post(
        monkeypatch, _anthropic_tool_use_resp({"draft_candidates": []})
    )
    AnthropicProvider().generate(_request(json_schema_for(SCHEMA_ID)))
    assert captured["body"]["tools"][0]["name"] == "emit_structured_output"
    assert "output_config" not in captured["body"]


def _anthropic_tool_use_resp(tool_input):
    return {
        "model": "actual-anthropic-model",
        "stop_reason": "tool_use",
        "content": [{
            "type": "tool_use", "name": "emit_structured_output",
            "input": tool_input,
        }],
        "usage": {"input_tokens": 5, "output_tokens": 6},
    }


def test_anthropic_known_parameters_wrapper_is_normalized(anthropic_key, monkeypatch):
    """Bekannter Envelope {"parameters": {...}} wird ENG entpackt und als
    sichere Metadate markiert; die Schema-Autorität bleibt beim Gateway."""
    inner = {"draft_candidates": [], "placeholders": []}
    _capture_post(monkeypatch, _anthropic_tool_use_resp({"parameters": inner}))
    result = AnthropicProvider().generate(_request(json_schema_for(SCHEMA_ID)))
    assert json.loads(result.raw_output) == inner
    assert result.tool_wrapper_normalized is True


def test_anthropic_unknown_wrapper_is_not_unwrapped(anthropic_key, monkeypatch):
    """Unbekannte Wrapper (anderer Key / zusätzliche Keys) bleiben unangetastet
    — kein rekursives oder Best-effort-Unwrapping."""
    for wrapped in (
        {"payload": {"draft_candidates": []}},
        {"parameters": {"draft_candidates": []}, "extra": 1},
        {"parameters": "kein dict"},
    ):
        _capture_post(monkeypatch, _anthropic_tool_use_resp(wrapped))
        result = AnthropicProvider().generate(_request(json_schema_for(SCHEMA_ID)))
        assert json.loads(result.raw_output) == wrapped
        assert result.tool_wrapper_normalized is False


def test_anthropic_wrapper_with_invalid_inner_schema_fails_at_gateway(
    anthropic_key, monkeypatch
):
    """Normalisierter Wrapper mit ungültigem Inhalt: der Adapter liefert das
    innere Objekt, die pydantic-Validierung lehnt es ab (einzige Autorität)."""
    from app.agents.schemas import ValidationError, validate_payload

    _capture_post(
        monkeypatch,
        _anthropic_tool_use_resp({"parameters": {"voellig": "falsch"}}),
    )
    result = AnthropicProvider().generate(_request(json_schema_for(SCHEMA_ID)))
    assert result.tool_wrapper_normalized is True
    with pytest.raises(ValidationError):
        validate_payload(SCHEMA_ID, json.loads(result.raw_output))


def test_anthropic_text_fallback_without_tool_use(anthropic_key, monkeypatch):
    _capture_post(
        monkeypatch,
        {
            "content": [{"type": "text", "text": '{"a": 1}'}],
            "usage": {"input_tokens": 1, "output_tokens": 2},
        },
    )
    result = AnthropicProvider().generate(_request(json_schema_for(SCHEMA_ID)))
    assert result.raw_output == '{"a": 1}'


def test_anthropic_without_schema_keeps_legacy_wire_format(anthropic_key, monkeypatch):
    captured = _capture_post(
        monkeypatch,
        {"content": [{"type": "text", "text": "ok"}], "usage": {}},
    )
    AnthropicProvider().generate(_request(None))
    assert "tools" not in captured["body"]
    assert "tool_choice" not in captured["body"]
    # PRÄZ#5: ohne Schema bleibt das alte 1024er-Limit — kein pauschales Verteuern.
    assert captured["body"]["max_tokens"] == 1024


@pytest.mark.parametrize(
    ("status", "payload", "code"),
    [
        (401, {"error": {}}, "auth_failed"),
        (404, {"error": {}}, "model_unavailable"),
        (429, {"error": {"code": "insufficient_quota"}}, "quota_exceeded"),
        (429, {"error": {}}, "rate_limited"),
        (504, {"error": {}}, "timeout"),
        (503, {"error": {}}, "provider_outage"),
    ],
)
def test_openai_safe_error_classification(openai_key, monkeypatch, status, payload, code):
    _capture_post(monkeypatch, payload, status)
    with pytest.raises(ProviderError) as caught:
        OpenAIProvider().generate(_request(json_schema_for(SCHEMA_ID)))
    assert caught.value.code == code


def test_openai_refusal_before_schema_validation(openai_key, monkeypatch):
    _capture_post(monkeypatch, {
        "status": "completed",
        "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "safe"}]}],
        "usage": {},
    })
    with pytest.raises(ProviderError) as caught:
        OpenAIProvider().generate(_request(json_schema_for(SCHEMA_ID)))
    assert caught.value.code == "refusal"


def test_openai_missing_structured_output_is_retryable_schema_error(
    openai_key, monkeypatch
):
    _capture_post(monkeypatch, {
        "status": "completed", "model": "actual-openai-model",
        "output": [], "usage": {},
    })
    with pytest.raises(ProviderError) as caught:
        OpenAIProvider().generate(_request(json_schema_for(SCHEMA_ID)))
    assert caught.value.code == "schema_invalid"
    assert caught.value.retryable is True


def test_anthropic_refusal_before_schema_validation(anthropic_key, monkeypatch):
    _capture_post(monkeypatch, {"stop_reason": "refusal", "content": [], "usage": {}})
    with pytest.raises(ProviderError) as caught:
        AnthropicProvider().generate(_request(json_schema_for(SCHEMA_ID)))
    assert caught.value.code == "refusal"


def test_anthropic_missing_structured_output_is_retryable_schema_error(
    anthropic_key, monkeypatch
):
    _capture_post(monkeypatch, {
        "model": "actual-anthropic-model", "stop_reason": "end_turn",
        "content": [], "usage": {},
    })
    with pytest.raises(ProviderError) as caught:
        AnthropicProvider().generate(_request(json_schema_for(SCHEMA_ID)))
    assert caught.value.code == "schema_invalid"
    assert caught.value.retryable is True


@pytest.mark.parametrize(
    ("status", "payload", "code"),
    [
        (401, {"error": {"type": "authentication_error"}}, "auth_failed"),
        (402, {"error": {"type": "billing_error"}}, "quota_exceeded"),
        (404, {"error": {"type": "not_found_error"}}, "model_unavailable"),
        (429, {"error": {"type": "rate_limit_error"}}, "rate_limited"),
        (504, {"error": {"type": "timeout_error"}}, "timeout"),
        (529, {"error": {"type": "overloaded_error"}}, "provider_outage"),
    ],
)
def test_anthropic_safe_error_classification(
    anthropic_key, monkeypatch, status, payload, code
):
    _capture_post(monkeypatch, payload, status)
    with pytest.raises(ProviderError) as caught:
        AnthropicProvider().generate(_request(json_schema_for(SCHEMA_ID)))
    assert caught.value.code == code
