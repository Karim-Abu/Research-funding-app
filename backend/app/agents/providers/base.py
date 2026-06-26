"""Provider adapter protocol + shared types (Milestone 9A)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class ProviderRequest:
    model_id: str
    # Assembled prompt — contains NO API keys and (per data policy) no restricted
    # source content in shared logs. Providers must not log it.
    prompt: str
    output_schema_id: str
    timeout_seconds: int
    max_output_tokens: int | None = None


@dataclass(frozen=True)
class ProviderResult:
    raw_output: str  # the model's structured output (expected JSON), unparsed
    usage: ProviderUsage = field(default_factory=ProviderUsage)


class ProviderError(Exception):
    """Provider returned an error (non-timeout)."""


class ProviderTimeout(Exception):
    """Provider call exceeded the configured timeout."""


class ProviderUnavailable(Exception):
    """Provider route is not configured (e.g. missing API key)."""


@runtime_checkable
class ProviderAdapter(Protocol):
    name: str

    def available(self) -> bool: ...

    def generate(self, request: ProviderRequest) -> ProviderResult: ...
