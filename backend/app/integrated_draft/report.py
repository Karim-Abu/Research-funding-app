"""Integrated draft run Markdown report (R5.9).

Whitelist-only: renders the DraftPackage field statuses, short draft previews (the draft
is the generated output — allowed), usage/token/latency numbers, and research-context
usage. It NEVER emits raw prompts, internal system instructions, secrets/API keys, or
private project/partner data. No price values (cost_status only).
"""
from __future__ import annotations

from app.integrated_draft.package import DraftPackage, FieldDraftItem

_PREVIEW_MAX = 200


def _preview(text: str | None) -> str:
    if not text:
        return "—"
    one_line = " ".join(text.split())
    if len(one_line) > _PREVIEW_MAX:
        one_line = one_line[:_PREVIEW_MAX].rstrip() + "…"
    return one_line.replace("|", "/")


def _num(value: int | None) -> str:
    return "—" if value is None else str(value)


def render_report(package: DraftPackage, *, generated_at: str) -> str:
    lines = [
        "# R5.9 — Integrated Draft Run Report (F1 synthetic)",
        "",
        f"*Generiert:* {generated_at} · *Case:* `{package.case_id}` · "
        f"*data_mode:* `{package.data_mode}` · *provider_mode:* `{package.provider_mode}`",
        "",
        "## 1. Case Summary",
        "",
        f"- case_id: `{package.case_id}` · project_id: `{package.project_id}` · "
        f"run_id: `{package.run_id}`",
        f"- provider_mode: `{package.provider_mode}` · data_mode: `{package.data_mode}` · "
        f"erzeugt: {package.created_at}",
        f"- Felder im Paket: {len(package.fields)} · **Human Review erforderlich: ja** "
        "(kein Auto-Accept, kein automatisches Submit, nicht copy-ready).",
        "",
        "## 2. Field Summary",
        "",
        "| field_id | status | missing_inputs | human_review |",
        "| --- | --- | --- | --- |",
    ]
    for f in package.fields:
        lines.append(
            f"| {f.field_id} | {f.status} | {len(f.missing_inputs)} | "
            f"{'ja' if f.human_review_required else 'nein'} |"
        )

    lines += ["", "## 3. Generated Draft Preview", ""]
    for f in package.fields:
        lines.append(f"**{f.field_id}** ({f.status})")
        lines.append("")
        lines.append(f"> {_preview(f.suggestion_text)}")
        if f.missing_inputs:
            gaps = ", ".join(mi.get("label", "?") for mi in f.missing_inputs)
            lines.append(f">")
            lines.append(f"> _missing_inputs: {gaps}_")
        lines.append("")

    lines += [
        "## 4. Usage Summary",
        "",
        "| field_id | input_tokens | output_tokens | total_tokens | latency_ms | cost_status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for f in package.fields:
        lines.append(
            f"| {f.field_id} | {_num(f.input_tokens)} | {_num(f.output_tokens)} | "
            f"{_num(f.total_tokens)} | {_num(f.latency_ms)} | {f.cost_status or '—'} |"
        )
    us = package.usage_summary
    lines += [
        "",
        f"- Total: input={us.get('input_tokens', 0)} · output={us.get('output_tokens', 0)} "
        f"· total={us.get('total_tokens', 0)} tokens · UsageRecords="
        f"{us.get('usage_record_count', 0)}",
        f"- cost_status counts: {us.get('cost_status_counts', {})} "
        "(Fake-Provider ⇒ keine Preiswerte).",
        "",
        "## 5. Research Usage",
        "",
        "| Kontext | genutzt | ResearchCandidates | importierte D0/public-Quellen |",
        "| --- | --- | --- | --- |",
    ]
    for key, label in (("market", "Market (VC)"), ("partner", "Partner (SOL)")):
        rc = package.research_summary.get(key, {})
        lines.append(
            f"| {label} | {'ja' if rc.get('used') else 'nein'} | "
            f"{rc.get('candidates', 0)} | {rc.get('imported_sources', 0)} |"
        )
    lines += [
        "",
        "- ResearchCandidates/Snippets sind **advisory, keine Fakten und keine Evidence**; "
        "ihre IDs erscheinen nie in `used_anchor_ids`.",
        "",
        "## 6. Quality Notes",
        "",
        "- Jeder LLM-Feldvorschlag erfordert **menschliche Prüfung**; nichts ist automatisch "
        "übernommen, freigegeben oder copy-ready.",
        "- Fehlende Markt-/SOTA-/Baseline-/Partner-/Budgetangaben erscheinen als "
        "`missing_inputs`/Platzhalter — keine erfundenen Werte.",
        "- Marktzahlen/Partner-Fit aus Research-Kontext sind Kandidaten, keine bestätigten "
        "Aussagen. **Keine Förderzusage.**",
        "",
        "## 7. Limitations",
        "",
        "- Synthetischer F1-Demo-Lauf (Fake-Provider); **keine** finale Einreichung.",
        "- **Nicht** automatisch copy-ready; Evidenz-/Faktenkorrektheit muss geprüft werden.",
        "- Budget/Eligibility/Policy bleiben deterministisch und sind nicht Teil dieses Laufs.",
        "",
        "---",
        "",
        "Erzeugt mit `python scripts/run_integrated_draft_f1.py --provider fake` (Fake default; "
        "realer Provider erst im R5.9-REAL-Ticket). Feldvorschläge brauchen Human Review.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report", "DraftPackage", "FieldDraftItem"]
