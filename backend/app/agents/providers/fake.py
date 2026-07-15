"""Deterministic fake provider (Milestone 9A) — mandatory for all automated tests.

No network, no API key. Produces deterministic, schema-valid output and supports
malformed / timeout / provider-error / usage-simulation modes plus arbitrary
fixed payloads (for prompt-injection and reference-integrity fixtures).
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

# Minimal schema-valid default outputs (empty extractions — valid, no provenance
# or reference concerns). Profiles without a default fall back to "{}".
_DEFAULT_OUTPUTS: dict[str, dict] = {
    "ProjectFactExtractionResult@v1": {
        "facts": [],
        "conflicts": [],
        "missing_information": [],
    },
}


class FakeProvider:
    """name=``fake``; deterministic. ``mode`` ∈ success | malformed | malformed_json
    | timeout | error. ``payload`` overrides the success output."""

    name = "fake"

    def __init__(
        self,
        *,
        mode: str = "success",
        payload: dict | None = None,
        raw_output: str | None = None,
        usage: ProviderUsage | None = None,
    ) -> None:
        self.mode = mode
        self._payload = payload
        self._raw_output = raw_output
        self._usage = usage or ProviderUsage(input_tokens=10, output_tokens=20)
        self.calls = 0

    def available(self) -> bool:
        return True

    def generate(self, request: ProviderRequest) -> ProviderResult:
        self.calls += 1
        if self.mode == "timeout":
            raise ProviderTimeout("fake timeout")
        if self.mode == "error":
            raise ProviderError("fake provider error")
        if self.mode == "malformed_json":
            return ProviderResult(
                raw_output="{ this is not valid json", usage=self._usage,
                model="fake",
            )
        if self.mode == "malformed":
            # Structurally JSON but schema-invalid (extra/forbidden field).
            return ProviderResult(
                raw_output=json.dumps({"unexpected_field": True}), usage=self._usage,
                model="fake",
            )
        # success
        if self._raw_output is not None:
            return ProviderResult(
                raw_output=self._raw_output, usage=self._usage, model="fake"
            )
        payload = (
            self._payload
            if self._payload is not None
            else _DEFAULT_OUTPUTS.get(request.output_schema_id, {})
        )
        # Ebene E: der Fake meldet sich unverwechselbar als "fake" — ein
        # Fake-Ergebnis kann nie als reales Modell erscheinen.
        return ProviderResult(
            raw_output=json.dumps(payload), usage=self._usage, model="fake"
        )
