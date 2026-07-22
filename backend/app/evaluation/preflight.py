"""Provider-Preflight (Ebene E) — Live-Readiness ohne Antragsinhalt.

Prüft je Provider (OpenAI, Anthropic, Firecrawl) ausschliesslich mit einem
konstanten synthetischen Ping (D0, kein Projekt-/Antragsinhalt):

1. Key vorhanden,
2. API erreichbar,
3. konfiguriertes Modell verfügbar (Routen-``model_id`` vs. vom Provider
   gemeldetem ``actual_model_id``),
4. strukturierte Ausgabe unterstützt (minimales JSON-Schema),
5. Rate-Limit-/Quota-Fehler verständlich klassifiziert.

Bindend: es werden DIESELBEN produktiven Adapter benutzt wie in der App
(``app.agents.providers.*``, ``app.research.providers.firecrawl``) — keine
parallele Provider-Logik. Nicht ausgeführte Prüfungen sind ``not_run``,
niemals «bestanden». Läuft nie im Pflicht-CI; der Aufruf ist opt-in
(scripts/run_provider_preflight.py). Keine Keys, Prompts oder Rohantworten
im Report — nur Status, Codes und Modell-IDs.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.providers.anthropic import AnthropicProvider
from app.agents.providers.base import (
    ProviderError,
    ProviderRequest,
    ProviderTimeout,
    ProviderUnavailable,
)
from app.agents.providers.openai import OpenAIProvider
from app.agents.registry import AgentRegistry, get_agent_registry
from app.config.settings import Settings, get_settings
from app.db.models import ProviderPreflightResult
from app.evaluation.pricing import (
    COST_STATUS_PRICED,
    PRICE_TABLE_VERSION,
    resolve_cost,
)
from app.provider_errors import classify_provider_failure, provider_reason_is_retryable

PASS = "pass"
FAIL = "fail"
NOT_RUN = "not_run"
LIVE_FAKE_CONFLICT = "live_fake_conflict"

CORE_LIVE_ROLE_IDS = (
    "A1_FACT_EVIDENCE_ANALYST",
    "A2_INNOSUISSE_PROPOSAL_WRITER",
    "A3_INNOSUISSE_CRITICAL_REVIEWER",
)

# Konstanter, öffentlicher Ping — bewusst OHNE jeden Antrags-/Projektbezug.
PING_PROMPT = (
    "Preflight connectivity check. Reply ONLY with the JSON object "
    '{"pong": true}.'
)
PING_SCHEMA_ID = "PreflightPong@v1"
PING_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {"pong": {"type": "boolean"}},
    "required": ["pong"],
}
PING_TIMEOUT_SECONDS = 30
# Public-safe Firecrawl-Ping (generischer öffentlicher Begriff, D0).
FIRECRAWL_PING_QUERY = "innosuisse innovation funding overview"

_AGENT_ADAPTERS = {
    "openai": ("openai_direct", OpenAIProvider),
    "anthropic": ("anthropic_direct", AnthropicProvider),
}

_CHECK_NAMES = (
    "configuration",
    "key_present",
    "api_reachable",
    "model_available",
    "structured_output",
    "rate_limit_clarity",
)


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    status: str  # pass | fail | not_run
    detail: str


@dataclass
class ProviderPreflight:
    provider: str
    mode: str  # live | fake | disabled | not_configured
    checks: list[PreflightCheck] = field(default_factory=list)
    route_key: str | None = None
    requested_model_id: str | None = None
    actual_model_id: str | None = None
    latency_ms: int | None = None
    error_class: str | None = None
    retryable: bool = False

    @property
    def status(self) -> str:
        if any(check.status == FAIL for check in self.checks):
            return FAIL
        if all(check.status == PASS for check in self.checks) and self.checks:
            return PASS
        return NOT_RUN


def classify_provider_error(message: str) -> tuple[str, str]:
    """Compatibility projection of the canonical provider classification.

    Existing readiness clients retain their established reason literals while
    research execution consumes the canonical provider-prefixed literals.
    """
    classified = classify_provider_failure(message)
    compatibility_code = {
        "provider_auth_error": "auth_failed",
        "provider_rate_limited": "rate_limited",
        "provider_timeout": "timeout",
    }.get(classified.reason_code, classified.reason_code)
    return compatibility_code, classified.safe_detail


def _retryable_reason(reason_code: str | None) -> bool:
    return provider_reason_is_retryable(reason_code) or reason_code == "provider_unavailable"


@dataclass(frozen=True)
class ReadinessAssessment:
    status: str
    reason_code: str | None = None
    retryable: bool = False


def configuration_fingerprint(
    route_key: str,
    *,
    settings: Settings | None = None,
    registry: AgentRegistry | None = None,
) -> str:
    """Hash only non-secret configuration that determines preflight validity."""
    settings = settings or get_settings()
    registry = registry or get_agent_registry()
    if route_key == "firecrawl":
        payload = {
            "route_key": route_key,
            "mode": firecrawl_mode(settings),
            "key_present": bool(settings.firecrawl_api_key),
            "registry_version": settings.agent_registry_version,
        }
    else:
        route = registry.route(route_key)
        requested = route.requested_model_id(settings)
        cost = resolve_cost(
            provider=route.provider,
            model_id=requested,
            input_tokens=0,
            output_tokens=0,
            settings=settings,
        ) if requested else None
        payload = {
            "route_key": route_key,
            "route_alias": route.alias,
            "provider": route.provider,
            "requested_model_id": requested,
            "evaluation_only": route.evaluation_only,
            "quality_ceiling_enabled": settings.agent_quality_ceiling_enabled,
            "key_present": _provider_key_present(route.provider, settings),
            "registry_version": settings.agent_registry_version,
            "pricing_version": (
                cost.price_version if cost and cost.price_version
                else PRICE_TABLE_VERSION
            ),
            "cost_status": cost.cost_status if cost else "unknown_price",
        }
    encoded = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def preflight_route(
    route_key: str,
    *,
    settings: Settings | None = None,
    registry: AgentRegistry | None = None,
    adapter=None,
    execute_live: bool = True,
) -> ProviderPreflight:
    """Synthetic, schema-validating smoke for one exact configured route."""
    settings = settings or get_settings()
    registry = registry or get_agent_registry()
    route = registry.route(route_key)
    adapter_cls = OpenAIProvider if route.provider == "openai_direct" else AnthropicProvider
    adapter = adapter or adapter_cls()
    requested = route.requested_model_id(settings)
    result = ProviderPreflight(
        provider=route.provider, mode="live", route_key=route_key,
        requested_model_id=requested,
    )
    if live_fake_conflict(settings):
        result.error_class = LIVE_FAKE_CONFLICT
        result.checks.append(PreflightCheck(
            "configuration", FAIL,
            "AI_EVAL_MODE=real kollidiert mit AGENT_FAKE_PROVIDER=true.",
        ))
        result.checks = _not_run_rest(
            result.checks, "Konfigurationskonflikt zuerst beheben."
        )
        return result
    if settings.ai_eval_mode != "real":
        result.error_class = "live_eval_mode_disabled"
        result.checks.append(PreflightCheck(
            "configuration", FAIL,
            "AI_EVAL_MODE=real ist für einen Live-Provider-Preflight erforderlich.",
        ))
        result.checks = _not_run_rest(
            result.checks, "Live-Evaluationsmodus zuerst aktivieren."
        )
        return result
    result.checks.append(PreflightCheck(
        "configuration", PASS, "Kein Live-/Demo-Konflikt."
    ))
    key_present = adapter.available()
    result.checks.append(PreflightCheck(
        "key_present", PASS if key_present else FAIL,
        "API-Schlüssel konfiguriert." if key_present else "Kein API-Schlüssel konfiguriert.",
    ))
    if not key_present:
        result.mode = "not_configured"
        result.error_class = "auth_failed"
        result.checks = _not_run_rest(result.checks, "Ohne Schlüssel nicht prüfbar.")
        return result
    if not requested:
        result.error_class = "model_unavailable"
        result.checks.append(PreflightCheck(
            "model_available", FAIL,
            "Der logische Kandidat ist nicht auf eine Provider-Modell-ID aufgelöst.",
        ))
        result.checks = _not_run_rest(result.checks, "Modell-ID nicht konfiguriert.")
        return result
    if not execute_live:
        result.checks = _not_run_rest(result.checks, "Live-Aufruf nicht freigegeben.")
        return result
    request = ProviderRequest(
        model_id=requested, prompt=PING_PROMPT, output_schema_id=PING_SCHEMA_ID,
        timeout_seconds=PING_TIMEOUT_SECONDS, output_json_schema=PING_JSON_SCHEMA,
        reasoning_effort=(route.capabilities or {}).get("default_effort"),
    )
    started = datetime.now(timezone.utc)
    try:
        ping = adapter.generate(request)
    except ProviderError as exc:
        result.error_class = exc.code
        result.retryable = exc.retryable
        result.checks.append(PreflightCheck(
            "api_reachable", FAIL, f"[{exc.code}] Provider-Aufruf fehlgeschlagen.",
        ))
        result.checks = _not_run_rest(result.checks, "Wegen Providerfehler nicht prüfbar.")
        return result
    finally:
        result.latency_ms = int(
            (datetime.now(timezone.utc) - started).total_seconds() * 1000
        )
    result.actual_model_id = ping.model
    result.checks.extend([
        PreflightCheck("api_reachable", PASS, "Provider-API hat geantwortet."),
        PreflightCheck(
            "model_available", PASS if bool(ping.model) else FAIL,
            "Provider hat die tatsächliche Modell-ID gemeldet."
            if ping.model else "Provider hat keine Modell-ID gemeldet.",
        ),
    ])
    try:
        structured_ok = json.loads(ping.raw_output) == {"pong": True}
    except (json.JSONDecodeError, TypeError):
        structured_ok = False
    result.checks.extend([
        PreflightCheck(
            "structured_output", PASS if structured_ok else FAIL,
            "Schema-Smoke erfolgreich." if structured_ok else "Schema-Smoke fehlgeschlagen.",
        ),
        PreflightCheck("rate_limit_clarity", PASS, "Fehlerklassifikation aktiv."),
    ])
    if not structured_ok:
        result.error_class = "schema_invalid"
    return result


def persist_route_preflight(
    db: Session, result: ProviderPreflight, *, triggered_by: str | None = None,
    settings: Settings | None = None,
) -> ProviderPreflightResult:
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    route_key = result.route_key or "unknown"
    registry = get_agent_registry()
    try:
        route_alias = registry.route(route_key).alias
    except Exception:  # pragma: no cover - malformed registry fails at startup
        route_alias = route_key
    pricing_version = PRICE_TABLE_VERSION
    if route_key != "firecrawl":
        try:
            route = registry.route(route_key)
            cost = resolve_cost(
                provider=route.provider,
                model_id=result.requested_model_id,
                input_tokens=0,
                output_tokens=0,
                settings=settings,
            )
            pricing_version = cost.price_version or PRICE_TABLE_VERSION
        except Exception:  # pragma: no cover - invalid registry fails elsewhere
            pricing_version = PRICE_TABLE_VERSION
    row = ProviderPreflightResult(
        preflight_id=str(uuid.uuid4()), route_key=route_key,
        route_alias=route_alias, provider=result.provider,
        requested_model_id=result.requested_model_id,
        actual_model_id=result.actual_model_id, status=result.status,
        checks_json=[{"name": c.name, "status": c.status, "detail": c.detail} for c in result.checks],
        error_class=result.error_class,
        reason_code=result.error_class,
        retryable=result.retryable,
        configuration_fingerprint=configuration_fingerprint(
            route_key, settings=settings, registry=registry
        ),
        registry_version=settings.agent_registry_version,
        pricing_version=pricing_version,
        latency_ms=result.latency_ms,
        triggered_by=triggered_by, checked_at=now,
        expires_at=now + timedelta(seconds=settings.provider_preflight_ttl_seconds),
    )
    db.add(row)
    db.flush()
    return row


def latest_route_preflight(db: Session, route_key: str) -> ProviderPreflightResult | None:
    return db.scalar(
        select(ProviderPreflightResult)
        .where(ProviderPreflightResult.route_key == route_key)
        .order_by(ProviderPreflightResult.checked_at.desc())
    )


def live_fake_conflict(settings: Settings) -> bool:
    return settings.ai_eval_mode == "real" and settings.agent_fake_provider


def _provider_key_present(provider: str, settings: Settings) -> bool:
    if provider == "openai_direct":
        return bool(settings.openai_api_key)
    if provider == "anthropic_direct":
        return bool(settings.anthropic_api_key)
    return False


def route_configuration_reason(
    route_key: str,
    *,
    settings: Settings | None = None,
    registry: AgentRegistry | None = None,
) -> str | None:
    """First deployment-only reason that makes one live route unusable."""
    settings = settings or get_settings()
    registry = registry or get_agent_registry()
    if live_fake_conflict(settings):
        return LIVE_FAKE_CONFLICT
    if settings.ai_eval_mode != "real":
        return "live_eval_mode_disabled"
    route = registry.route(route_key)
    if route.evaluation_only and not settings.agent_quality_ceiling_enabled:
        return "live_route_evaluation_disabled"
    requested = route.requested_model_id(settings)
    if not requested:
        return "live_model_id_missing"
    if not _provider_key_present(route.provider, settings):
        return "live_provider_key_missing"
    cost = resolve_cost(
        provider=route.provider,
        model_id=requested,
        input_tokens=0,
        output_tokens=0,
        settings=settings,
    )
    if cost.cost_status != COST_STATUS_PRICED:
        return "live_price_metadata_missing"
    return None


def route_preflight_reason(
    db: Session,
    route_key: str,
    *,
    settings: Settings | None = None,
    registry: AgentRegistry | None = None,
) -> str | None:
    """Compatibility reason: None only when the derived route status is ready."""
    readiness = route_readiness(
        db, route_key, settings=settings, registry=registry
    )
    return None if readiness.status == "ready" else readiness.reason_code


def route_readiness(
    db: Session | None,
    route_key: str,
    *,
    settings: Settings | None = None,
    registry: AgentRegistry | None = None,
) -> ReadinessAssessment:
    """Derive route truth from config plus its matching persisted preflight."""
    settings = settings or get_settings()
    registry = registry or get_agent_registry()
    configured_reason = route_configuration_reason(
        route_key, settings=settings, registry=registry
    )
    if configured_reason:
        if configured_reason == LIVE_FAKE_CONFLICT:
            return ReadinessAssessment("error", configured_reason, False)
        if configured_reason in {
            "live_eval_mode_disabled", "live_route_evaluation_disabled",
        }:
            return ReadinessAssessment("disabled", configured_reason, False)
        return ReadinessAssessment("not_configured", configured_reason, False)
    if db is None or not hasattr(db, "scalar"):
        return ReadinessAssessment(
            "configured_unverified", "live_preflight_required", False
        )
    requested = registry.route(route_key).requested_model_id(settings)
    row = latest_route_preflight(db, route_key)
    if row is None:
        return ReadinessAssessment(
            "configured_unverified", "live_preflight_required", False
        )
    if row.requested_model_id != requested:
        return ReadinessAssessment(
            "configured_unverified", "live_preflight_stale_model", False
        )
    expected_fingerprint = configuration_fingerprint(
        route_key, settings=settings, registry=registry
    )
    if row.configuration_fingerprint != expected_fingerprint:
        return ReadinessAssessment(
            "configured_unverified", "live_preflight_stale_configuration", False
        )
    if row.status != PASS:
        reason = row.reason_code or row.error_class or "live_preflight_failed"
        retryable = bool(row.retryable) or _retryable_reason(reason)
        return ReadinessAssessment(
            "degraded" if retryable else "error", reason, retryable
        )
    if not row.actual_model_id:
        return ReadinessAssessment("error", "live_actual_model_missing", False)
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        return ReadinessAssessment(
            "configured_unverified", "live_preflight_expired", False
        )
    return ReadinessAssessment("ready")


def route_preflight_passed(
    db: Session,
    route_key: str,
    *,
    settings: Settings | None = None,
    registry: AgentRegistry | None = None,
) -> bool:
    return route_preflight_reason(
        db, route_key, settings=settings, registry=registry
    ) is None


def ready_route_for_role(
    db: Session | None,
    role_id: str,
    *,
    settings: Settings | None = None,
    registry: AgentRegistry | None = None,
) -> tuple[str | None, str | None]:
    """Resolve one usable primary/fallback route for a live model role."""
    settings = settings or get_settings()
    registry = registry or get_agent_registry()
    role = (registry.role_routes or {}).get(role_id)
    if role is None or role.execution_kind != "model_gateway":
        return None, "live_route_not_configured"
    candidates = [key for key in (role.primary, role.fallback) if key]
    configured: list[str] = []
    configuration_reasons: list[str] = []
    for route_key in candidates:
        reason = route_configuration_reason(
            route_key, settings=settings, registry=registry
        )
        if reason is None:
            configured.append(route_key)
        else:
            configuration_reasons.append(reason)
    if not configured:
        return None, configuration_reasons[0] if configuration_reasons else (
            "live_route_not_configured"
        )
    if db is None or not hasattr(db, "scalar"):
        return None, "live_preflight_required"
    preflight_reasons: list[str] = []
    for route_key in configured:
        reason = route_preflight_reason(
            db, route_key, settings=settings, registry=registry
        )
        if reason is None:
            return route_key, None
        preflight_reasons.append(reason)
    return None, preflight_reasons[0]


def generation_mode_status(
    db: Session | None,
    settings: Settings,
    *,
    registry: AgentRegistry | None = None,
    role_ids: tuple[str, ...] = CORE_LIVE_ROLE_IDS,
) -> tuple[str, str | None]:
    """Deployment generation truth shared by capabilities and status views."""
    if settings.ai_eval_mode == "real":
        if live_fake_conflict(settings):
            return "live_unavailable", LIVE_FAKE_CONFLICT
        registry = registry or get_agent_registry()
        for role_id in role_ids:
            _route_key, reason = ready_route_for_role(
                db, role_id, settings=settings, registry=registry
            )
            if reason:
                return "live_unavailable", reason
        return "real_eval", None
    if settings.agent_fake_provider:
        return "fake_demo", None
    return "unavailable", "no_approved_model_provider"


def _not_run_rest(done: list[PreflightCheck], reason: str) -> list[PreflightCheck]:
    names = {check.name for check in done}
    return done + [
        PreflightCheck(name, NOT_RUN, reason)
        for name in _CHECK_NAMES
        if name not in names
    ]


def _route_for(
    registry: AgentRegistry, provider_key: str, settings: Settings
) -> str | None:
    for route in registry.model_routes.values():
        requested = route.requested_model_id(settings)
        if route.provider == provider_key and requested and route.status == "active":
            return requested
    for route in registry.model_routes.values():
        requested = route.requested_model_id(settings)
        if route.provider == provider_key and requested:
            return requested
    return None


def preflight_agent_provider(
    provider: str,
    *,
    settings: Settings | None = None,
    registry: AgentRegistry | None = None,
    adapter=None,
    execute_live: bool = True,
) -> ProviderPreflight:
    """Preflight für einen Agent-Provider («openai» | «anthropic»)."""
    settings = settings or get_settings()
    registry = registry or get_agent_registry()
    provider_key, adapter_cls = _AGENT_ADAPTERS[provider]
    adapter = adapter or adapter_cls()
    result = ProviderPreflight(provider=provider, mode="live")

    if live_fake_conflict(settings):
        result.error_class = LIVE_FAKE_CONFLICT
        result.checks.append(PreflightCheck(
            "configuration", FAIL,
            "AI_EVAL_MODE=real kollidiert mit AGENT_FAKE_PROVIDER=true.",
        ))
        result.checks = _not_run_rest(
            result.checks, "Konfigurationskonflikt zuerst beheben."
        )
        return result
    if settings.ai_eval_mode != "real":
        result.error_class = "live_eval_mode_disabled"
        result.checks.append(PreflightCheck(
            "configuration", FAIL,
            "AI_EVAL_MODE=real ist für einen Live-Provider-Preflight erforderlich.",
        ))
        result.checks = _not_run_rest(
            result.checks, "Live-Evaluationsmodus zuerst aktivieren."
        )
        return result
    result.checks.append(PreflightCheck(
        "configuration", PASS, "Kein Live-/Demo-Konflikt."
    ))
    key_present = adapter.available()
    result.checks.append(
        PreflightCheck(
            "key_present",
            PASS if key_present else FAIL,
            "API-Schlüssel konfiguriert." if key_present
            else "Kein API-Schlüssel konfiguriert (Backend-Umgebung).",
        )
    )
    if not key_present:
        result.mode = "not_configured"
        result.checks = _not_run_rest(result.checks, "Ohne Schlüssel nicht prüfbar.")
        return result
    if not execute_live:
        result.checks = _not_run_rest(
            result.checks, "Live-Aufruf nicht freigegeben (Opt-in fehlt)."
        )
        return result

    requested_model = _route_for(registry, provider_key, settings)
    if requested_model is None:
        result.checks.append(
            PreflightCheck(
                "model_available", FAIL,
                f"Keine Modellroute für Provider «{provider_key}» in der Registry.",
            )
        )
        result.checks = _not_run_rest(result.checks, "Keine Modellroute konfiguriert.")
        return result

    request = ProviderRequest(
        model_id=requested_model,
        prompt=PING_PROMPT,
        output_schema_id=PING_SCHEMA_ID,
        timeout_seconds=PING_TIMEOUT_SECONDS,
        output_json_schema=PING_JSON_SCHEMA,
    )
    try:
        ping = adapter.generate(request)
    except ProviderTimeout:
        result.error_class = "timeout"
        result.retryable = True
        result.checks.append(
            PreflightCheck(
                "api_reachable", FAIL,
                "Zeitüberschreitung — die Provider-API war nicht erreichbar.",
            )
        )
        result.checks = _not_run_rest(result.checks, "API nicht erreichbar.")
        return result
    except (ProviderError, ProviderUnavailable) as exc:
        code, text = classify_provider_error(str(exc))
        result.error_class = code
        result.retryable = getattr(exc, "retryable", False) or _retryable_reason(code)
        failed = "model_available" if code == "model_unavailable" else "api_reachable"
        result.checks.append(PreflightCheck(failed, FAIL, f"[{code}] {text}"))
        if code == "rate_limited":
            result.checks.append(
                PreflightCheck("rate_limit_clarity", PASS, f"[{code}] {text}")
            )
        result.checks = _not_run_rest(
            result.checks, "Wegen vorherigem Fehler nicht prüfbar."
        )
        return result

    result.checks.append(
        PreflightCheck("api_reachable", PASS, "Provider-API hat geantwortet.")
    )
    if ping.model:
        detail = (
            f"Angefragt «{requested_model}», vom Provider gemeldet «{ping.model}»."
        )
        result.checks.append(PreflightCheck("model_available", PASS, detail))
    else:
        result.checks.append(
            PreflightCheck(
                "model_available", FAIL,
                "Der Provider hat kein Modell in der Antwort gemeldet — "
                "Modellauflösung nicht nachweisbar.",
            )
        )
    try:
        payload = json.loads(ping.raw_output)
        structured_ok = isinstance(payload, dict) and "pong" in payload
    except (json.JSONDecodeError, TypeError):
        structured_ok = False
    result.checks.append(
        PreflightCheck(
            "structured_output",
            PASS if structured_ok else FAIL,
            "Schema-konforme JSON-Antwort erhalten." if structured_ok
            else "Die Antwort war kein schema-konformes JSON.",
        )
    )
    result.checks.append(
        PreflightCheck(
            "rate_limit_clarity", PASS,
            "Kein Rate-Limit aufgetreten; 429 würde verständlich "
            "klassifiziert (siehe classify_provider_error).",
        )
    )
    return result


def firecrawl_mode(settings: Settings) -> str:
    """Firecrawl-Tri-State: disabled | fake | live | not_configured."""
    if not settings.web_research_enabled:
        return "disabled"
    if settings.web_research_fake_provider:
        return "fake"
    if settings.firecrawl_api_key:
        return "live"
    return "not_configured"


def firecrawl_preflight_reason(
    db: Session | None, settings: Settings
) -> str | None:
    readiness = firecrawl_readiness(db, settings)
    return None if readiness.status == "ready" else readiness.reason_code


def firecrawl_readiness(
    db: Session | None, settings: Settings
) -> ReadinessAssessment:
    mode = firecrawl_mode(settings)
    if mode == "disabled":
        return ReadinessAssessment("disabled", "web_research_disabled", False)
    if mode == "fake":
        return ReadinessAssessment("fake", "web_research_demo", False)
    if mode != "live":
        return ReadinessAssessment("not_configured", "firecrawl_key_missing", False)
    if db is None or not hasattr(db, "scalar"):
        return ReadinessAssessment(
            "configured_unverified", "firecrawl_preflight_required", False
        )
    row = latest_route_preflight(db, "firecrawl")
    if row is None:
        return ReadinessAssessment(
            "configured_unverified", "firecrawl_preflight_required", False
        )
    if row.configuration_fingerprint != configuration_fingerprint(
        "firecrawl", settings=settings
    ):
        return ReadinessAssessment(
            "configured_unverified", "firecrawl_preflight_stale_configuration", False
        )
    if row.status != PASS:
        reason = row.reason_code or row.error_class or "firecrawl_preflight_failed"
        retryable = bool(row.retryable) or _retryable_reason(reason)
        return ReadinessAssessment(
            "degraded" if retryable else "error", reason, retryable
        )
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        return ReadinessAssessment(
            "configured_unverified", "firecrawl_preflight_expired", False
        )
    return ReadinessAssessment("ready")


def preflight_firecrawl(
    *,
    settings: Settings | None = None,
    provider=None,
    execute_live: bool = True,
) -> ProviderPreflight:
    """Preflight für die Webrecherche (Firecrawl) inkl. Modusanzeige."""
    settings = settings or get_settings()
    mode = firecrawl_mode(settings)
    result = ProviderPreflight(
        provider="firecrawl", mode=mode, route_key="firecrawl"
    )
    result.checks.append(PreflightCheck(
        "configuration",
        PASS if mode == "live" else (NOT_RUN if mode in ("disabled", "fake") else FAIL),
        f"Webrecherche-Modus: {mode}.",
    ))
    key_present = mode == "live"
    result.checks.append(
        PreflightCheck(
            "key_present",
            PASS if key_present else (NOT_RUN if mode in ("disabled", "fake") else FAIL),
            f"Webrecherche-Modus: {mode}.",
        )
    )
    if mode != "live" or not execute_live:
        reason = (
            f"Modus «{mode}» — kein Live-Aufruf." if mode != "live"
            else "Live-Aufruf nicht freigegeben (Opt-in fehlt)."
        )
        result.checks = _not_run_rest(result.checks, reason)
        return result

    from app.research.providers.base import (
        CreditExceeded,
        ProviderError as WebProviderError,
        ProviderTimeout as WebProviderTimeout,
        ProviderUnavailable as WebProviderUnavailable,
        SearchRequest,
    )
    from app.research.providers.firecrawl import FirecrawlProvider

    provider = provider or FirecrawlProvider(
        api_key=settings.firecrawl_api_key, timeout_seconds=PING_TIMEOUT_SECONDS
    )
    try:
        outcome = provider.search(
            SearchRequest(query=FIRECRAWL_PING_QUERY, max_results=1)
        )
    except CreditExceeded:
        result.error_class = "rate_limited"
        result.retryable = True
        result.checks.append(
            PreflightCheck(
                "rate_limit_clarity", PASS,
                "[rate_limited] Firecrawl meldet Kontingent-/Budgetgrenze "
                "(HTTP 402/429) — verständlich klassifiziert.",
            )
        )
        result.checks.append(
            PreflightCheck(
                "api_reachable", FAIL,
                "Kontingent-/Budgetgrenze erreicht — keine Suche möglich.",
            )
        )
        result.checks = _not_run_rest(result.checks, "Kontingent erschöpft.")
        return result
    except (WebProviderError, WebProviderTimeout, WebProviderUnavailable) as exc:
        code, text = classify_provider_error(str(exc))
        result.error_class = code
        result.retryable = isinstance(
            exc, (WebProviderTimeout, WebProviderUnavailable)
        ) or _retryable_reason(code)
        result.checks.append(PreflightCheck("api_reachable", FAIL, f"[{code}] {text}"))
        result.checks = _not_run_rest(result.checks, "API nicht erreichbar.")
        return result

    result.checks.append(
        PreflightCheck("api_reachable", PASS, "Firecrawl-Suche hat geantwortet.")
    )
    result.latency_ms = outcome.latency_ms
    # Live darf NIE Fake-Hosts liefern (example.org ist der Fake-Provider).
    fake_hosts = [
        candidate.url
        for candidate in outcome.candidates
        if "example.org" in candidate.url
    ]
    if fake_hosts:
        result.error_class = "live_demo_domain_rejected"
    result.checks.append(
        PreflightCheck(
            "model_available",
            FAIL if fake_hosts else PASS,
            "Live-Modus lieferte example.org-Ergebnisse — Modusverwechslung!"
            if fake_hosts
            else f"{len(outcome.candidates)} echte(s) Suchergebnis(se) erhalten "
            "(0 ist ein gültiger, dokumentierter Leerzustand).",
        )
    )
    result.checks.append(
        PreflightCheck(
            "structured_output", PASS,
            "Suchantwort strukturell gültig (Kandidatenliste).",
        )
    )
    result.checks.append(
        PreflightCheck(
            "rate_limit_clarity", PASS,
            "Kein Kontingentfehler aufgetreten; 402/429 würde als "
            "Kontingent-/Budgetgrenze klassifiziert.",
        )
    )
    return result


def run_preflight(
    *,
    settings: Settings | None = None,
    registry: AgentRegistry | None = None,
    execute_live: bool,
    adapters: dict[str, object] | None = None,
    web_provider=None,
) -> list[ProviderPreflight]:
    """Alle Provider-Preflights (deterministische Reihenfolge)."""
    settings = settings or get_settings()
    registry = registry or get_agent_registry()
    adapters = adapters or {}
    results = [
        preflight_agent_provider(
            provider,
            settings=settings,
            registry=registry,
            adapter=adapters.get(provider),
            execute_live=execute_live,
        )
        for provider in ("openai", "anthropic")
    ]
    results.append(
        preflight_firecrawl(
            settings=settings, provider=web_provider, execute_live=execute_live
        )
    )
    return results


def configured_live_route_keys(
    *,
    registry: AgentRegistry | None = None,
    role_ids: tuple[str, ...] = CORE_LIVE_ROLE_IDS,
    include_comparison: bool = False,
) -> list[str]:
    registry = registry or get_agent_registry()
    route_keys: list[str] = []
    for role_id in role_ids:
        role = (registry.role_routes or {}).get(role_id)
        if role is None or role.execution_kind != "model_gateway":
            continue
        candidates = [role.primary, role.fallback]
        if include_comparison:
            candidates.append(role.comparison)
        for route_key in candidates:
            if route_key and route_key not in route_keys:
                route_keys.append(route_key)
    return route_keys


def run_configured_preflight(
    *,
    settings: Settings | None = None,
    registry: AgentRegistry | None = None,
    execute_live: bool,
    adapters: dict[str, object] | None = None,
    web_provider=None,
) -> list[ProviderPreflight]:
    """Exact environment-resolved role routes plus Firecrawl; metadata only."""
    settings = settings or get_settings()
    registry = registry or get_agent_registry()
    adapters = adapters or {}
    results = [
        preflight_route(
            route_key,
            settings=settings,
            registry=registry,
            adapter=adapters.get(route_key),
            execute_live=execute_live,
        )
        for route_key in configured_live_route_keys(registry=registry)
    ]
    results.append(
        preflight_firecrawl(
            settings=settings, provider=web_provider, execute_live=execute_live
        )
    )
    return results


_STATUS_LABELS = {PASS: "bestanden", FAIL: "nicht bestanden", NOT_RUN: "not_run"}


def _route_configured(result: ProviderPreflight) -> bool:
    if result.provider == "firecrawl":
        return result.mode == "live"
    return bool(result.requested_model_id)


def render_report(results: list[ProviderPreflight]) -> str:
    """Whitelist-Markdown-Report — Status/Codes/Modell-IDs, keine Rohdaten.

    ``not_run`` wird IMMER wörtlich als ``not_run`` gerendert — nie als
    bestanden und nie in einer Sammel-Grün-Aussage versteckt.
    """
    lines = [
        "# Provider-Preflight (Ebene E — Live-Readiness)",
        "",
        "Konstanter synthetischer Ping ohne Antragsinhalt; dieselben",
        "produktiven Adapter wie die App. `not_run` heisst: nicht geprüft —",
        "niemals bestanden.",
        "",
    ]
    for result in results:
        lines.append(
            f"## {result.provider} — Modus: {result.mode} — "
            f"Gesamtstatus: {_STATUS_LABELS[result.status]}"
        )
        lines.append("")
        if result.route_key:
            lines.append(f"- Route: `{result.route_key}`")
        lines.append(
            f"- Route konfiguriert: {'ja' if _route_configured(result) else 'nein'}"
        )
        lines.append(
            f"- Angefragte Modell-ID: `{result.requested_model_id}`"
            if result.requested_model_id else "- Angefragte Modell-ID: nicht aufgelöst"
        )
        lines.append(
            f"- Tatsächliche Modell-ID: `{result.actual_model_id}`"
            if result.actual_model_id else "- Tatsächliche Modell-ID: nicht bestätigt"
        )
        lines.append("")
        lines.append("| Check | Status | Detail |")
        lines.append("|---|---|---|")
        for check in result.checks:
            lines.append(
                f"| {check.name} | {_STATUS_LABELS[check.status]} | {check.detail} |"
            )
        lines.append("")
    return "\n".join(lines)


def to_json(results: list[ProviderPreflight]) -> str:
    return json.dumps(
        [
            {
                "provider": result.provider,
                "mode": result.mode,
                "status": result.status,
                "route_key": result.route_key,
                "route_configured": _route_configured(result),
                "requested_model_id": result.requested_model_id,
                "actual_model_id": result.actual_model_id,
                "latency_ms": result.latency_ms,
                "error_class": result.error_class,
                "checks": [
                    {"name": c.name, "status": c.status, "detail": c.detail}
                    for c in result.checks
                ],
            }
            for result in results
        ],
        ensure_ascii=False,
        indent=2,
    )
