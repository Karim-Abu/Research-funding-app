# Live-Model-Evaluation (Ebene C) — Modellqualität

**Status: not_run** — solange kein Opt-in-Lauf durchgeführt wurde, gilt
diese Evaluation ausdrücklich als *nicht durchgeführt*; sie erscheint nie
als bestanden und fliesst nie in eine Sammel-Grün-Aussage ein.

## Durchführung (opt-in, nie Pflicht-CI)

```powershell
# Keys in backend/.env; CI darf nicht gesetzt sein
$env:RUN_REAL_PROVIDER_SMOKE = "true"; $env:AI_EVAL_MODE = "real"
backend\.venv\Scripts\python.exe scripts\run_model_quality_eval.py
```

Die Generierung läuft ausschliesslich über die produktiven Pfade
(`gateway.invoke`, Produktiv-Profile aus der Agent-Registry, versionierte
Prompt-Assets, echte Provider-Adapter) mit dem synthetischen F1/D0-Fall —
gleicher Eingabetext, gleiche Rubrik, OpenAI **und** Anthropic. Es gibt
keine parallele Evaluationslogik (Harness-Vertrag).

## Ergebnisartefakte

| Artefakt | Ort | Inhalt |
|---|---|---|
| Whitelist-Summary | `backend/var/evaluation/model_quality_summary.{md,json}` (gitignoriert) | Status je Provider, Metrik-Ergebnisse, Modell-IDs, Zählwerte |
| Rohoutputs | `backend/var/evaluation/r5_9_real/` (gitignoriert) | vollständige Modellantworten — nie committen |

## Deterministische Metriken (je Feld, je Provider)

| Metrik | Bedeutung |
|---|---|
| `terms_preserved` | projektspezifische Pflichtbegriffe bleiben erhalten |
| `mandatory_subsections` | Pflichtunterabschnitte (z. B. 3.1–3.3) vorhanden |
| `char_limit` | Innolink-Zeichenlimit eingehalten |
| `no_invented_numbers` | keine Zahlen ohne Grundlage im Eingabekontext |
| `no_invented_patents` | keine erfundenen Patentbehauptungen |
| `no_review_notes_as_prose` | Review-Notizen/Portalfragen nie als finale Prosa |
| `kpi_gaps_marked_open` | KPI-/Angabelücken als offen gekennzeichnet, nicht erfunden |

## Human-Rubric (verpflichtend menschlich)

Nützlichkeit / Struktur / Präzision werden pro Feld manuell (1–5) in der
Summary-Tabelle ergänzt — nie KI-bewertet.

## Übertrag in den Acceptance-Report

Nach einem Lauf: Status («durchgeführt» + Datum) und die Metrik-Zählwerte
je Provider in `docs/demo/demo-acceptance-report.md` (Kategorie «Live model
evaluation») übernehmen. Ohne Lauf bleibt dort wörtlich `not_run` stehen.
