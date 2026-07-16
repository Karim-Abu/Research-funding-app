"""Hermetische Contract-Tests für die realen Provider-Adapter.

Kein Netz: ``httpx.post`` wird gemonkeypatcht (die Adapter importieren httpx
lazy in ``generate``). Prüft, dass ein schema-tragender ``ProviderRequest``
die korrekten provider-nativen Structured-Output-Request-Felder erzeugt
(OpenAI Responses / Anthropic Messages) und keine Sampling-Parameter erfindet.
"""
from __future__ import annotations

import json

import pytest

from app.agents.providers.anthropic import AnthropicProvider
from app.agents.providers.base import ProviderError, ProviderRequest
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


def _request(schema: dict | None) -> ProviderRequest:
    return ProviderRequest(
        model_id="test-model",
        prompt="hermetic prompt",
        output_schema_id=SCHEMA_ID,
        timeout_seconds=5,
        output_json_schema=schema,
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


# --- Anthropic ---------------------------------------------------------------


def test_anthropic_structured_output_request_and_parsing(anthropic_key, monkeypatch):
    bundle_input = {"draft_candidates": [], "placeholders": []}
    captured = _capture_post(
        monkeypatch,
        {
            "model": "actual-anthropic-model",
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": json.dumps(bundle_input)}],
            "usage": {"input_tokens": 5, "output_tokens": 6},
        },
    )
    schema = json_schema_for(SCHEMA_ID)
    request = _request(schema)
    request = ProviderRequest(**{**request.__dict__, "reasoning_effort": "medium"})
    result = AnthropicProvider().generate(request)
    body = captured["body"]
    assert body["output_config"]["format"] == {
        "type": "json_schema", "schema": schema,
    }
    assert body["output_config"]["effort"] == "medium"
    assert "tools" not in body and "tool_choice" not in body
    assert "temperature" not in body and "top_p" not in body
    assert body["max_tokens"] == 4096
    assert json.loads(result.raw_output) == bundle_input
    assert result.usage.input_tokens == 5 and result.usage.output_tokens == 6
    assert result.model == "actual-anthropic-model"


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
