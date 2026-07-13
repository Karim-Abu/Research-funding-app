"""Partner research Markdown report (RESEARCH.2).

Whitelist-only: renders planner queries (public-safe) + PartnerCandidate metadata. It
NEVER emits raw HTML/fetched page bodies, secrets/API keys, or confidential raw queries.
Every candidate is a "potential fit", never a confirmed fact, eligibility guarantee, or
best-partner claim — no automatic contact is implied anywhere.
"""
from __future__ import annotations

from app.partner_research.runner import PartnerResearchOutcome

_SNIPPET_MAX = 160


def _snippet(text: str | None) -> str:
    if not text:
        return "—"
    one_line = " ".join(text.split())
    if len(one_line) > _SNIPPET_MAX:
        one_line = one_line[:_SNIPPET_MAX].rstrip() + "…"
    return one_line.replace("|", "/")


def render_report(outcome: PartnerResearchOutcome, *, generated_at: str) -> str:
    lines = [
        "# RESEARCH.2 — Partner Research Report (F1 synthetic)",
        "",
        f"*Generiert:* {generated_at} · *Case:* `{outcome.case_id}` · "
        f"*data_mode:* `{outcome.data_mode}` · *Provider:* `{outcome.provider or 'fake'}`",
        "",
        "## Pflichthinweise",
        "",
        "- Nur **D0/public** (F1 synthetic). Keine echten D2-Daten, keine Partnernamen aus "
        "vertraulichen Projekten, keine Budgetzahlen, keine personenbezogene Suche.",
        "- **PartnerCandidates sind eine mögliche fachliche Passung, keine bestätigten "
        "Fakten und kein \"bester Partner\".** Kein Beleg, keine Eignungsprüfung, keine "
        "Innosuisse-Förderfähigkeit oder Beitragsberechtigung bestätigt.",
        "- **Kein automatischer Kontakt** — es werden keine E-Mails versendet, keine "
        "Formulare ausgefüllt, keine Scraping-Profile von Einzelpersonen erstellt.",
        "- **Keine automatische Partneranlage** — es wird keine `Partner`-Datenbankzeile "
        "erstellt; jeder Kandidat erfordert menschliche Prüfung.",
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
        f"- PartnerCandidates: {len(outcome.candidates)}",
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
        "## PartnerCandidates",
        "",
        "| candidate_type | organization | country_or_region | confidence | "
        "potential_project_role | evidence_url | snippet | review |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not outcome.candidates:
        lines.append("| _keine_ | — | — | — | — | — | — | — |")
    for c in outcome.candidates:
        lines.append(
            f"| {c.candidate_type} | {c.organization.replace('|', '/')} | "
            f"{c.country_or_region or '—'} | {c.confidence} | "
            f"{c.potential_project_role.replace('|', '/')} | {c.evidence_url} | "
            f"{_snippet(c.evidence_snippet)} | {c.status} |"
        )
    lines += [
        "",
        "## Offene Limitations",
        "",
        "- Kandidaten sind unbestätigt; Organisations-/Standortangaben sind nicht "
        "verifiziert.",
        "- Keine Eignungsprüfung, keine Innosuisse-Förderfähigkeit oder "
        "Beitragsberechtigung bestätigt.",
        "- Kein Kontakt aufgenommen; eine Kontaktaufnahme erfolgt ausschliesslich manuell "
        "nach menschlicher Prüfung.",
        "- **Human Review erforderlich** für jeden Kandidaten vor jeder Weiterverwendung.",
        "",
        "---",
        "",
        "Erzeugt mit `python scripts/run_partner_research_f1.py` (Fake default; realer "
        "Firecrawl nur env-gated, nie in CI). PartnerCandidates brauchen Human Review.",
        "",
    ]
    return "\n".join(lines)
