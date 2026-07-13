"""Market research Markdown report (RESEARCH.1a).

Whitelist-only: renders planner queries (public-safe) + MarketCandidate metadata. It
NEVER emits raw HTML/fetched page bodies, secrets/API keys, or confidential raw queries.
Snippets are short public candidate excerpts (D0/synthetic) and are clearly marked as
"candidate, not evidence".
"""
from __future__ import annotations

from app.market_research.runner import MarketResearchOutcome

_SNIPPET_MAX = 160


def _snippet(text: str | None) -> str:
    if not text:
        return "—"
    one_line = " ".join(text.split())
    if len(one_line) > _SNIPPET_MAX:
        one_line = one_line[:_SNIPPET_MAX].rstrip() + "…"
    return one_line.replace("|", "/")


def render_report(outcome: MarketResearchOutcome, *, generated_at: str) -> str:
    lines = [
        "# RESEARCH.1 — Market Research Report (F1 synthetic)",
        "",
        f"*Generiert:* {generated_at} · *Case:* `{outcome.case_id}` · "
        f"*data_mode:* `{outcome.data_mode}` · *Provider:* `{outcome.provider or 'fake'}`",
        "",
        "## Pflichthinweise",
        "",
        "- Nur **D0/public** (F1 synthetic). Keine echten D2-Daten, keine Partnernamen, "
        "keine Budgetzahlen, keine personenbezogene Suche.",
        "- **MarketCandidates sind Kandidaten, keine Fakten.** Ein Snippet ist **kein "
        "Beleg** und wird nicht automatisch zu einer Fundstelle (EvidenceAnchor). Keine "
        "automatische TAM/SAM/SOM-Aussage, keine automatische Value-Creation-Änderung.",
        "- **Human Review erforderlich** für jeden Kandidaten vor jeder Weiterverwendung.",
        "- Alle Queries liefen über die bestehende Search Query Firewall + ResearchExecutor "
        "(kein zweiter Webpfad). Firecrawl-Kosten werden als Credits/ToolInvocation gezählt "
        "(keine CHF/USD-Umrechnung).",
        "- Keine Roh-HTML-Inhalte, keine Secrets, keine vertraulichen Rohqueries im Report.",
        "",
        "## Kennzahlen",
        "",
        f"- Geplante Queries: {len(outcome.queries)} (blockiert/übersprungen: "
        f"{outcome.blocked_queries})",
        f"- ResearchResults: {outcome.result_count}",
        f"- ToolInvocations: {outcome.tool_invocation_count} · Credits: "
        f"{outcome.credits_used}",
        f"- Importierte Quellen (SourceDocuments): {outcome.imported_source_count}",
        "",
        "## Geplante Queries (public-safe)",
        "",
        "| purpose | query_text | public_safe | approval_required |",
        "| --- | --- | --- | --- |",
    ]
    for q in outcome.queries:
        lines.append(
            f"| {q.purpose} | {q.query_text.replace('|', '/')} | {q.public_safe} | "
            f"{q.approval_required} |"
        )
    lines += [
        "",
        "## MarketCandidates",
        "",
        "| candidate_type | purpose | status | confidence | rank | title | source_url | "
        "snippet | review |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not outcome.candidates:
        lines.append("| _keine_ | — | — | — | — | — | — | — | — |")
    for c in outcome.candidates:
        lines.append(
            f"| {c.candidate_type} | {c.purpose} | {c.status} | {c.confidence} | "
            f"{c.provider_rank if c.provider_rank is not None else '—'} | "
            f"{c.title.replace('|', '/')} | {c.source_url} | {_snippet(c.snippet)} | "
            f"{'ja' if c.human_review_required else 'nein'} |"
        )
    lines += [
        "",
        "## Offene Risiken",
        "",
        "- Kandidaten sind unbestätigt; Marktzahlen/Wettbewerber sind Signale, keine Fakten.",
        "- Ein Import als D0-Quelle erfolgt nur über den bestehenden Import-/Review-Prozess "
        "(nicht in diesem Slice).",
        "- Realer Firecrawl-Lauf ist manuell/env-gated; dieser Report kann im Fake-Modus "
        "erzeugt worden sein (siehe Provider oben).",
        "",
        "---",
        "",
        "Erzeugt mit `python scripts/run_market_research_f1.py` (Fake default; realer "
        "Firecrawl nur env-gated, nie in CI). MarketCandidates brauchen Human Review.",
        "",
    ]
    return "\n".join(lines)
