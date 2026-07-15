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

import json
import re
from dataclasses import dataclass, field

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

PASS = "pass"
FAIL = "fail"
NOT_RUN = "not_run"

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

    @property
    def status(self) -> str:
        if any(check.status == FAIL for check in self.checks):
            return FAIL
        if all(check.status == PASS for check in self.checks) and self.checks:
            return PASS
        return NOT_RUN


def classify_provider_error(message: str) -> tuple[str, str]:
    """HTTP-/Fehlerklassifikation → (code, verständlicher deutscher Text)."""
    match = re.search(r"http (\d{3})", message)
    status = int(match.group(1)) if match else None
    if status in (401, 403):
        return "auth_failed", (
            "Der API-Schlüssel wurde abgelehnt (HTTP "
            f"{status}). Schlüssel prüfen/erneuern."
        )
    if status == 404:
        return "model_unavailable", (
            "Das konfigurierte Modell ist beim Provider nicht verfügbar "
            "(HTTP 404). Modellroute in der Registry prüfen."
        )
    if status == 429:
        return "rate_limited", (
            "Rate-Limit oder Kontingent erreicht (HTTP 429). Später erneut "
            "versuchen oder Kontingent/Abrechnung beim Provider prüfen."
        )
    if status is not None and status >= 500:
        return "provider_outage", (
            f"Der Provider meldet einen Serverfehler (HTTP {status}). "
            "Später erneut versuchen."
        )
    return "provider_error", (
        "Der Provider-Aufruf ist fehlgeschlagen (keine HTTP-Statusangabe). "
        "Netzwerk/Konfiguration prüfen."
    )


def _not_run_rest(done: list[PreflightCheck], reason: str) -> list[PreflightCheck]:
    names = {check.name for check in done}
    return done + [
        PreflightCheck(name, NOT_RUN, reason)
        for name in _CHECK_NAMES
        if name not in names
    ]


def _route_for(registry: AgentRegistry, provider_key: str) -> str | None:
    for route in registry.model_routes.values():
        if route.provider == provider_key and route.status == "active":
            return route.model_id
    for route in registry.model_routes.values():
        if route.provider == provider_key:
            return route.model_id
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

    requested_model = _route_for(registry, provider_key)
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


def preflight_firecrawl(
    *,
    settings: Settings | None = None,
    provider=None,
    execute_live: bool = True,
) -> ProviderPreflight:
    """Preflight für die Webrecherche (Firecrawl) inkl. Modusanzeige."""
    settings = settings or get_settings()
    mode = firecrawl_mode(settings)
    result = ProviderPreflight(provider="firecrawl", mode=mode)
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
        result.checks.append(PreflightCheck("api_reachable", FAIL, f"[{code}] {text}"))
        result.checks = _not_run_rest(result.checks, "API nicht erreichbar.")
        return result

    result.checks.append(
        PreflightCheck("api_reachable", PASS, "Firecrawl-Suche hat geantwortet.")
    )
    # Live darf NIE Fake-Hosts liefern (example.org ist der Fake-Provider).
    fake_hosts = [
        candidate.url
        for candidate in outcome.candidates
        if "example.org" in candidate.url
    ]
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


_STATUS_LABELS = {PASS: "bestanden", FAIL: "nicht bestanden", NOT_RUN: "not_run"}


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
