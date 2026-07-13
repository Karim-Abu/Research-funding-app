"""EVAL.1 — Fake-Usage-Smoke: erzeugt messbare UsageRecords/ToolInvocations.

Nur Fake-Provider (LLM + Web), keine echten API-Calls, keine Secrets. Der
Smoke fährt die PRODUKTIVEN Grenzen (gateway.invoke, research.service →
research_executor) — kein Eval-Bypass, data_mode bleibt rein deskriptiv.

F1-Ableitung (Owner-bestätigt): der kanonische F1-Fall ist confidential +
deterministic_only und erzeugt damit 0 LLM-Calls. Für die Metering-Messung
verwendet der Smoke eine F1-ABGELEITETE synthetische Variante mit
public/synthetic/cloud_assisted (D0) — dokumentiert im Report.

Report-Ausnahme (Owner-genehmigt, Ticket EVAL.1): der deterministische
Report wird nach ``docs/evaluation/eval1_usage_cost_report.md`` committet —
abweichend von der M10-Konvention "Summaries nie nach docs/" (corr 5).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.agents.gateway import ModelRequest, ModelResponse, invoke
from app.agents.providers import FakeProvider
from app.agents.providers.base import ProviderUsage
from app.config.settings import get_settings
from app.contracts.research import ResearchTaskCreate
from app.db.models import AgentInvocation, AnalysisRun, Project, ResearchTask
from app.evaluation.data_mode import derive_data_mode
from app.evaluation.pricing import PRICE_TABLE_VERSION
from app.evaluation.usage import (
    run_usage_totals,
    tool_usage_by_research_task,
    usage_by_agent_task,
)
from app.research.executor import research_executor
from app.research.service import create_research_task

WS = "ws-demo"
ACTOR = "user-anna"
PROFILE = "A1.project_fact_extraction"

# F1-abgeleitete synthetische Stammdaten (kanonischer Fall:
# docs/evaluation/cases/F1_synthetic_case.md; Klassifikation bewusst
# D0-abgeleitet, siehe Modul-Docstring).
F1_TITLE = "F1 QUALIMON (EVAL.1-Ableitung, synthetisch)"
F1_DESCRIPTION = (
    "Synthetischer Evaluationsfall F1 (QUALIMON), abgeleitet für den "
    "Usage-/Cost-Metering-Smoke. Keine realen Projektdaten."
)
F1_SMOKE_CLASSIFICATION = {
    "sensitivity": "public",
    "origin": "synthetic",
    "processing_mode": "cloud_assisted",
    "web_research_mode": "validated_public",
    "nda_applies": False,
}
# Generische, öffentliche D0-Query (Firewall-konform, keine Projektbegriffe).
F1_WEB_QUERY = "ai based quality monitoring for production lines"

# Deterministische Fake-Token-Zahlen pro Run (unterscheidbar in der Tabelle).
_FAKE_USAGES = (
    ProviderUsage(input_tokens=11, output_tokens=22),
    ProviderUsage(input_tokens=13, output_tokens=29),
)


class SmokeFailure(RuntimeError):
    """Fail-closed: der Smoke schreibt keinen Report über einen kaputten Lauf."""


def _base_request(run_id: str, project_id: str) -> ModelRequest:
    return ModelRequest(
        profile_id=PROFILE,
        workspace_id=WS,
        input_payload={
            "run_id": run_id,
            "fragment_ids": ["frag-1"],
            "active_requirement_ids": [],
            "active_field_ids": [],
            "data_classification": {
                "sensitivity": "public",
                "origin": "synthetic",
                "processing_mode": "cloud_assisted",
            },
        },
        classification={
            "sensitivity": "public", "origin": "synthetic", "nda_applies": False,
        },
        processing_mode="cloud_assisted",
        run_id=run_id,
        project_id=project_id,
        allowed_fragment_ids=frozenset({"frag-1"}),
    )


def run_case_f1(
    db,
    *,
    id_prefix: str = "eval1-f1",
    project_title: str = F1_TITLE,
    project_description: str = F1_DESCRIPTION,
    include_web_research: bool = True,
) -> dict:
    """Seeded F1-abgeleitetes Projekt + 2 Runs + Fake-Gateway-Calls (+ Fake-
    Web-Research) und aggregiert die Metering-Resultate. Committet selbst
    (der Research-Executor öffnet eine eigene Session)."""
    project_id = f"{id_prefix}-project"
    db.add(
        Project(
            project_id=project_id,
            workspace_id=WS,
            title=project_title,
            description=project_description,
            funding_instrument_profile_id=(
                "innosuisse_innovation_project_with_implementation_partner"
            ),
            data_classification=dict(F1_SMOKE_CLASSIFICATION),
            created_by=ACTOR,
            status="draft",
        )
    )

    run_ids = []
    for i, usage in enumerate(_FAKE_USAGES, start=1):
        run_id = f"{id_prefix}-run-{i}"
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
        # Fake-Adapter explizit per Resolver injiziert — die Provider-Wahl
        # bleibt beim Gateway; kein Settings-Flag nötig, kein echter Call.
        fake = FakeProvider(usage=usage)
        resp = invoke(
            db, _base_request(run_id, project_id),
            provider_resolver=lambda _route: fake,
        )
        if not isinstance(resp, ModelResponse):
            raise SmokeFailure(
                f"Fake-Gateway-Call für {run_id} fehlgeschlagen: "
                f"{getattr(resp, 'error_code', 'unbekannt')}"
            )
        run_ids.append(run_id)
    db.commit()

    task_id = None
    web_usage = None
    task_provider = None
    if include_web_research:
        settings = get_settings()
        prev_enabled = settings.web_research_enabled
        prev_fake = settings.web_research_fake_provider
        settings.web_research_enabled = True
        settings.web_research_fake_provider = True
        try:
            project = db.get(Project, project_id)
            task, operation, _accepted = create_research_task(
                db,
                project=project,
                payload=ResearchTaskCreate(
                    purpose="competence_gap_analysis",
                    subject_type="topic",
                    query_preview=F1_WEB_QUERY,
                    max_results=3,
                    user_confirms_public_professional_purpose=True,
                ),
                actor_user_id=ACTOR,
                task_id=f"{id_prefix}-task",
                operation_id=f"{id_prefix}-op",
            )
            task_id = task.research_task_id
            db.commit()  # Executor nutzt eine eigene Session auf derselben DB.
            research_executor(task_id, operation.operation_id)
            db.expire_all()
            refreshed = db.get(ResearchTask, task_id)
            if refreshed is None or refreshed.status != "succeeded":
                raise SmokeFailure(
                    "Fake-Web-Research nicht erfolgreich: status="
                    f"{getattr(refreshed, 'status', 'fehlt')}, "
                    f"code={getattr(refreshed, 'error_code', None)}"
                )
            task_provider = refreshed.provider
            if task_provider != "fake":
                raise SmokeFailure(
                    f"Web-Provider war nicht der Fake: {task_provider}"
                )
            web_usage = tool_usage_by_research_task(db, task_id)
        finally:
            settings.web_research_enabled = prev_enabled
            settings.web_research_fake_provider = prev_fake

    latencies = {
        f"{inv.run_id}/{inv.profile_id}": inv.latency_ms
        for inv in db.query(AgentInvocation).filter(
            AgentInvocation.run_id.in_(run_ids)
        )
    }
    return {
        "project_id": project_id,
        "data_mode": derive_data_mode(
            ai_eval_mode=get_settings().ai_eval_mode,
            origin=F1_SMOKE_CLASSIFICATION["origin"],
        ),
        "runs": {rid: run_usage_totals(db, rid) for rid in run_ids},
        "agent_tasks": {rid: usage_by_agent_task(db, rid) for rid in run_ids},
        "web": web_usage,
        "web_provider": task_provider,
        "research_task_id": task_id,
        "exact_latencies_ms": latencies,  # nur stdout, nie im committeten Report
        "price_table_version": PRICE_TABLE_VERSION,
    }


def _latency_bucket(value) -> str:
    # Committeter Report bleibt byte-deterministisch: Wall-Clock-Latenzen
    # werden nur als Messnachweis gebucketed, exakte Werte gehen auf stdout.
    if value is None:
        return "nicht gemessen"
    return "gemessen (< 60000 ms)" if int(value) < 60000 else "gemessen"


def render_report(result: dict, *, generated_at: str | None = None) -> str:
    lines = [
        "# EVAL.1 — Usage-/Cost-Metering Smoke-Report (F1, Fake-Provider)",
        "",
        f"*Generiert:* {generated_at or 'deterministisch (ohne Zeitstempel)'}"
        f" · *Preistabelle:* `{result['price_table_version']}`",
        "",
        "## Pflichthinweise",
        "",
        "- **Fake-/Demo-Provider**: Alle LLM- und Web-Calls liefen über die",
        "  deterministischen Fake-Provider. **Es wurden keine echten API-Calls**",
        "  (OpenAI/Anthropic/Azure/Firecrawl) ausgeführt.",
        "- **Keine Aussage zu realen Modellkosten**: Dieser Report beweist die",
        "  Mess-Pipeline (cost_status), er ist **keine Kostenrechnung**.",
        "- `cost_chf=0.0` bedeutet **nie** automatisch \"kostenlos\": Summen",
        "  werden ausschliesslich über `cost_status='priced'` gebildet;",
        "  `unknown_price`/`not_applicable` tragen nie zu Summen bei.",
        "- Die Preistabelle ist bewusst leer (Owner-Entscheid EVAL.1, keine",
        "  Realpreise); jede künftige Preiszeile braucht source_url +",
        "  last_checked.",
        "",
        "## Abweichungen (dokumentiert)",
        "",
        "- **docs/-Ausnahme**: M10-Konvention schreibt Summaries nur nach",
        "  git-ignoriertem `var/` (\"never to docs/\", corr 5). Dieser eine",
        "  deterministische Pipeline-Nachweis wird gemäss Ticket EVAL.1",
        "  bewusst committet.",
        "- **F1-Ableitung**: Kanonisches F1 ist confidential+deterministic_only",
        "  (0 LLM-Calls). Der Smoke nutzt eine F1-abgeleitete synthetische",
        "  D0-Variante (public/synthetic/cloud_assisted), damit die",
        "  Metering-Pfade (Gateway + Web-Research) real durchlaufen werden.",
        "- **Latenzen**: Wall-Clock-Werte würden den committeten Report bei",
        "  jedem Lauf ändern — sie erscheinen hier nur gebucketed; exakte",
        "  ms-Werte gibt der Smoke auf stdout aus.",
        "",
        f"## data_mode: `{result['data_mode']}`",
        "",
        "Abgeleitetes Label (kein Enforcement; Gates bleiben data_policy ×",
        "provider_policy × policy_matrix).",
        "",
        "## LLM-Calls (Fake-Gateway, Profil A1.project_fact_extraction)",
        "",
        "| run_id | UsageRecords | input_tokens | output_tokens | cost_status | cost_chf (nur priced) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for rid in sorted(result["runs"]):
        t = result["runs"][rid]
        statuses = ", ".join(
            f"{k}={v}" for k, v in sorted(t["cost_status_counts"].items())
        )
        lines.append(
            f"| {rid} | {t['usage_record_count']} | {t['input_tokens']} |"
            f" {t['output_tokens']} | {statuses} | {t['cost_chf_priced']} |"
        )
    lines += [
        "",
        "## Pro agent_task",
        "",
        "| run_id | agent_task | Invocations | Tokens (in/out) | Latenz | cost_statuses |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for rid in sorted(result["agent_tasks"]):
        for row in result["agent_tasks"][rid]:
            lines.append(
                f"| {rid} | {row['agent_task']} | {row['invocation_count']} |"
                f" {row['input_tokens']}/{row['output_tokens']} |"
                f" {_latency_bucket(row['max_latency_ms'])} |"
                f" {', '.join(row['cost_statuses'])} |"
            )
    lines += ["", "## Web-Research (Fake-Provider, Credits nativ)", ""]
    if result["web"] is None:
        lines.append("Kein Web-Research-Teil in diesem Lauf.")
    else:
        lines += [
            f"Research-Task: `{result['research_task_id']}` ·"
            f" Provider: `{result['web_provider']}`",
            "",
            "| tool_id | Zeilen nach Status | Credits (nativ = gezählte ToolInvocations) |",
            "| --- | --- | --- |",
        ]
        for tool_id in sorted(result["web"]["by_tool"]):
            entry = result["web"]["by_tool"][tool_id]
            rows = ", ".join(
                f"{k}={v}" for k, v in sorted(entry["rows_by_status"].items())
            )
            lines.append(f"| {tool_id} | {rows} | {entry['credits_native']} |")
        lines += [
            "",
            "Credits werden als native Einheit gezählt (identische Semantik wie",
            "`research/cost_guard.tool_calls_used`); keine spekulative CHF/USD-",
            "Umrechnung (Owner-Entscheid EVAL.1).",
        ]
    lines += [
        "",
        "---",
        "",
        "Erzeugt mit `python scripts/run_eval_usage_smoke.py --case F1"
        " --provider fake` gegen eine frische Temp-SQLite-DB über die",
        "produktiven Grenzen (`gateway.invoke`, Research-Service/Executor).",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "EVAL.1 Fake-Usage-Smoke: nur --provider fake; echte Provider sind "
            "für diesen Smoke ausgeschlossen."
        )
    )
    parser.add_argument("--case", required=True, choices=["F1"])
    parser.add_argument("--provider", required=True, choices=["fake"])
    parser.add_argument(
        "--out",
        default=str(
            Path(__file__).resolve().parents[3]
            / "docs" / "evaluation" / "eval1_usage_cost_report.md"
        ),
    )
    parser.add_argument(
        "--generated-at", default=None,
        help="Optionaler fixer Zeitstempel; Default: ohne (Byte-Determinismus).",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    if settings.ai_eval_mode == "real":
        print(
            "eval1-smoke: AI_EVAL_MODE=real ist für den Fake-Smoke nicht"
            " zulässig — abgebrochen.",
            file=sys.stderr,
        )
        return 2

    from app.db.base import Base
    from app.db.session import SessionLocal, engine

    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        _ensure_base_rows(db)
        result = run_case_f1(db)
    except SmokeFailure as exc:
        print(f"eval1-smoke: {exc}", file=sys.stderr)
        return 2
    finally:
        db.close()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render_report(result, generated_at=args.generated_at), encoding="utf-8"
    )
    print(f"eval1-smoke: Report geschrieben: {out}")
    print(f"eval1-smoke: exakte Latenzen (ms): {result['exact_latencies_ms']}")
    for rid, totals in sorted(result["runs"].items()):
        print(f"eval1-smoke: {rid}: {totals}")
    return 0


def _ensure_base_rows(db) -> None:
    """Minimale Stammdaten für die frische Smoke-DB (Spiegel der Test-Seeds)."""
    from app.db.models import FundingProfile, User, Workspace

    if db.get(Workspace, WS) is None:
        db.add(Workspace(id=WS, name="Demo Workspace"))
    profile_id = "innosuisse_innovation_project_with_implementation_partner"
    if db.get(FundingProfile, profile_id) is None:
        db.add(FundingProfile(id=profile_id, title="Innosuisse Innovation Project"))
    if db.get(User, ACTOR) is None:
        from app.security.passwords import hash_password

        db.add(
            User(
                id=ACTOR, workspace_id=WS, name="Anna Keller",
                email="anna.keller@example.test",
                password_hash=hash_password("eval1-smoke-local-only"),
                role="lead_admin", display_label="Anna Keller",
            )
        )
    db.commit()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
