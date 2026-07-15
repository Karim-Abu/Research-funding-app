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
    # R5.5b: optional JSON Schema of the declared output (pydantic
    # model_json_schema). Adapters MAY use it for provider-native structured
    # output (OpenAI Responses / Anthropic Messages output_config). Advisory
    # only — the gateway's pydantic validation stays the sole authority.
    output_json_schema: dict | None = None
    # Provider-neutral role setting. Adapters translate this only when the
    # selected route supports it; unsupported sampling knobs are never added.
    reasoning_effort: str | None = None


@dataclass(frozen=True)
class ProviderResult:
    raw_output: str  # the model's structured output (expected JSON), unparsed
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    # Live-Readiness (Ebene E): das vom Provider in der Antwort GEMELDETE
    # Modell (z. B. Auflösung eines Alias) — nie das angefragte model_id.
    # None, wenn der Provider kein Modell zurückmeldet.
    model: str | None = None
    # Safe provider stop reason (stop, max_tokens, refusal, ...), never raw text.
    termination_reason: str | None = None


class ProviderError(Exception):
    """Typed, log-safe provider failure."""

    def __init__(
        self,
        message: str = "provider request failed",
        *,
        code: str = "provider_error",
        retryable: bool = False,
        termination_reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.termination_reason = termination_reason or code


class ProviderTimeout(ProviderError):
    """Provider call exceeded the configured timeout."""

    def __init__(self, message: str = "provider timeout") -> None:
        super().__init__(
            message, code="timeout", retryable=True, termination_reason="timeout"
        )


class ProviderUnavailable(ProviderError):
    """Provider route is not configured (e.g. missing API key/model mapping)."""

    def __init__(self, message: str = "provider unavailable") -> None:
        super().__init__(
            message,
            code="model_unavailable",
            termination_reason="provider_unavailable",
        )


@runtime_checkable
class ProviderAdapter(Protocol):
    name: str

    def available(self) -> bool: ...

    def generate(self, request: ProviderRequest) -> ProviderResult: ...
