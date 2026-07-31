---
title: "EVAL3 — Ausführungsplan"
date: 2026-07-25
commit: 8416914
status: executed
tags: [eval3, execution-plan, reproducibility]
---

# EVAL3 — Ausführungsplan

Die tatsächlich ausgeführten Läufe, ihre Befehle und Artefakte. Alle Befehle
stammen aus `package.json`, `backend/pytest.ini`, `playwright.config.ts` und
`scripts/verify_all.ps1` — **nicht** aus README-Prosa (die README widerspricht
dem Gate, siehe [[TECHNICAL_EVIDENCE_INVENTORY]] B6).

Ausgangszustand: [[EVALUATION_BASELINE]] · Ergebnisse: [[EVAL3_TECHNICAL_VERIFICATION]]

## Erfassungsstrategie

Die Runner persistieren von sich aus nichts (Befund B1–B3). Deshalb wurde
**jeder** Lauf beim Aufruf erfasst — ohne eine einzige Repo-Konfiguration zu
ändern, ausschliesslich über CLI-Flags und Umleitung:

| Ebene | Zusatz beim Aufruf |
|---|---|
| alle | `stdout.log`, `stderr.log`, `command.txt`, `result.json` (Exit Code, Start/Ende, Commit) |
| pytest | `--junitxml=runs/<RUN_ID>/junit.xml` |
| vitest | `--reporter=junit --outputFile.junit=runs/<RUN_ID>/junit.xml` |
| verify_all | `*>&1 \| Tee-Object -FilePath runs/GATE-01/verify_all.log` |

`playwright.config.ts`, `vitest.config.ts` und `pytest.ini` blieben unverändert.

## Sicherheitsvorgaben für jeden Lauf

- `RUN_REAL_PROVIDER_SMOKE` wird **nie** gesetzt → 4 pytest-Dateien überspringen
  sich selbst, alle kostenpflichtigen Skripte bleiben aus.
- `AI_EVAL_MODE=off` beim Backend-Lauf (zusätzlich zur Hermetik in
  `conftest.py`).
- `backend/.env` wird nicht verändert; `backend/app.db` wird nicht berührt.
- Migrations- und E2E-Läufe nutzen Wegwerf-Datenbanken, die danach gelöscht werden.

## Läufe

| Run ID | Kategorie | Befehl | Voraussetzungen | Erwartete Outputs | Timeout |
|---|---|---|---|---|---|
| `CONTRACT-01` | Contracts | `python final_backend_contracts_v1_1/validate_contracts.py` | PyYAML | Zählwerte je Registry, Exit 0/1 | 5 min |
| `GUARD-01` | Testdaten-Policy | `python scripts/check_testdata_markers.py --root .` | stdlib | Marker-/Allowlist-Zahl | 5 min |
| `GUARD-02` | Legacy-Status | `python scripts/check_legacy_status_paths.py --root .` | stdlib | Allowlist-Zahl, Paritätstest vorhanden | 5 min |
| `MIGRATE-01` | Migration | `DATABASE_URL=sqlite:///./var/eval_migrate_check.db APP_ENV=test python -m alembic -c alembic.ini upgrade head` | frische DB | Upgrade-Kette bis `c4d7e1f9a2b3` | 5 min |
| `BACKEND-01` | Backend-Suite | `AI_EVAL_MODE=off python -m pytest -q -p no:warnings --junitxml=…` | Temp-SQLite (automatisch) | `junit.xml`, Testzahlen | 10 min |
| `LINT-01` | Frontend-Lint | `corepack pnpm lint` | node_modules | ESLint-Ausgabe | 10 min |
| `TSC-01` | Typecheck | `corepack pnpm exec tsc --noEmit` | node_modules | TS-Fehler | 10 min |
| `VITEST-01` | Frontend-Tests | `corepack pnpm exec vitest run --reporter=default --reporter=junit --outputFile.junit=…` | node_modules | `junit.xml`, Testzahlen | 10 min |
| `BUILD-01` | Build | `rm -rf .next && corepack pnpm build` | node_modules | Route-Manifest | 15 min |
| `GATE-01` | **Gesamtgate** | `.\scripts\verify_all.ps1` (mit `Tee-Object`) | Word für die DOCX-Zeile; Ports 3000/8000 frei | 6 Kategorien + 14 Gate-Zeilen, `EvaluationRunSummary.json` | 60 min |
| `R-COVERAGE` | Coverage-Join | `python scripts/evaluation/requirement_coverage.py` | PyYAML | `requirement_coverage.json`, [[EVAL3_REQUIREMENT_COVERAGE]] | 5 min |

### Was `GATE-01` intern abdeckt

`verify_all.ps1` ist das repo-eigene Abschlussgate und ersetzt einen separaten
E2E-Block. Es führt in dieser Reihenfolge aus:

1. Testdaten-Marker + Legacy-Status-Guard
2. Migration auf frischer Wegwerf-DB
3. Backend-pytest (ohne DOCX-Smoke) — **eigene Zeile** für den DOCX-Smoke
4. Frontend: vitest, lint, tsc, build
5. Wegwerf-DB `verify_e2e.db` + `python -m app.demo.seed --reset --evaluation`
6. Start Backend :8000 + Frontend :3000 mit **erzwungenen Fake-Providern**
   (`AGENT_FAKE_PROVIDER=true`, `WEB_RESEARCH_FAKE_PROVIDER=true`,
   `AI_EVAL_MODE=off`)
7. Playwright-Gesamtsuite, danach Golden-Path-Zweitlauf, Import-Pfad,
   Review-Truth
8. `scripts/smoke_api.py`
9. Re-Seed + `python -m app.evaluation` → `EvaluationRunSummary.json`
10. Aufräumen: Server beenden, Wegwerf-DB löschen

Damit ist die E2E-Kategorie vollständig abgedeckt — inklusive der geforderten
Security-/Privacy-, Evidence-, Export- und Recovery-Szenarien, die als Specs Teil
der Suite sind.

## Nicht ausgeführt (bewusst)

| Kategorie | Grund | Status |
|---|---|---|
| 4 Real-Provider-pytest-Dateien | `RUN_REAL_PROVIDER_SMOKE` nicht gesetzt | `blocked-requires-explicit-live-approval` |
| `run_real_provider_smoke.py`, `run_r5_5_field_smoke.py`, `run_integrated_draft_real.py` | kostenpflichtige LLM-Calls | `blocked-requires-explicit-live-approval` |
| `run_live_research_smoke.py`, `run_live_web_smoke.py`, `run_live_llm_phase2.py` | kostenpflichtige Firecrawl-/LLM-Calls | `blocked-requires-explicit-live-approval` |
| `run_role_model_eval.py` (ohne `--fake`) | Kosten-Cap CHF 12, reale Calls | `blocked-requires-explicit-live-approval` |
| `run_provider_preflight.py`, `run_provider_availability_smoke.py` | reale Provider-Pings | `blocked-requires-explicit-live-approval` |
| `run_private_innolink_acceptance.py` | benötigt echtes, nicht eingecheckte Antrags-PDF | `not-reproducible` (per Design) |
| Opt-in-Playwright-Specs (`RUN4A_VISUAL`, `RUN4A_REVIEW`, `RUN4B_VISUAL`, `FINAL_ACCEPT`) | erzeugen nur Screenshots; vorhandene Assets vom 23.07. werden als historisch geführt | `not-executed` |

Für jeden blockierten Punkt sind Befehl, Konfiguration und Grund in
[[EVAL3_TECHNICAL_VERIFICATION]] §Blockiert dokumentiert.
