"""Deterministic fake provider behaviour (Milestone 9A)."""
from __future__ import annotations

import json
import socket

import pytest

from app.agents.providers import (
    FakeProvider,
    ProviderError,
    ProviderRequest,
    ProviderTimeout,
)

_REQ = ProviderRequest(
    model_id="x", prompt="p", output_schema_id="ProjectFactExtractionResult@v1",
    timeout_seconds=10,
)


def test_deterministic_success_default_output():
    fake = FakeProvider()
    a = fake.generate(_REQ).raw_output
    b = FakeProvider().generate(_REQ).raw_output
    assert a == b  # deterministic
    assert json.loads(a) == {"facts": [], "conflicts": [], "missing_information": []}


def test_payload_override():
    fake = FakeProvider(payload={"facts": [], "conflicts": [], "missing_information": []})
    assert "facts" in json.loads(fake.generate(_REQ).raw_output)


def test_malformed_json_mode():
    out = FakeProvider(mode="malformed_json").generate(_REQ).raw_output
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)


def test_timeout_mode():
    with pytest.raises(ProviderTimeout):
        FakeProvider(mode="timeout").generate(_REQ)


def test_error_mode():
    with pytest.raises(ProviderError):
        FakeProvider(mode="error").generate(_REQ)


def test_usage_simulation():
    from app.agents.providers.base import ProviderUsage

    fake = FakeProvider(usage=ProviderUsage(input_tokens=123, output_tokens=45))
    result = fake.generate(_REQ)
    assert result.usage.input_tokens == 123 and result.usage.output_tokens == 45


def test_no_network(monkeypatch):
    def _blocked(*_a, **_k):
        raise AssertionError("fake provider attempted network access")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    assert FakeProvider().generate(_REQ).raw_output  # succeeds with sockets blocked
