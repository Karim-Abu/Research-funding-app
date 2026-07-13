"""R5.5b — hermetische Unit-Tests für die realen Provider-Adapter.

Kein Netz: ``httpx.post`` wird gemonkeypatcht (die Adapter importieren httpx
lazy in ``generate``). Prüft, dass ein schema-tragender ``ProviderRequest``
die korrekten provider-nativen Structured-Output-Request-Felder erzeugt
(OpenAI ``response_format`` strict / Anthropic forced tool use) — und dass
Requests OHNE Schema exakt das bisherige Wire-Format behalten.
"""
from __future__ import annotations

import json

import pytest

from app.agents.providers.anthropic import AnthropicProvider
from app.agents.providers.base import ProviderRequest
from app.agents.providers.openai import OpenAIProvider, _strict_schema
from app.agents.schemas import json_schema_for
from app.config.settings import get_settings

SCHEMA_ID = "PortalFieldDraftBundle@v1"


class _Resp:
    status_code = 200

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def _capture_post(monkeypatch, payload: dict) -> dict:
    """httpx.post ersetzen; gibt das dict zurück, in dem der Request landet."""
    captured: dict = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, body=json, timeout=timeout)
        return _Resp(payload)

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
    "choices": [{"message": {"content": "{}"}}],
    "usage": {"prompt_tokens": 3, "completion_tokens": 4},
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
    result = OpenAIProvider().generate(_request(json_schema_for(SCHEMA_ID)))
    body = captured["body"]
    rf = body["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["strict"] is True
    assert rf["json_schema"]["name"] == "PortalFieldDraftBundle_v1"  # sanitisiert
    assert rf["json_schema"]["schema"]["additionalProperties"] is False
    assert body["max_completion_tokens"] == 4096  # R5.5b: Structured-Output-Pfad
    assert result.usage.input_tokens == 3 and result.usage.output_tokens == 4


def test_openai_without_schema_keeps_legacy_wire_format(openai_key, monkeypatch):
    captured = _capture_post(monkeypatch, _OPENAI_RESP)
    OpenAIProvider().generate(_request(None))
    assert "response_format" not in captured["body"]  # EVAL.2-Verhalten unverändert
    # PRÄZ#5: ohne Schema bleibt das alte 1024er-Limit — kein pauschales Verteuern.
    assert captured["body"]["max_completion_tokens"] == 1024


# --- Anthropic ---------------------------------------------------------------


def test_anthropic_forced_tool_use_request_and_parsing(anthropic_key, monkeypatch):
    bundle_input = {"draft_candidates": [], "placeholders": []}
    captured = _capture_post(
        monkeypatch,
        {
            "content": [
                {"type": "text", "text": "ignoriert — tool_use gewinnt"},
                {
                    "type": "tool_use",
                    "name": "emit_structured_output",
                    "input": bundle_input,
                },
            ],
            "usage": {"input_tokens": 5, "output_tokens": 6},
        },
    )
    schema = json_schema_for(SCHEMA_ID)
    result = AnthropicProvider().generate(_request(schema))
    body = captured["body"]
    assert body["tool_choice"] == {"type": "tool", "name": "emit_structured_output"}
    assert body["tools"][0]["name"] == "emit_structured_output"
    # input_schema unverändert (keine strict-Transformation nötig bei Anthropic)
    assert body["tools"][0]["input_schema"] == schema
    assert body["max_tokens"] == 4096  # R5.5b: Structured-Output-Pfad
    # tool_use-Input wird als JSON-Text zurückgegeben — Gateway validiert weiter.
    assert json.loads(result.raw_output) == bundle_input
    assert result.usage.input_tokens == 5 and result.usage.output_tokens == 6


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
