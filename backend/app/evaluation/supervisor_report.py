"""EVAL.4 — Supervisor Evaluation Report für den Integrated Draft Run (F1 synthetic).

Reine Aggregations-Funktion über bereits vorhandene, whitelist-sichere Daten — **kein
neuer Provider-Call, kein Netzwerkzugriff, keine DB-Session**. Liest die R5.9-REAL-Envelopes
(``{"report": {...whitelist...}, "artifact": {...roh...}}``) aus
``backend/var/evaluation/r5_9_real/{provider}.json`` (`_load_results`/`_default_results_dir`,
wiederverwendet aus ``integrated_draft_real.py``) und liest **ausschliesslich**
``entry["report"]`` — der ``artifact``-Teil (Rohtext/volle AIProposal) bleibt strukturell
aussen vor. Damit ist "kein Provider-Call möglich" durch Konstruktion erfüllt: die
Renderfunktion hat schlicht keinen Import-Pfad zu einem Provider-Adapter oder Gateway.

Research-Kennzahlen (Sektion 5) zitieren die bereits committeten RESEARCH.1/2-Reports als
feste Zahlen (nicht zur Laufzeit neu geparst) plus die tatsächlich vom Integrated-Draft-Lauf
konsumierten Kandidaten (aus ``research_summary`` je Envelope).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from app.agents import a2_fields
from app.evaluation.integrated_draft_real import PROVIDERS, _default_results_dir, _load_results
from app.registry.loader import get_registry

_QUALITY_CRITERIA = (
    "field_fit", "specificity", "factuality", "missing_input_handling", "language_quality",
)

# Feste Zweck-Beschreibung je Feld (Dokumentation, nicht aus Laufzeitdaten abgeleitet).
_PURPOSE: dict[str, str] = {
    "INTRO.APP.NAME": "Antragstitel — deterministisch aus dem Projekttitel.",
    "INTRO.APP.NAME_EN": "Englischer Antragstitel — deterministisch aus F1-Stammdaten, "
                         "keine automatische Übersetzung.",
    "INTRO.APP.ABSTRACT": "Öffentliche Kurzfassung des Vorhabens und Innovationsziels.",
    "INTRO.APP.EXECUTIVE_SUMMARY": "Ausführlichere Zusammenfassung: Ausgangslage, "
                                    "Innovationsziel, geplanter Nutzen.",
    "ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS": "Erläuterung zur finanziellen "
                                                          "Unabhängigkeit der Partner.",
    "VC.BUSINESS_TARGETS_MODEL.EDITOR": "Wertschöpfung, Geschäftsmodell und Markt — "
                                         "konsumiert advisory Market-Research-Kontext.",
    "SOL.INNOVATION_SOLUTION.EDITOR": "Stand der Technik, Neuheit, Ziele, Vorarbeiten, "
                                       "Partner-Eignung — konsumiert advisory "
                                       "Partner-Research-Kontext.",
    "PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION": "Erläuterung der geplanten "
                                                "Management-Stunden.",
}


def _routing_rows(results: dict[str, dict]) -> list[dict]:
    """Field/Agent/Provider/Modell/Modus/Purpose je Feld (registry-getrieben, nie
    hardcodiert dupliziert)."""
    observed: dict[str, dict[str, str]] = {}
    research_used: dict[str, bool] = {}
    for provider, entry in results.items():
        for f in entry["report"]["fields"]:
            observed.setdefault(f["field_id"], {})[provider] = (
                f"{f['provider']}/{f['model']}" if f["provider"] else "—"
            )
        rs = entry["report"].get("research_summary") or {}
        if rs.get("market", {}).get("used"):
            research_used["VC.BUSINESS_TARGETS_MODEL.EDITOR"] = True
        if rs.get("partner", {}).get("used"):
            research_used["SOL.INNOVATION_SOLUTION.EDITOR"] = True

    rows = []
    for field in get_registry().m6_draft_fields():
        config = a2_fields.resolve_field_config(field.field_id)
        if config is None:
            agent, mode = "deterministisch (Template)", "Deterministic"
        elif research_used.get(field.field_id):
            agent, mode = config.profile_id, "LLM + Research-Kontext (advisory)"
        else:
            agent, mode = config.profile_id, "LLM"
        provider_models = observed.get(field.field_id, {})
        rows.append({
            "field_id": field.field_id,
            "agent": agent,
            "mode": mode,
            "providers": "; ".join(
                f"{p}: {m}" for p, m in sorted(provider_models.items())
            ) or "—",
            "purpose": _PURPOSE.get(field.field_id, "—"),
        })
    return rows


def _fmt_counts(counts: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in sorted((counts or {}).items())) or "—"


def _executive_summary(results: dict[str, dict]) -> list[str]:
    lines = [
        "## 1. Executive Summary", "",
        "- **Fall:** F1 synthetic (D0 public/synthetic) — Innosuisse Innovation Project "
        "mit Umsetzungspartner. Keine echten D2-Daten, kein echter Antrag.",
    ]
    providers_present = [p for p in PROVIDERS if p in results]
    lines.append(
        f"- **Provider-Modus:** {', '.join(providers_present) or '—'} (real, manueller "
        "Opt-in, R5.9-REAL/R5.9b) — zusätzlich existiert eine deterministische "
        "Fake-Baseline (R5.9, `r5_9_integrated_draft_run_report.md`)."
    )
    for provider in providers_present:
        r = results[provider]["report"]
        us = r["usage_summary"]
        n_fields = len(r["fields"])
        n_ok = sum(1 for f in r["fields"] if f["status"] != "failed")
        lines.append(
            f"- **{provider}:** {n_ok}/{n_fields} Felder ohne `failed`-Status · "
            f"total_tokens={us.get('total_tokens', 0)} · "
            f"cost_status={_fmt_counts(us.get('cost_status_counts', {}))}."
        )
    lines += [
        "- **Kernlimitationen:** OpenAI (gpt-5.4) lieferte für "
        "`SOL.INNOVATION_SOLUTION.EDITOR` initial einen strukturell unvollständigen "
        "Entwurf (Feldregel `mandatory_structure_missing`, kein Schema-Fehler) — "
        "Anthropic liefert für dieses Feld vollständig und dient als dokumentierter "
        "Demo-Default (R5.9b). Kosten sind `unknown_price` (Preistabelle bewusst leer). "
        "Kein automatischer Auto-Accept, keine automatische Einreichung, keine "
        "Förderzusage.",
        "",
    ]
    return lines


def _agent_routing_section(results: dict[str, dict]) -> list[str]:
    lines = [
        "## 2. Agent/Task Routing", "",
        "| field_id | Agent (Profil) | Provider/Modell (beobachtet) | Modus | Purpose |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in _routing_rows(results):
        lines.append(
            f"| {row['field_id']} | {row['agent']} | {row['providers']} | {row['mode']} | "
            f"{row['purpose']} |"
        )
    lines.append("")
    return lines


def _integrated_draft_result_section(results: dict[str, dict]) -> list[str]:
    lines = ["## 3. Integrated Draft Result", ""]
    for provider in PROVIDERS:
        entry = results.get(provider)
        if entry is None:
            continue
        lines += [
            f"### Provider: {provider}", "",
            "| field_id | status | human_review_required | missing_inputs |",
            "| --- | --- | --- | --- |",
        ]
        for f in entry["report"]["fields"]:
            lines.append(
                f"| {f['field_id']} | {f['status']} | "
                f"{'ja' if f['human_review_required'] else 'nein'} | "
                f"{f['missing_inputs_count']} |"
            )
        lines.append("")
    return lines


def _token_cost_section(results: dict[str, dict]) -> list[str]:
    lines = ["## 4. Token & Cost Summary", ""]
    for provider in PROVIDERS:
        entry = results.get(provider)
        if entry is None:
            continue
        r = entry["report"]
        lines += [
            f"### Provider: {provider}", "",
            "| field_id | tokens in/out/total | latency_ms | cost_status |",
            "| --- | --- | --- | --- |",
        ]
        for f in r["fields"]:
            tokens = (
                f"{f['input_tokens'] if f['input_tokens'] is not None else '—'}/"
                f"{f['output_tokens'] if f['output_tokens'] is not None else '—'}/"
                f"{f['total_tokens'] if f['total_tokens'] is not None else '—'}"
            )
            lines.append(
                f"| {f['field_id']} | {tokens} | "
                f"{f['latency_ms'] if f['latency_ms'] is not None else '—'} | "
                f"{f['cost_status'] or '—'} |"
            )
        us = r["usage_summary"]
        lines += [
            "",
            f"- Total: input={us.get('input_tokens', 0)} · "
            f"output={us.get('output_tokens', 0)} · total={us.get('total_tokens', 0)} "
            f"tokens · UsageRecords={us.get('usage_record_count', 0)}",
            f"- cost_status counts: {_fmt_counts(us.get('cost_status_counts', {}))}. "
            "**unknown_price** bedeutet: kein Eintrag in der (bewusst leeren) "
            "Preistabelle — **niemals** als \"0 CHF/gratis\" lesen. Ein `priced`-Betrag "
            "würde nur erscheinen, wenn die Preistabelle einen Owner-genehmigten "
            "Preis für (Provider, Modell) enthält — aktuell nicht der Fall.",
            "",
        ]
    return lines


def _research_summary_section(results: dict[str, dict]) -> list[str]:
    lines = [
        "## 5. Research Summary", "",
        "- **Market Research (RESEARCH.1)**: 5 geplante Queries, 15 ResearchResults, "
        "10 ToolInvocations, 0 importierte Quellen — siehe "
        "`research1_market_report_F1.md`.",
        "- **Partner Research (RESEARCH.2)**: 5 geplante Queries, 15 ResearchResults, "
        "10 ToolInvocations, 15 PartnerCandidates — siehe "
        "`research2_partner_report_F1.md`.",
        "",
        "**Im Integrated Draft Run konsumierter Research-Kontext (je Provider):**", "",
    ]
    for provider in PROVIDERS:
        entry = results.get(provider)
        if entry is None:
            continue
        rs = entry["report"].get("research_summary") or {}
        for key, label in (("market", "Market (VC)"), ("partner", "Partner (SOL)")):
            rc = rs.get(key, {})
            lines.append(
                f"- {provider} · {label}: genutzt={'ja' if rc.get('used') else 'nein'}, "
                f"candidates={rc.get('candidates', 0)}, "
                f"imported_sources={rc.get('imported_sources', 0)}"
            )
    lines += [
        "",
        "- **ResearchCandidates/Snippets sind advisory, keine Fakten und keine "
        "Evidence.** Sie werden nie automatisch als `evidence_anchor_ids` zitiert.",
        "",
    ]
    return lines


def _quality_assessment_section(results: dict[str, dict]) -> list[str]:
    lines = [
        "## 6. Quality Assessment Table", "",
        "Platzhalter — **wird nicht von Claude/der KI bewertet**, nur von menschlichen "
        "Reviewern anhand von "
        "[agent_quality_scoring_template.md](agent_quality_scoring_template.md) "
        "ausgefüllt.", "",
    ]
    for provider in PROVIDERS:
        entry = results.get(provider)
        if entry is None:
            continue
        lines += [
            f"### Provider: {provider}", "",
            "| field_id | field_fit | specificity | factuality | "
            "missing_input_handling | language_quality | reviewer_notes |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for f in entry["report"]["fields"]:
            lines.append(
                f"| {f['field_id']} | TODO | TODO | TODO | TODO | TODO | TODO |"
            )
        lines.append("")
    return lines


_SAFETY_GOVERNANCE = [
    "## 7. Safety/Governance", "",
    "- **Kein Auto-Submit**: keine automatische Innolink-/Portal-Einreichung.",
    "- **Kein Auto-Accept**: jeder Feldvorschlag erfordert explizite menschliche "
    "Annahme/Ablehnung/Bearbeitung.",
    "- **Human Review Pflicht** für jeden KI-generierten Feldvorschlag "
    "(`human_review_required=true`).",
    "- **Keine Rohprompts, keine Systemmessages, keine API-Keys** in diesem Report — "
    "nur Feldentwürfe (Produktoutput) und Metadaten.",
    "- Nur synthetische F1-Daten — keine echten D2-Daten, keine echten Partnernamen, "
    "keine echten Budgetzahlen.",
    "- **Keine Förderzusage** und keine implizite Aussage zur Bewilligungswahrscheinlichkeit.",
    "",
]

_LIMITATIONS = [
    "## 8. Limitations", "",
    "- Nur die 8 aktuell unterstützten Innolink-Felder (`registry.m6_draft_fields()`).",
    "- Nur der synthetische F1-Fall — keine Aussage über reale Antragsdaten.",
    "- Preise können `unknown_price` sein (Preistabelle bewusst leer, kein "
    "Owner-genehmigter Preis eingetragen).",
    "- ResearchCandidates sind nie Evidence — auch nicht bei hoher `confidence`.",
    "- OpenAI zeigte für Solution eine Struktur-Lücke (jetzt via Anthropic-Demo-Default "
    "dokumentiert umgangen, R5.9b) — keine dauerhafte Prompt-/Contract-Änderung nötig, "
    "aber weiterhin als bekannte Provider-Eigenschaft zu beobachten.",
    "- **Die finale Einreichungsverantwortung bleibt beim Menschen** — dieser Report "
    "ersetzt keine fachliche/rechtliche Prüfung.",
    "",
]


def render_supervisor_report(results: dict[str, dict], *, generated_at: str) -> str:
    """Whitelist-Report über bereits vorhandene R5.9-REAL-Envelopes — liest nur
    ``entry['report']`` je Provider, nie ``entry['artifact']``."""
    lines = [
        "# EVAL.4 — Supervisor Evaluation Report (Integrated Draft, F1 synthetic)",
        "", f"*Generiert:* {generated_at}", "",
    ]
    lines += _executive_summary(results)
    lines += _agent_routing_section(results)
    lines += _integrated_draft_result_section(results)
    lines += _token_cost_section(results)
    lines += _research_summary_section(results)
    lines += _quality_assessment_section(results)
    lines += _SAFETY_GOVERNANCE
    lines += _LIMITATIONS
    lines += [
        "---", "",
        "Erzeugt mit `python scripts/run_supervisor_report.py` aus den bestehenden "
        "R5.9-REAL-Artefakten (`backend/var/evaluation/r5_9_real/*.json`, "
        "git-ignoriert). Kein neuer Provider-Call.", "",
    ]
    return "\n".join(lines)


def _default_report_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "docs" / "evaluation" / "supervisor_eval_report.md"
    )


def main() -> int:
    results = _load_results(_default_results_dir())
    if not results:
        print(
            "supervisor-report: keine R5.9-REAL-Artefakte gefunden in "
            f"{_default_results_dir()} — zuerst "
            "scripts/run_integrated_draft_real.py ausführen.",
            file=sys.stderr,
        )
        return 2
    out = _default_report_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render_supervisor_report(
            results, generated_at=datetime.now(timezone.utc).date().isoformat()
        ),
        encoding="utf-8",
    )
    print(f"supervisor-report: geschrieben nach {out} (Provider: {', '.join(results)})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
