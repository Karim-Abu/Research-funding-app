"""Ebene C — Live-Model-Evaluation (Modellqualität, opt-in, nie Pflicht-CI).

Bewertet die Outputs des R5.9-REAL-Laufs (gleicher Eingabetext, gleiche
Rubrik, OpenAI UND Anthropic) mit deterministischen Metriken. Die
GENERIERUNG läuft ausschliesslich über den produktiven Pfad
(``app.evaluation.integrated_draft_real`` → ``run_integrated_draft`` →
``gateway.invoke`` mit Produktiv-Profilen, Prompt-Assets und Adaptern) —
dieses Modul fügt NUR die Auswertung hinzu (keine parallele Provider-Logik,
Harness-Vertrag E.8).

Metriken (rein, einzeln unit-getestet):
- projektspezifische Begriffe erhalten (``terms_preserved``),
- Pflichtunterabschnitte vorhanden (``mandatory_subsections_present``),
- Zeichenlimit eingehalten (``char_limit_respected``),
- keine erfundenen Zahlen (``no_invented_numbers``) und keine erfundenen
  Patentbehauptungen (``no_invented_patents``),
- Review-Notizen/Portalfragen nicht als finale Prosa
  (``no_review_notes_as_prose``),
- KPI-/Angabelücken als offen gekennzeichnet (``kpi_gaps_marked_open``).

Der Human-Rubric-Score (Nützlichkeit/Struktur/Präzision) bleibt ausdrücklich
menschlich (TODO-Tabelle im Report — nie KI-bewertet). Rohe Modelloutputs
bleiben im gitignorierten ``backend/var/evaluation/``; der Report enthält nur
Status, Zählwerte, Modell-IDs und Metrik-Ergebnisse. Nicht durchgeführte
Läufe werden wörtlich als ``not_run`` berichtet — nie als bestanden.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

PROVIDERS = ("openai", "anthropic")
PASS, FAIL, NOT_RUN = "pass", "fail", "not_run"

# Gap-/Offen-Marker, die eine Lücke EHRLICH kennzeichnen (statt Werte zu
# erfinden). "[[…]]" ist der etablierte Platzhalter der Template-Drafts.
GAP_MARKERS = ("[[", "offen", "fehlt", "zu ergänzen", "nicht verfügbar", "keine angabe")

# Muster für Review-Notizen/Portalfragen, die NICHT als finale Prosa in einem
# Feldvorschlag stehen dürfen.
_NOTE_PATTERNS = (
    re.compile(r"\bTODO\b", re.I),
    re.compile(r"^\s*(?:review|hinweis an die prüfung)[:\s]", re.I | re.M),
    re.compile(r"^\s*\d+\.\d+(?:\.\d+)?\s+(?:describe|what|how|does|which)\b.*\?\s*$",
               re.I | re.M),
)

_NUMBER_RE = re.compile(r"\d+(?:[.,'’]\d+)*")
_SECTION_MARKER_RE = re.compile(r"^\d\.\d(?:\.\d)?$")


@dataclass(frozen=True)
class MetricResult:
    name: str
    status: str  # pass | fail | not_run
    detail: str


def _normalize_number(token: str) -> str:
    return token.replace("'", "").replace("’", "").replace(",", ".")


def extract_numbers(text: str) -> set[str]:
    """Numerische Tokens (normalisiert); Abschnittsmarker (3.1, 4.5.1) und
    kleine Aufzählungszahlen (0–10) zählen nicht als Faktenbehauptung."""
    numbers: set[str] = set()
    for token in _NUMBER_RE.findall(text or ""):
        if _SECTION_MARKER_RE.fullmatch(token):
            continue
        normalized = _normalize_number(token)
        try:
            if float(normalized) <= 10:
                continue
        except ValueError:
            pass
        numbers.add(normalized)
    return numbers


def terms_preserved(text: str, required_terms: tuple[str, ...]) -> MetricResult:
    if not required_terms:
        return MetricResult("terms_preserved", NOT_RUN, "Keine Pflichtbegriffe definiert.")
    lowered = (text or "").lower()
    missing = [term for term in required_terms if term.lower() not in lowered]
    return MetricResult(
        "terms_preserved",
        PASS if not missing else FAIL,
        f"{len(required_terms) - len(missing)}/{len(required_terms)} "
        f"Pflichtbegriffe enthalten"
        + (f"; fehlend: {len(missing)}" if missing else ""),
    )


def mandatory_subsections_present(
    text: str, expected_markers: tuple[str, ...]
) -> MetricResult:
    if not expected_markers:
        return MetricResult(
            "mandatory_subsections", NOT_RUN, "Kein Unterabschnitts-Soll definiert."
        )
    missing = [marker for marker in expected_markers if marker not in (text or "")]
    return MetricResult(
        "mandatory_subsections",
        PASS if not missing else FAIL,
        f"{len(expected_markers) - len(missing)}/{len(expected_markers)} "
        f"Pflichtunterabschnitte vorhanden"
        + (f"; fehlend: {', '.join(missing)}" if missing else ""),
    )


def char_limit_respected(text: str, limit: int | None) -> MetricResult:
    if limit is None:
        return MetricResult("char_limit", NOT_RUN, "Kein Zeichenlimit definiert.")
    count = len(text or "")
    return MetricResult(
        "char_limit",
        PASS if count <= limit else FAIL,
        f"{count}/{limit} Zeichen",
    )


def no_invented_numbers(text: str, input_corpus: str) -> MetricResult:
    known = extract_numbers(input_corpus)
    invented = sorted(extract_numbers(text) - known)
    return MetricResult(
        "no_invented_numbers",
        PASS if not invented else FAIL,
        "Keine Zahlen ausserhalb des Eingabekontexts."
        if not invented
        else f"{len(invented)} Zahl(en) ohne Eingabe-Grundlage.",
    )


def no_invented_patents(text: str, input_corpus: str) -> MetricResult:
    claims_patent = bool(re.search(r"\bpatent\w*", text or "", re.I))
    input_has_patent = bool(re.search(r"\bpatent\w*", input_corpus or "", re.I))
    invented = claims_patent and not input_has_patent
    return MetricResult(
        "no_invented_patents",
        FAIL if invented else PASS,
        "Patentbehauptung ohne Eingabe-Grundlage." if invented
        else "Keine erfundene Patentbehauptung.",
    )


def no_review_notes_as_prose(text: str) -> MetricResult:
    hits = sum(1 for pattern in _NOTE_PATTERNS if pattern.search(text or ""))
    return MetricResult(
        "no_review_notes_as_prose",
        PASS if hits == 0 else FAIL,
        "Keine Review-Notizen/Portalfragen im Fliesstext."
        if hits == 0
        else f"{hits} Notiz-/Fragemuster im Fliesstext.",
    )


def kpi_gaps_marked_open(text: str, missing_inputs_count: int) -> MetricResult:
    if missing_inputs_count <= 0:
        return MetricResult(
            "kpi_gaps_marked_open", PASS, "Keine offenen Eingabelücken gemeldet."
        )
    lowered = (text or "").lower()
    marked = any(marker in lowered for marker in GAP_MARKERS)
    return MetricResult(
        "kpi_gaps_marked_open",
        PASS if marked else FAIL,
        f"{missing_inputs_count} gemeldete Lücke(n); "
        + ("als offen gekennzeichnet." if marked
           else "NICHT als offen gekennzeichnet."),
    )


# --- Auswertung der R5.9-REAL-Ergebnisse --------------------------------------

def _field_limits() -> dict[str, int | None]:
    from app.registry import get_registry

    registry = get_registry()
    return {
        field_id: definition.character_limit
        for field_id, definition in registry.portal_fields.items()
    }


def _expected_markers(field_id: str) -> tuple[str, ...]:
    from app.registry import get_registry

    if not field_id.endswith(".EDITOR"):
        return ()
    markers = []
    for question in get_registry().mandatory_questions(field_id):
        match = re.search(r"MANDATORY_(\d+)_(\d+)(?:_(\d+))?$", question.field_id)
        if match:
            markers.append(".".join(part for part in match.groups() if part))
    return tuple(markers)


def build_input_corpus(entry: dict) -> str:
    """Eingabekontext des Laufs (Titel + bekannte synthetische Seeds) — die
    Grundlage für «keine erfundenen Zahlen/Patente»."""
    from app.evaluation.integrated_draft_real import _TITLE_DE, _TITLE_EN

    parts = [_TITLE_DE, _TITLE_EN]
    research = entry.get("report", {}).get("research_summary", {})
    parts.append(json.dumps(research, ensure_ascii=False))
    return "\n".join(parts)


def evaluate_entry(entry: dict, *, required_terms: tuple[str, ...]) -> list[dict]:
    """Metriken je Feld eines Provider-Ergebnisses (report + artifact)."""
    limits = _field_limits()
    corpus = build_input_corpus(entry)
    by_field_artifact = {
        item["field_id"]: item for item in entry.get("artifact", {}).get("fields", [])
    }
    rows: list[dict] = []
    for field in entry["report"]["fields"]:
        field_id = field["field_id"]
        text = (by_field_artifact.get(field_id) or {}).get("suggestion_text") or ""
        if field["status"] not in ("generated", "missing_inputs"):
            rows.append({
                "field_id": field_id, "status": field["status"],
                "model": field.get("model"),
                "metrics": [MetricResult(
                    "all", NOT_RUN,
                    f"Feldstatus «{field['status']}» — keine Bewertung."
                ).__dict__],
            })
            continue
        metrics = [
            terms_preserved(text, required_terms),
            mandatory_subsections_present(text, _expected_markers(field_id)),
            char_limit_respected(text, limits.get(field_id)),
            no_invented_numbers(text, corpus),
            no_invented_patents(text, corpus),
            no_review_notes_as_prose(text),
            kpi_gaps_marked_open(text, int(field.get("missing_inputs_count") or 0)),
        ]
        rows.append({
            "field_id": field_id, "status": field["status"],
            "model": field.get("model"),
            "metrics": [metric.__dict__ for metric in metrics],
        })
    return rows


def render_quality_report(
    per_provider: dict[str, list[dict] | None],
    *,
    generated_at: str,
    not_run_reasons: dict[str, str],
) -> str:
    """Whitelist-Report: Status/Zählwerte/Modell-IDs — nie Rohtexte.

    Nicht durchgeführte Provider werden wörtlich als ``not_run`` berichtet;
    es gibt keine Sammel-Grün-Aussage.
    """
    lines = [
        "# Live-Model-Evaluation (Ebene C) — Modellqualität",
        "",
        f"*Generiert:* {generated_at} — gleicher synthetischer Eingabetext "
        "(F1/D0), gleiche Rubrik, beide Provider über den produktiven "
        "Gateway-Pfad. `not_run` heisst: nicht durchgeführt — nie bestanden.",
        "",
    ]
    for provider in PROVIDERS:
        rows = per_provider.get(provider)
        if rows is None:
            lines += [
                f"## Provider: {provider} — Status: not_run",
                "",
                f"Grund: {not_run_reasons.get(provider, 'kein Ergebnis vorhanden')}",
                "",
            ]
            continue
        lines += [f"## Provider: {provider} — Status: durchgeführt", ""]
        for row in rows:
            lines += [
                f"### {row['field_id']} — Feldstatus `{row['status']}` — "
                f"Modell `{row['model'] or '—'}`",
                "",
                "| Metrik | Ergebnis | Detail |",
                "|---|---|---|",
            ]
            for metric in row["metrics"]:
                lines.append(
                    f"| {metric['name']} | {metric['status']} | {metric['detail']} |"
                )
            lines.append("")
        lines += [
            "### Human-Rubric (manuell auszufüllen — nie KI-bewertet)",
            "",
            "| Feld | Nützlichkeit (1–5) | Struktur (1–5) | Präzision (1–5) |",
            "|---|---|---|---|",
        ]
        for row in rows:
            lines.append(f"| {row['field_id']} | _TODO_ | _TODO_ | _TODO_ |")
        lines.append("")
    return "\n".join(lines)


def summarize_status(per_provider: dict[str, list[dict] | None]) -> str:
    """Gesamtstatus für das Gate: durchgeführt | not_run."""
    return (
        "durchgeführt"
        if any(rows is not None for rows in per_provider.values())
        else "not_run"
    )


def evaluate_results_dir(
    results_dir: Path, *, required_terms: tuple[str, ...] = ("QUALIMON",)
) -> tuple[dict[str, list[dict] | None], dict[str, str]]:
    """Lädt vorhandene R5.9-REAL-Ergebnisse und bewertet sie je Provider."""
    per_provider: dict[str, list[dict] | None] = {}
    reasons: dict[str, str] = {}
    for provider in PROVIDERS:
        path = results_dir / f"{provider}.json"
        if not path.exists():
            per_provider[provider] = None
            reasons[provider] = (
                "kein R5.9-REAL-Ergebnis (Opt-in-Lauf nicht durchgeführt oder "
                "Provider nicht verfügbar)"
            )
            continue
        entry = json.loads(path.read_text(encoding="utf-8"))
        per_provider[provider] = evaluate_entry(entry, required_terms=required_terms)
    return per_provider, reasons
