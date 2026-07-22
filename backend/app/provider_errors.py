"""Pure, content-free classification of provider failures.

The classifier is shared by readiness checks, research execution and live-smoke
orchestration.  It deliberately contains no retry loop and never inspects or
persists provider response bodies.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


_HTTP_STATUS = re.compile(r"(?:http|status)\s*[:=]?\s*(\d{3})", re.IGNORECASE)
_INVALID_RESPONSE_HINTS = (
    "invalid json",
    "invalid payload",
    "invalid schema",
    "schema error",
    "schema validation",
    "returned no content",
    "missing structured output",
    "provider_output_invalid",
    "provider_response_invalid",
)


@dataclass(frozen=True)
class ProviderFailureClassification:
    reason_code: str
    retryable: bool
    http_status: int | None
    safe_detail: str

    @property
    def http_class(self) -> str:
        return f"{self.http_status // 100}xx" if self.http_status is not None else "not_available"


def _status_from(message: str, explicit: int | None) -> int | None:
    if explicit is not None:
        return explicit
    match = _HTTP_STATUS.search(message)
    return int(match.group(1)) if match else None


def classify_provider_failure(
    message: str = "",
    *,
    source_code: str | None = None,
    http_status: int | None = None,
) -> ProviderFailureClassification:
    """Return the single canonical safe diagnosis for a provider failure."""
    normalized_message = str(message or "").casefold()
    normalized_code = str(source_code or "").casefold()
    status = _status_from(normalized_message, http_status)

    if status in (401, 403) or normalized_code in {"auth_failed", "provider_auth_error"}:
        return ProviderFailureClassification(
            "provider_auth_error", False, status,
            "Die Provider-Authentifizierung wurde abgelehnt.",
        )
    if status == 429 or normalized_code in {"rate_limited", "provider_rate_limited"}:
        return ProviderFailureClassification(
            "provider_rate_limited", True, status,
            "Der Provider hat den Aufruf wegen eines Rate-Limits oder Kontingents abgelehnt.",
        )
    if status in (502, 503, 504) or normalized_code == "provider_outage":
        return ProviderFailureClassification(
            "provider_outage", True, status,
            "Der Provider ist vorübergehend nicht verfügbar.",
        )
    if (
        normalized_code in {"timeout", "provider_timeout"}
        or "timeout" in normalized_message
        or "time limit" in normalized_message
        or "zeitlimit" in normalized_message
    ):
        return ProviderFailureClassification(
            "provider_timeout", True, status,
            "Der Provider-Aufruf hat das Zeitlimit überschritten.",
        )
    if (
        normalized_code in {"provider_response_invalid", "provider_output_invalid", "schema_error"}
        or any(hint in normalized_message for hint in _INVALID_RESPONSE_HINTS)
    ):
        return ProviderFailureClassification(
            "provider_response_invalid", False, status,
            "Die Provider-Antwort entsprach nicht dem erwarteten Vertrag.",
        )
    if status == 404 or normalized_code == "model_unavailable":
        return ProviderFailureClassification(
            "model_unavailable", False, status,
            "Die konfigurierte Provider-Ressource ist nicht verfügbar.",
        )
    if status == 402 or normalized_code in {"credit_exceeded", "provider_credit_exceeded"}:
        return ProviderFailureClassification(
            "provider_credit_exceeded", False, status,
            "Das Provider-Kontingent ist nicht verfügbar.",
        )
    if normalized_code == "provider_unavailable":
        return ProviderFailureClassification(
            "provider_unavailable", False, status,
            "Der Provider ist nicht konfiguriert oder nicht erreichbar.",
        )
    if status is not None and status >= 500:
        return ProviderFailureClassification(
            "provider_outage", True, status,
            "Der Provider ist vorübergehend nicht verfügbar.",
        )
    return ProviderFailureClassification(
        normalized_code or "provider_error", False, status,
        "Der Provider-Aufruf ist fehlgeschlagen.",
    )


def provider_reason_is_retryable(reason_code: str | None) -> bool:
    """Retryability metadata only; this helper never performs a retry."""
    return str(reason_code or "").casefold() in {
        "provider_rate_limited",
        "provider_outage",
        "provider_timeout",
        # Compatibility for pre-RUN-3C persisted readiness rows.
        "rate_limited",
        "timeout",
    }
