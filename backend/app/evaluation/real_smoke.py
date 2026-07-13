"""EVAL.2 — Manueller Real-Provider-Smoke (OpenAI, Anthropic, Firecrawl).

Beweist mit genau EINEM realen Call pro Provider, dass die Adapter über die
bestehenden Grenzen (``gateway.invoke``, Research-Service → Executor)
funktionieren und Usage-/Cost-Metadaten geschrieben werden. Azure ist NICHT
Teil dieses Smokes (kein Adapter im App-Code, policy-blockiert).

Manual Mode — reale Calls nur wenn ALLE Guards erfüllt sind:
``CI`` nicht gesetzt, ``RUN_REAL_PROVIDER_SMOKE=true``, ``AI_EVAL_MODE=real``,
abgeleiteter ``data_mode == synthetic_eval``, ``--case F1``, Provider explizit,
API-Key vorhanden. Max 1 Smoke-Lauf pro Provider (Result-JSON-Existenz-Check),
max 1 LLM-Call (Registry-Kopie mit ``max_retries=0`` + Single-Call-Proxy).

Daten: ausschliesslich die F1-abgeleitete synthetische D0-Variante (EVAL.1)
bzw. eine fixe public-safe Firecrawl-Query. Keine echten D2-Daten, keine
Partnernamen, keine Budgetzahlen. Roh-Outputs landen NUR als Eval-Artefakt im
git-ignorierten ``backend/var/evaluation/eval2/`` — nie in Logs/Audit/Report.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from sqlalchemy import select

from app.agents.gateway import ModelResponse, invoke
from app.agents.providers.anthropic import AnthropicProvider
from app.agents.providers.base import ProviderUnavailable
from app.agents.providers.openai import OpenAIProvider
from app.agents.registry import AgentRegistry, get_agent_registry
from app.config.settings import get_settings
from app.contracts.research import ResearchTaskCreate
from app.db.models import (
    AgentInvocation,
    AnalysisRun,
    Project,
    ResearchTask,
    UsageRecord,
)
from app.evaluation.data_mode import derive_data_mode
from app.evaluation.pricing import PRICE_TABLE_VERSION
from app.evaluation.usage import run_usage_totals, tool_usage_by_research_task
from app.evaluation.usage_smoke import (
    ACTOR,
    F1_SMOKE_CLASSIFICATION,
    PROFILE,
    WS,
    SmokeFailure,
    _base_request,
    _ensure_base_rows,
)
from app.research.executor import research_executor
from app.research.service import create_research_task

PROVIDERS = ("openai", "anthropic", "firecrawl")
ROUTE_FOR = {"openai": "openai_direct", "anthropic": "anthropic_direct"}
# Fixe public-safe D0-Query — keine Projektbegriffe, keine sensiblen Muster.
FIRECRAWL_QUERY = "industrial AI quality monitoring manufacturing Switzerland"

# Vom Report ausgeschlossene Ergebnis-Teile (nur var/-Artefakt): Rohoutputs.
_ARTIFACT_KEY = "artifact"


def guard_refusal(
    *, provider: str, env: Mapping[str, str], settings
) -> str | None:
    """Pure Manual-Mode-Prüfung. Liefert den Refusal-Grund oder None.

    Meldungen enthalten nie Key-Material — nur Providernamen/Flag-Namen.
    """
    if env.get("CI", "").strip():
        return "ci_environment: reale Provider-Smokes sind in CI verboten"
    if env.get("RUN_REAL_PROVIDER_SMOKE") != "true":
        return "RUN_REAL_PROVIDER_SMOKE=true fehlt (expliziter manueller Opt-in)"
    if settings.ai_eval_mode != "real":
        return "AI_EVAL_MODE=real fehlt (Owner-Freigabe für synthetic_eval)"
    if (
        derive_data_mode(ai_eval_mode=settings.ai_eval_mode, origin="synthetic")
        != "synthetic_eval"
    ):
        return "data_mode ist nicht synthetic_eval"
    key_present = {
        "openai": bool(settings.openai_api_key),
        "anthropic": bool(settings.anthropic_api_key),
        "firecrawl": bool(settings.firecrawl_api_key),
    }[provider]
    if not key_present:
        return (
            f"provider_unavailable: kein API-Key für {provider} konfiguriert "
            "(backend/.env)"
        )
    return None


class _SingleCallAdapter:
    """Defense-in-depth-Cap: erlaubt genau einen generate()-Call."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.calls = 0

    @property
    def name(self) -> str:  # provider_policy/_try_route lesen adapter.name
        return self._inner.name

    def available(self) -> bool:
        return self._inner.available()

    def generate(self, request):
        if self.calls >= 1:
            raise ProviderUnavailable("eval2_call_cap_reached")
        self.calls += 1
        return self._inner.generate(request)


def no_retry_registry() -> AgentRegistry:
    """In-Memory-Kopie der Registry mit max_retries=0 für das A1-Profil.

    Strikt restriktiver als der Contract (max_retries=1); die YAML bleibt
    unangetastet, das lru-gecachte Original wird nicht mutiert.
    """
    base = get_agent_registry()
    profile = base.profile(PROFILE)
    patched = dataclasses.replace(
        profile,
        invocation_limits={**profile.invocation_limits, "max_retries": 0},
    )
    return AgentRegistry(
        base.model_routes, base.agents, {**base.profiles, PROFILE: patched}
    )


def _target_route_model(target_route_provider: str) -> str | None:
    """model_id der A1-Route, die auf den Ziel-Provider zeigt (primary oder
    fallback) — für den Fall, dass kein UsageRecord entstand."""
    registry = get_agent_registry()
    profile = registry.profile(PROFILE)
    for route_key in (profile.primary_model, profile.fallback_model):
        if route_key and registry.route(route_key).provider == target_route_provider:
            return registry.route(route_key).model_id
    return None


def _seed_project_and_run(db, id_prefix: str) -> tuple[str, str]:
    project_id = f"{id_prefix}-project"
    db.add(
        Project(
            project_id=project_id,
            workspace_id=WS,
            title="F1 QUALIMON (EVAL.2 Real-Smoke, synthetisch)",
            description="Synthetischer F1-abgeleiteter Real-Provider-Smoke.",
            funding_instrument_profile_id=(
                "innosuisse_innovation_project_with_implementation_partner"
            ),
            data_classification=dict(F1_SMOKE_CLASSIFICATION),
            created_by=ACTOR,
            status="draft",
        )
    )
    run_id = f"{id_prefix}-run"
    db.add(
        AnalysisRun(
            run_id=run_id, project_id=project_id, workspace_id=WS,
            created_by=ACTOR, status="completed",
            current_stage="finalize_run", progress_percent=100,
            processing_mode="cloud_assisted",
            effective_data_classification=dict(F1_SMOKE_CLASSIFICATION),
            snapshot_versions={},
        )
    )
    db.flush()
    return project_id, run_id


def run_llm_case(db, provider: str, *, adapter=None) -> dict:
    """Genau ein realer LLM-Call über gateway.invoke (Profil A1).

    ``adapter`` ist nur für Tests injizierbar (Fake); Default sind die echten
    Adapter. Provider-Auswahl per gefiltertem Resolver: nur Routen des
    Ziel-Providers erhalten den Adapter (anthropic ⇒ primary; openai ⇒
    Gateway-Fallback auf die openai-Route).
    """
    target_route_provider = ROUTE_FOR[provider]
    inner = adapter or (
        OpenAIProvider() if provider == "openai" else AnthropicProvider()
    )
    proxy = _SingleCallAdapter(inner)
    project_id, run_id = _seed_project_and_run(db, f"eval2-{provider}")

    resp = invoke(
        db,
        _base_request(run_id, project_id),
        provider_resolver=(
            lambda route: proxy if route.provider == target_route_provider else None
        ),
        registry=no_retry_registry(),
    )
    db.commit()

    totals = run_usage_totals(db, run_id)
    success = isinstance(resp, ModelResponse)
    status = "succeeded" if success else resp.status
    error_code = None if success else resp.error_code

    if proxy.calls == 0:
        raise SmokeFailure(
            f"Kein Provider-Call ausgeführt (status={status}, "
            f"code={error_code}) — Policy/Verfügbarkeit hat blockiert."
        )
    # Metering-Pflicht: Tokens gemessen ODER der Call scheiterte auf
    # Transport-Ebene (HTTP-Fehler/Timeout ⇒ keine Token-Antwort zu metern;
    # Schema-Failures metern seit dem EVAL.2-Gateway-Diff immer).
    if totals["usage_record_count"] == 0 and status not in ("failed", "timed_out"):
        raise SmokeFailure("Metering-Lücke: kein UsageRecord trotz Provider-Call")

    inv = db.scalar(
        select(AgentInvocation).where(AgentInvocation.run_id == run_id)
    )
    latency_ms = inv.latency_ms if inv else None
    # Modell des GEMETERTEN Calls: aus dem UsageRecord — AgentInvocation
    # trägt nach einem Fallback-Versuch die zuletzt versuchte Route, nicht
    # die tatsächlich bediente. Ohne Record (Transportfehler): Ziel-Route
    # aus der Registry ableiten.
    metered = db.scalar(
        select(UsageRecord.model).where(UsageRecord.run_id == run_id)
    )
    model_id = metered or _target_route_model(target_route_provider)

    output_payload = resp.output.model_dump() if success else None
    return {
        "report": {
            "provider": provider,
            "kind": "llm",
            "route_provider": target_route_provider,
            "model": model_id,
            "data_mode": derive_data_mode(
                ai_eval_mode=get_settings().ai_eval_mode, origin="synthetic"
            ),
            "status": status,
            "error_code": error_code,
            "llm_calls": proxy.calls,
            "latency_ms": latency_ms,
            "input_tokens": totals["input_tokens"],
            "output_tokens": totals["output_tokens"],
            "total_tokens": totals["input_tokens"] + totals["output_tokens"],
            "usage_record_count": totals["usage_record_count"],
            "cost_status_counts": totals["cost_status_counts"],
            "cost_chf_priced": totals["cost_chf_priced"],
            "price_table_version": PRICE_TABLE_VERSION,
        },
        _ARTIFACT_KEY: {
            # Nur var/-Eval-Artefakt: validierter Output bzw. sicherer
            # Fehlerdetail-Text — nie in Report/Logs/Audit.
            "llm_output": output_payload,
            "safe_detail": None if success else resp.safe_detail,
        },
    }


def run_web_case(db) -> dict:
    """Genau ein realer Firecrawl-Search über den Research-Chokepoint."""
    settings = get_settings()
    prev_enabled = settings.web_research_enabled
    prev_fake = settings.web_research_fake_provider
    settings.web_research_enabled = True
    # Real-Modus erzwingen — eine lokale .env könnte den Fake aktiviert haben.
    settings.web_research_fake_provider = False
    try:
        project_id, _run_id = _seed_project_and_run(db, "eval2-firecrawl")
        project = db.get(Project, project_id)
        task, operation, _accepted = create_research_task(
            db,
            project=project,
            payload=ResearchTaskCreate(
                purpose="competence_gap_analysis",
                subject_type="topic",
                query_preview=FIRECRAWL_QUERY,
                max_results=3,
                user_confirms_public_professional_purpose=True,
            ),
            actor_user_id=ACTOR,
            task_id="eval2-firecrawl-task",
            operation_id="eval2-firecrawl-op",
        )
        db.commit()  # Executor öffnet eine eigene Session auf derselben DB.
        research_executor(task.research_task_id, operation.operation_id)
        db.expire_all()
        refreshed = db.get(ResearchTask, task.research_task_id)
        if refreshed is None or refreshed.status == "blocked":
            raise SmokeFailure(
                "Firecrawl-Task blockiert: "
                f"code={getattr(refreshed, 'error_code', 'fehlt')}"
            )
        if refreshed.status == "succeeded" and refreshed.provider != "firecrawl":
            raise SmokeFailure(
                f"Web-Provider war nicht firecrawl: {refreshed.provider}"
            )
        tools = tool_usage_by_research_task(db, refreshed.research_task_id)
        provider_usage = refreshed.provider_usage or {}
        return {
            "report": {
                "provider": "firecrawl",
                "kind": "web_search",
                "tool": "search_public_professional_sources",
                "data_mode": derive_data_mode(
                    ai_eval_mode=settings.ai_eval_mode, origin="synthetic"
                ),
                "status": refreshed.status,
                "error_code": refreshed.error_code,
                "search_calls": 1,
                "result_count": refreshed.result_count,
                "latency_ms": provider_usage.get("latency_ms"),
                "credits_used": provider_usage.get("credits_used"),
                "tool_invocations": tools["by_tool"],
                "query_public_safe": FIRECRAWL_QUERY,
            },
            _ARTIFACT_KEY: {
                "provider_usage": provider_usage,
            },
        }
    finally:
        settings.web_research_enabled = prev_enabled
        settings.web_research_fake_provider = prev_fake


def _fmt_cost(report: dict) -> str:
    counts = report.get("cost_status_counts") or {}
    if counts.get("priced"):
        return f"{report['cost_chf_priced']} CHF (nur priced summiert)"
    return "nicht bepreist (unknown_price/not_applicable) — nie als 0 CHF lesen"


def render_report(results: dict[str, dict | None], *, generated_at: str) -> str:
    lines = [
        "# EVAL.2 — Manueller Real Provider Smoke (OpenAI, Anthropic, Firecrawl)",
        "",
        f"*Generiert:* {generated_at} · *Preistabelle:* `{PRICE_TABLE_VERSION}`",
        "",
        "## Pflichthinweise",
        "",
        "- **data_mode = synthetic_eval**: ausschliesslich synthetische",
        "  F1-abgeleitete Daten bzw. eine fixe public-safe Query — **keine",
        "  echten D2-Daten**, keine Partnernamen, keine Budgetzahlen.",
        "- **Azure ist NICHT Teil dieses Smoke-Tests** (kein Adapter im",
        "  App-Code; ProviderPolicy blockiert Azure bis zu einem separaten",
        "  Slice mit institutioneller Freigabe).",
        "- Keine Rohprompts und keine Rohantworten in diesem Report; der",
        "  Provider-Output liegt nur als Eval-Artefakt im git-ignorierten",
        "  `backend/var/evaluation/eval2/`. Keine API-Keys in Report/Logs.",
        "- Kostenstatus ist Mess-Pipeline, keine Kostenrechnung: `cost_chf`",
        "  wird nur über `cost_status='priced'` summiert; die Preistabelle",
        "  enthält weiterhin keine Realpreise (unknown_price ist erwartet).",
        "- Alle Calls liefen über die bestehenden Grenzen (`gateway.invoke`,",
        "  Research-Service → Executor inkl. Firewall/SSRF) — kein Bypass.",
        "",
    ]
    for provider in PROVIDERS:
        entry = results.get(provider)
        title = {"openai": "OpenAI", "anthropic": "Anthropic",
                 "firecrawl": "Firecrawl"}[provider]
        lines.append(f"## {title}")
        lines.append("")
        if entry is None:
            lines.append("**ausstehend** — dieser Smoke wurde noch nicht ausgeführt.")
            lines.append("")
            continue
        r = entry["report"]
        rows: list[tuple[str, object]] = [("data_mode", r["data_mode"])]
        if r["kind"] == "llm":
            rows += [
                ("Modell", r["model"]),
                ("Route", r["route_provider"]),
                ("Status / error_code", f"{r['status']} / {r['error_code']}"),
                ("LLM-Calls", r["llm_calls"]),
                ("input_tokens", r["input_tokens"]),
                ("output_tokens", r["output_tokens"]),
                ("total_tokens", r["total_tokens"]),
                ("Latenz (ms)", r["latency_ms"]),
                ("UsageRecords", r["usage_record_count"]),
                ("cost_status", ", ".join(
                    f"{k}={v}" for k, v in sorted(r["cost_status_counts"].items())
                ) or "—"),
                ("Kosten", _fmt_cost(r)),
            ]
        else:
            tool_rows = r["tool_invocations"].get(
                "search_public_professional_sources", {}
            )
            rows += [
                ("Tool", r["tool"]),
                ("Status / error_code", f"{r['status']} / {r['error_code']}"),
                ("Search-Calls", r["search_calls"]),
                ("Ergebnisse (nach SSRF-Gate)", r["result_count"]),
                ("Latenz (ms)", r["latency_ms"]),
                ("ToolInvocations (Zeilen nach Status)", ", ".join(
                    f"{k}={v}" for k, v in sorted(
                        (tool_rows.get("rows_by_status") or {}).items()
                    )
                ) or "—"),
                ("Credits (nativ)", tool_rows.get("credits_native", 0)),
                ("Credits laut Provider", (
                    r["credits_used"] if r["credits_used"] is not None
                    else "nicht ausgewiesen"
                )),
                ("Query (public-safe, fix)", f"`{r['query_public_safe']}`"),
            ]
        lines += ["| Feld | Wert |", "| --- | --- |"]
        lines += [f"| {k} | {v} |" for k, v in rows]
        lines.append("")
    lines += [
        "---",
        "",
        "Erzeugt mit `python scripts/run_real_provider_smoke.py --case F1",
        "--provider <openai|anthropic|firecrawl>` (Manual Mode: CI ungesetzt,",
        "`RUN_REAL_PROVIDER_SMOKE=true`, `AI_EVAL_MODE=real`), frische",
        "Temp-SQLite-DB pro Lauf, max 1 Call pro Provider.",
        "",
    ]
    return "\n".join(lines)


def _default_results_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "var" / "evaluation" / "eval2"


def _default_report_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "docs" / "evaluation" / "eval2_real_provider_smoke_report.md"
    )


def _load_results(results_dir: Path) -> dict[str, dict | None]:
    results: dict[str, dict | None] = {}
    for provider in PROVIDERS:
        path = results_dir / f"{provider}.json"
        results[provider] = (
            json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "EVAL.2 manueller Real-Provider-Smoke — nur mit explizitem "
            "Manual-Mode-Opt-in; nie in CI."
        )
    )
    parser.add_argument("--case", required=True, choices=["F1"])
    parser.add_argument(
        "--provider", required=True, choices=list(PROVIDERS)
    )
    parser.add_argument("--results-dir", default=str(_default_results_dir()))
    parser.add_argument("--out", default=str(_default_report_path()))
    parser.add_argument(
        "--generated-at",
        default=datetime.now(timezone.utc).date().isoformat(),
    )
    args = parser.parse_args(argv)

    refusal = guard_refusal(
        provider=args.provider, env=os.environ, settings=get_settings()
    )
    if refusal:
        print(f"eval2-smoke: verweigert — {refusal}", file=sys.stderr)
        return 2

    results_dir = Path(args.results_dir)
    result_path = results_dir / f"{args.provider}.json"
    if result_path.exists():
        print(
            f"eval2-smoke: {args.provider} wurde bereits ausgeführt "
            f"({result_path}). Max 1 Smoke-Lauf pro Provider — Datei bewusst "
            "löschen für einen Re-Run.",
            file=sys.stderr,
        )
        return 2

    from app.db.base import Base
    from app.db.session import SessionLocal, engine

    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        _ensure_base_rows(db)
        if args.provider == "firecrawl":
            result = run_web_case(db)
        else:
            result = run_llm_case(db, args.provider)
    except SmokeFailure as exc:
        print(f"eval2-smoke: {exc}", file=sys.stderr)
        return 2
    finally:
        db.close()

    results_dir.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render_report(_load_results(results_dir), generated_at=args.generated_at),
        encoding="utf-8",
    )
    r = result["report"]
    print(f"eval2-smoke: {args.provider}: status={r['status']}"
          f" error_code={r.get('error_code')}")
    print(f"eval2-smoke: Artefakt: {result_path}")
    print(f"eval2-smoke: Report aktualisiert: {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
