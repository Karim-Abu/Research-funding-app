"""R5.9-REAL — Manueller Real-Provider Integrated Draft Run (F1 synthetic).

Fährt den bestehenden Integrated-Draft-Orchestrator (R5.9,
``app.integrated_draft.runner.run_integrated_draft``) unverändert für alle 6 A2-Felder
gegen einen erzwungenen echten Provider (OpenAI oder Anthropic) über die bestehende
Grenze ``run_a2_field_drafting`` → ``gateway.invoke`` und misst Provider/Modell/Tokens/
Latenz/cost_status/usage_record_id je Feld. Die zwei Namensfelder (NAME/NAME_EN) bleiben
deterministisch (kein LLM). Kein CI-Test, kein Produktivlauf.

Manual Mode — reale Calls nur wenn ALLE Guards erfüllt sind (``guard_refusal``,
wiederverwendet aus EVAL.2): ``CI`` nicht gesetzt, ``RUN_REAL_PROVIDER_SMOKE=true``,
``AI_EVAL_MODE=real``, abgeleiteter ``data_mode == synthetic_eval``, Provider explizit,
API-Key vorhanden. Max 1 Lauf pro Provider (Artefakt-Existenz). Der Provider wird über
einen Route-Filter je Feld erzwungen (``_CountingAdapter``, wiederverwendet aus R5.5-REAL);
jedes A2-Profil ist zusätzlich durch sein eigenes ``max_per_run``/``max_retries`` gedeckelt
(bestehender Cost-Guard, R5.9-Kind-Projekt-Architektur — unverändert).

Daten: F1-abgeleitete synthetische D0-Variante (public/synthetic). Keine echten D2-Daten,
keine Partnernamen, keine Budgetzahlen. Roh-Outputs (suggested_text, AIProposal, rohe
Provider-Antworten) NUR als Eval-Artefakt im git-ignorierten
``backend/var/evaluation/r5_9_real/`` — nie in Report/Logs/Audit.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.agents import a2_fields
from app.agents.providers.anthropic import AnthropicProvider
from app.agents.providers.openai import OpenAIProvider
from app.agents.registry import get_agent_registry
from app.config.settings import get_settings
from app.db.models import Project, ResearchResult, ResearchTask
from app.evaluation.field_real_smoke import _CountingAdapter
from app.evaluation.pricing import PRICE_TABLE_VERSION
from app.evaluation.real_smoke import ROUTE_FOR, _ARTIFACT_KEY, guard_refusal
from app.evaluation.usage_smoke import ACTOR, F1_SMOKE_CLASSIFICATION, WS, SmokeFailure, _ensure_base_rows
from app.integrated_draft.report import _preview
from app.integrated_draft.runner import run_integrated_draft

PROVIDERS = ("openai", "anthropic")

# Verbatim from the F1 goldstandard case (docs/evaluation/cases/F1_synthetic_case.md,
# "2. INTRO.APP.NAME_EN", status: present) — not invented, not translated here.
_TITLE_DE = "F1 QUALIMON — KI-gestützte Qualitätsüberwachung (R5.9-REAL, synthetisch)"
_TITLE_EN = "QUALIMON — AI-based Quality Monitoring for Production Lines"
_MARKET_PURPOSE = "market_comparison"
_PARTNER_PURPOSE = "partner_research_org_topic"


def _seed_base_project(db, *, classification: dict | None = None) -> Project:
    project_id = "r5_9_real-" + uuid.uuid4().hex[:8]
    project = Project(
        project_id=project_id, workspace_id=WS, title=_TITLE_DE,
        description="Synthetischer F1-abgeleiteter Real-Provider-Integrated-Draft-Lauf "
                     "(D0/public).",
        innovation_field="Industrial AI / Manufacturing Quality",
        funding_instrument_profile_id=(
            "innosuisse_innovation_project_with_implementation_partner"
        ),
        data_classification=dict(classification or F1_SMOKE_CLASSIFICATION),
        created_by=ACTOR, status="draft",
    )
    db.add(project)
    db.flush()
    return db.get(Project, project_id)


def _add_candidate(db, project, *, purpose: str, title: str) -> None:
    task_id = "rt-" + uuid.uuid4().hex[:8]
    db.add(ResearchTask(
        research_task_id=task_id, project_id=project.project_id,
        workspace_id=project.workspace_id, created_by=ACTOR, purpose=purpose,
        subject_type="topic", query_text="öffentliche Themen-/Organisationssuche",
        normalized_query_hash="qh", status="succeeded",
    ))
    db.add(ResearchResult(
        result_id="rr-" + uuid.uuid4().hex[:8], research_task_id=task_id,
        workspace_id=project.workspace_id, source_url="https://research.example.org/r/1",
        title=title, snippet="Öffentlich zugänglicher Auszug (Snippet ist kein Beleg).",
        provider_rank=1, status="candidate",
    ))


def _seed_context(db, field_id: str, project: Project) -> None:
    """Advisory market/partner research context onto the VC/SOL child projects (R5.7).
    Direct synthetic rows — no queries, no Firecrawl."""
    if field_id == "VC.BUSINESS_TARGETS_MODEL.EDITOR":
        _add_candidate(db, project, purpose=_MARKET_PURPOSE,
                        title="Öffentliche Marktquelle: Anbieter & Wettbewerber")
    elif field_id == "SOL.INNOVATION_SOLUTION.EDITOR":
        _add_candidate(db, project, purpose=_PARTNER_PURPOSE,
                        title="Öffentliche Partnerquelle: Forschungslabor Schweiz")
    db.flush()


def _build_resolver_for(provider: str, adapters: dict[str, object] | None = None):
    """Returns (resolver_for, proxies) for ``run_integrated_draft``'s ``resolver_for`` seam.

    Per A2 field, builds a fresh ``_CountingAdapter`` (cap = ``1 + profile.max_retries``,
    force-routed onto ``ROUTE_FOR[provider]`` — blocks cross-provider fallback) wrapping
    either an injected test adapter or a real ``OpenAIProvider``/``AnthropicProvider``.
    ``proxies`` (keyed by field_id) lets the caller read ``.calls``/``.raw_outputs`` after
    the run for metrics/artifact capture.
    """
    target_route = ROUTE_FOR[provider]
    proxies: dict[str, _CountingAdapter] = {}

    def resolver_for(field_id: str):
        config = a2_fields.resolve_field_config(field_id)
        profile = get_agent_registry().profile(config.profile_id)
        limit = 1 + int(profile.invocation_limits.get("max_retries", 0))
        injected = (adapters or {}).get(field_id)
        inner = injected or (
            OpenAIProvider() if provider == "openai" else AnthropicProvider()
        )
        proxy = _CountingAdapter(inner, limit=limit, adapter_name=target_route)
        if injected is not None:
            proxy._hermetic_test_model_id = "fake"
        proxies[field_id] = proxy
        return lambda route: proxy if route.provider == target_route else None

    return resolver_for, proxies


def run_integrated_draft_real(
    db, *, provider: str, adapters: dict[str, object] | None = None,
    classification: dict | None = None,
) -> dict:
    """Run the R5.9 integrated draft against a forced real provider for all 6 A2 fields.

    ``adapters`` injects per-field test doubles (no network); ``classification`` lets
    callers exercise the data-policy/provider-policy gates (e.g. confidential/real_project
    data must be blocked regardless of API keys). Raises ``SmokeFailure`` if not a single
    real call was executed across all A2 fields (policy/availability blocked everything —
    a metering gap, not a legitimate result).
    """
    _ensure_base_rows(db)
    project = _seed_base_project(db, classification=classification)
    resolver_for, proxies = _build_resolver_for(provider, adapters)
    package = run_integrated_draft(
        db, base_project=project, actor_user_id=ACTOR, case_id="F1",
        provider_mode=provider, data_mode="synthetic_eval",
        resolver_for=resolver_for, seed_context=_seed_context, title_en=_TITLE_EN,
        real_eval_confirmation=True,
    )
    db.commit()

    if sum(p.calls for p in proxies.values()) == 0:
        raise SmokeFailure(
            "Kein einziger Provider-Call über alle 6 A2-Felder ausgeführt — "
            "Policy/Verfügbarkeit hat den gesamten Lauf blockiert."
        )

    fields_report, fields_artifact = [], []
    for f in package.fields:
        proxy = proxies.get(f.field_id)
        fields_report.append({
            "field_id": f.field_id, "field_label": f.field_label, "status": f.status,
            "provider": f.provider, "model": f.model,
            "input_tokens": f.input_tokens, "output_tokens": f.output_tokens,
            "total_tokens": f.total_tokens, "latency_ms": f.latency_ms,
            "cost_status": f.cost_status, "usage_record_id": f.usage_record_id,
            "llm_calls": proxy.calls if proxy else 0,
            "missing_inputs_count": len(f.missing_inputs),
            "human_review_required": f.human_review_required,
            "suggestion_preview": _preview(f.suggestion_text),
        })
        fields_artifact.append({
            "field_id": f.field_id, "suggestion_text": f.suggestion_text,
            "ai_proposal": f.ai_proposal,
            "raw_outputs": list(proxy.raw_outputs) if proxy else [],
        })

    return {
        "report": {
            "provider": provider, "case_id": package.case_id,
            "project_id": package.project_id, "run_id": package.run_id,
            "created_at": package.created_at, "data_mode": package.data_mode,
            "price_table_version": PRICE_TABLE_VERSION,
            "fields": fields_report,
            "usage_summary": package.usage_summary,
            "research_summary": package.research_summary,
            "human_review_required": package.human_review_required,
        },
        _ARTIFACT_KEY: {"fields": fields_artifact},
    }


def _fmt_counts(counts: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in sorted((counts or {}).items())) or "—"


_NON_FAILURE_STATUSES = {"generated", "missing_inputs", "deterministic", "skipped"}


def _provider_limitation_notes(results: dict[str, dict]) -> list[str]:
    """Whitelist-safe Limitations-Zeilen: nennt Feld-ID/Provider/Status, nie Rohtext.

    Für jedes Feld, das bei mindestens einem vorhandenen Provider ``failed`` ist: wenn ein
    anderer vorhandener Provider dasselbe Feld erfolgreich liefert, wird dieser als
    Demo-Default benannt; scheitern alle vorhandenen Provider, wird das explizit als offene
    manuelle Prüfung ausgewiesen (kein stiller Ausfall).
    """
    by_field: dict[str, dict[str, str]] = {}
    for provider, entry in results.items():
        for f in entry["report"]["fields"]:
            by_field.setdefault(f["field_id"], {})[provider] = f["status"]
    notes: list[str] = []
    for field_id, statuses in sorted(by_field.items()):
        failing = sorted(p for p, s in statuses.items() if s == "failed")
        if not failing:
            continue
        working = sorted(p for p, s in statuses.items() if s in _NON_FAILURE_STATUSES)
        if working:
            notes.append(
                f"- `{field_id}`: bei {', '.join(failing)} als `failed` beobachtet "
                "(Feld-/Struktur-Regel, z. B. `mandatory_structure_missing` — kein "
                f"Schema-Bug) — {', '.join(working)} liefert hierfür einen vollständigen "
                "Draft und dient als Demo-Default."
            )
        else:
            notes.append(
                f"- `{field_id}`: bei allen ausgeführten Providern "
                f"({', '.join(failing)}) als `failed` beobachtet — kein Demo-Default "
                "verfügbar, manuelle Prüfung nötig."
            )
    return notes


def render_report(results: dict[str, dict], *, generated_at: str) -> str:
    """Whitelist-Report, ein Block je vorhandenem Provider — liest NUR ``entry['report']``;
    das ``artifact`` (Rohoutput) bleibt strukturell aussen vor."""
    lines = [
        "# R5.9-REAL — Real Integrated Draft Report (F1 synthetic)",
        "",
        f"*Generiert:* {generated_at} · *Preistabelle:* `{PRICE_TABLE_VERSION}`",
        "",
    ]
    for provider in PROVIDERS:
        entry = results.get(provider)
        if entry is None:
            continue
        r = entry["report"]
        lines += [f"## Provider: {provider}", "", "### 1. Case Summary", ""]
        lines += [
            f"- case_id: `{r['case_id']}` · project_id: `{r['project_id']}` · "
            f"run_id: `{r['run_id']}`",
            f"- provider: `{provider}` · data_mode: `{r['data_mode']}` · "
            f"erzeugt: {r['created_at']}",
            f"- Felder im Paket: {len(r['fields'])} · **Human Review erforderlich: ja** "
            "(kein Auto-Accept, kein automatisches Submit, nicht copy-ready).",
            "",
            "### 2. Field Summary", "",
            "| field_id | status | provider/model | tokens in/out/total | latency_ms | "
            "cost_status | missing_inputs | human_review |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for f in r["fields"]:
            model = f"{f['provider'] or '—'}/{f['model'] or '—'}"
            tokens = (
                f"{f['input_tokens'] if f['input_tokens'] is not None else '—'}/"
                f"{f['output_tokens'] if f['output_tokens'] is not None else '—'}/"
                f"{f['total_tokens'] if f['total_tokens'] is not None else '—'}"
            )
            lines.append(
                f"| {f['field_id']} | {f['status']} | {model} | {tokens} | "
                f"{f['latency_ms'] if f['latency_ms'] is not None else '—'} | "
                f"{f['cost_status'] or '—'} | {f['missing_inputs_count']} | "
                f"{'ja' if f['human_review_required'] else 'nein'} |"
            )
        lines += ["", "### 3. Draft Preview (KI-generiert — Human Review Pflicht)", ""]
        for f in r["fields"]:
            lines.append(
                f"**{f['field_id']}** ({f['status']}) — "
                "_KI-generierter Entwurf, keine Förderzusage_"
            )
            lines.append("")
            lines.append(f"> {f['suggestion_preview']}")
            lines.append("")
        us = r["usage_summary"]
        lines += [
            "### 4. Usage Summary", "",
            f"- Total: input={us.get('input_tokens', 0)} · "
            f"output={us.get('output_tokens', 0)} · total={us.get('total_tokens', 0)} "
            f"tokens · UsageRecords={us.get('usage_record_count', 0)}",
            f"- cost_status counts: {_fmt_counts(us.get('cost_status_counts', {}))} "
            "(Preistabelle bewusst leer ⇒ unknown_price — nie 0 CHF als gratis lesen).",
            "", "### 5. Research Context", "",
        ]
        rs = r["research_summary"]
        for key, label in (("market", "Market (VC)"), ("partner", "Partner (SOL)")):
            rc = rs.get(key, {})
            lines.append(
                f"- {label}: genutzt={'ja' if rc.get('used') else 'nein'}, "
                f"candidates={rc.get('candidates', 0)}, "
                f"imported_sources={rc.get('imported_sources', 0)}"
            )
        lines += [
            "- ResearchCandidates/Snippets sind advisory, keine Fakten und keine Evidence.",
            "", "### 6. Quality Notes (Platzhalter — manuell auszufüllen)", "",
            "| Feld | field_fit | specificity | factuality | missing_input_handling | "
            "language_quality |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for f in r["fields"]:
            lines.append(
                f"| {f['field_id']} | _TODO_ | _TODO_ | _TODO_ | _TODO_ | _TODO_ |"
            )
        lines.append("")
    lines += [
        "## 7. Limitations", "",
        "- Nur synthetischer F1-Fall (D0 public/synthetic) — keine echten D2-Daten.",
        "- **Keine Förderzusage** und keine Garantie für Copy-Readiness.",
        "- **Keine automatische Einreichung**; jeder Feldvorschlag erfordert Human Review.",
        "- ResearchCandidates sind advisory und gelten nie als Evidence.",
        "- Kostenstatus ist Mess-Pipeline, keine Kostenrechnung (Preistabelle bewusst leer).",
        *_provider_limitation_notes(results),
        "", "---", "",
        "Erzeugt mit `RUN_REAL_PROVIDER_SMOKE=true AI_EVAL_MODE=real python "
        "scripts/run_integrated_draft_real.py --provider <openai|anthropic>` (Manual Mode, "
        "CI ungesetzt), frische Temp-SQLite-DB, Keys aus `backend/.env`, max 1 Lauf pro "
        "Provider.", "",
    ]
    return "\n".join(lines)


def _default_results_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "var" / "evaluation" / "r5_9_real"


def _default_report_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "docs" / "evaluation" / "r5_9_real_integrated_draft_report.md"
    )


def _load_results(results_dir: Path) -> dict:
    results: dict = {}
    for provider in PROVIDERS:
        path = results_dir / f"{provider}.json"
        if path.exists():
            results[provider] = json.loads(path.read_text(encoding="utf-8"))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "R5.9-REAL manueller Real-Provider Integrated Draft Run — nur mit "
            "explizitem Manual-Mode-Opt-in; nie in CI."
        )
    )
    parser.add_argument("--provider", required=True, choices=list(PROVIDERS))
    parser.add_argument("--results-dir", default=str(_default_results_dir()))
    parser.add_argument("--out", default=str(_default_report_path()))
    parser.add_argument(
        "--generated-at", default=datetime.now(timezone.utc).date().isoformat()
    )
    args = parser.parse_args(argv)

    refusal = guard_refusal(
        provider=args.provider, env=os.environ, settings=get_settings()
    )
    if refusal:
        print(f"r5_9_real: verweigert — {refusal}", file=sys.stderr)
        return 2

    results_dir = Path(args.results_dir)
    result_path = results_dir / f"{args.provider}.json"
    if result_path.exists():
        print(
            f"r5_9_real: {args.provider} bereits ausgeführt ({result_path}) — Datei "
            "löschen für einen Re-Run. Übersprungen.", file=sys.stderr,
        )
    else:
        from app.db.base import Base
        from app.db.session import SessionLocal, engine

        Base.metadata.create_all(engine)
        db = SessionLocal()
        try:
            result = run_integrated_draft_real(db, provider=args.provider)
        except SmokeFailure as exc:
            print(f"r5_9_real: {args.provider}: {exc}", file=sys.stderr)
            return 2
        finally:
            db.close()
        results_dir.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        r = result["report"]
        print(
            f"r5_9_real: {args.provider}: fields={len(r['fields'])} "
            f"total_tokens={r['usage_summary'].get('total_tokens', 0)}"
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render_report(_load_results(results_dir), generated_at=args.generated_at),
        encoding="utf-8",
    )
    print(f"r5_9_real: Report aktualisiert: {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
