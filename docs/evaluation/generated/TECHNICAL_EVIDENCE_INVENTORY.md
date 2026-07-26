---
title: "Technische Evidenzinventur"
date: 2026-07-25
commit: 8416914
status: generated
tags: [eval3, evidence, inventory, reproducibility]
---

# Technische Evidenzinventur

Bestandsaufnahme aller ausführbaren Tests, Verifikationsskripte, Berichte und
Laufartefakte — und die kritische Frage je Eintrag: **Ist die Aussage durch einen
tatsächlich ausgeführten, versionierten Lauf gedeckt?**

Grundlage: [[EVALUATION_BASELINE]] (Commit `8416914`, `non-frozen-working-tree`).

## 1. Ausführbarer Testcode

| Evidence ID | Pfad | Typ | Umfang | Ausführbarer Nachweis | Status |
|---|---|---|---|---|---|
| T-BE | `backend/tests/` | pytest | 151 Testdateien, **1514 gesammelte Fälle** | ja — hermetisch, Temp-SQLite, keine Provider | `executable-test` |
| T-FE | `test/` | vitest (jsdom + MSW) | 78 Dateien, **631 Fälle** | ja — offline, `onUnhandledRequest: "error"` | `executable-test` |
| T-E2E | `e2e/` | Playwright | 33 Specs (28 Standard + 5 opt-in), 72 Fälle | ja — braucht Backend :8000 + Frontend :3000 + geseedete DB | `executable-test` |
| T-GUARD | `scripts/check_testdata_markers.py`, `scripts/check_legacy_status_paths.py` | Guard-Skripte | 2 | ja — stdlib, offline | `executable-test` |
| T-CONTRACT | `final_backend_contracts_v1_1/validate_contracts.py` | Contract-Validator | 9 YAML + OpenAPI | ja — offline (PyYAML) | `executable-test` |
| T-GATE | `scripts/verify_all.ps1` / `.sh` | Abschlussgate | 14 Gate-Zeilen, 6 Kategorien | ja — startet Server selbst, erzwingt Fake-Provider | `executable-test` |
| T-EVAL | `backend/app/evaluation/` (`python -m app.evaluation`) | Metrik-Harness | Schema `evaluation-run-summary-1` | ja — braucht DB mit abgeschlossenem Demo-Run | `executable-test` |
| T-SEED | `backend/app/demo/seed.py` | Demo-Seed | `--reset`, `--evaluation` | ja — braucht `DEMO_DATA_ENABLED=true` | `executable-test` |
| T-LIVE | 4 pytest-Dateien + ~10 `scripts/run_*`-Skripte | Real-Provider-Smokes | — | **nein** — kostenpflichtig, env-gated | `blocked-requires-explicit-live-approval` |

**Kein CI vorhanden.** Es gibt kein `.github/`, kein Makefile, keine Pipeline.
`verify_all` ist das manuell gefahrene CI-Äquivalent. Damit existiert keine
automatische, unabhängige Ausführung — jeder grüne Stand hängt an einem manuellen
Lauf auf einer Entwicklermaschine.

## 2. Neu erhobene Laufergebnisse (dieser Lauf, 2026-07-25)

Alle Rohartefakte unter `runs/<RUN_ID>/`. Siehe [[EVAL3_TECHNICAL_VERIFICATION]].

| Evidence ID | Lauf | Ergebnis | Artefakt | Status |
|---|---|---|---|---|
| R-CONTRACT-01 | `validate_contracts.py` | **PASS** (Exit 0) — 9 Dokumente, 76 Requirements, 165 Portalfelder, 83 API-Operationen | `runs/CONTRACT-01/` | `executed-result` |
| R-GUARD-01 | `check_testdata_markers.py` | **PASS** (Exit 0) — aber **0 Marker, 0 Allowlist** | `runs/GUARD-01/` | `executed-result` |
| R-GUARD-02 | `check_legacy_status_paths.py` | **PASS** (Exit 0) | `runs/GUARD-02/` | `executed-result` |
| R-MIGRATE-01 | `alembic upgrade head` auf frischer DB | **PASS** (Exit 0) — bis `c4d7e1f9a2b3` | `runs/MIGRATE-01/` | `executed-result` |
| R-BACKEND-01 | `pytest -q` | **FAIL** (Exit 1) — 1514 Tests, **6 failures**, 4 skipped, 550 s | `runs/BACKEND-01/` inkl. `junit.xml`, `failures.md` | `executed-result` |
| R-LINT-01 | `pnpm lint` | **PASS** (Exit 0) | `runs/LINT-01/` | `executed-result` |
| R-TSC-01 | `tsc --noEmit` | **PASS** (Exit 0) | `runs/TSC-01/` | `executed-result` |
| R-VITEST-01 | `vitest run` | **PASS** (Exit 0) — 78 Dateien, **631 Tests**, 34 s | `runs/VITEST-01/` inkl. `junit.xml` | `executed-result` |
| R-BUILD-01 | `pnpm build` | **PASS** (Exit 0) — 31 Seiten | `runs/BUILD-01/` | `executed-result` |
| R-GATE-01 | `verify_all.ps1` | siehe [[EVAL3_TECHNICAL_VERIFICATION]] | `runs/GATE-01/verify_all.log` | `executed-result` |
| R-COVERAGE | `scripts/evaluation/requirement_coverage.py` (**neu erstellt**) | 76 Requirements, 12 auswertbar, 64 contract-only | `requirement_coverage.json` | `executed-result` |

## 3. Kritische Prüfung der bestehenden Berichte

Bewertet nach: Befehl genannt? Datum? Commit? Exit Code? Testzahlen? Fehler
sichtbar? Zum aktuellen Code passend? Reproduzierbar?

### 3.1 Der zentrale Befund

**Das am häufigsten zitierte Ergebnis der Arbeit besitzt kein Artefakt.**

`scripts/verify_all.ps1` enthält **null** Schreibbefehle (`Tee-Object`,
`Start-Transcript`, `Out-File`, `>>`, `Set-Content` — verifiziert: 0 Treffer).
Es druckt ausschliesslich auf die Konsole. Jede «TECHNISCHES GATE GRÜN»-Angabe
in den Berichten ist damit eine **Abschrift**, kein erfasster Lauf.

Der einzige jemals persistierte verify_all-Lauf im Repo,
`verify_all_market_scope_recovery.log` (2026-07-22, UTF-16LE, git-ignoriert),
endet mit:

```
TECHNISCHES GATE (deterministisch, Fake-Provider): ROT
frontend tests (vitest)  : FAIL
docx render smoke        : FAIL
```

Demgegenüber behauptet `docs/FINAL_MVP_ACCEPTANCE_REPORT.md:40` wörtlich
«pass — **TECHNISCHES GATE GRÜN**, alle 14 deterministischen Zeilen pass».

### 3.2 Keine versionierten Maschinenartefakte

`backend/.gitignore:16` ignoriert `var/` — bestätigt via
`git check-ignore -v backend/var/evaluation/EvaluationRunSummary.json`.
**Sämtliche** maschinenlesbaren Evaluationsergebnisse liegen dort und sind damit
unversioniert. Einzige getrackte Rohdatei im ganzen Repo:
`docs/evaluation/baseline-f1-result.json`.

### 3.3 Playwright erzeugt konstruktionsbedingt keine Evidenz

`playwright.config.ts`: `retries: 0` (Z. 15), `reporter: [["list"]]` (Z. 16),
`trace: "off"` (Z. 20). Kein JUnit, kein HTML, keine Traces, keine Screenshots
bei Fehlern. Einziges Artefakt: `test-results/.last-run.json` — 45 Bytes,
`{"status":"passed","failedTests":[]}`, ohne Testzahlen, ohne Zeitstempel,
git-ignoriert. Behauptungen wie «53 passed / 0 failed / 15 skipped» sind daher
nicht belegbar.

*In diesem Lauf behoben:* Playwright/pytest/vitest wurden über CLI-Flags mit
JUnit-Ausgabe gefahren, ohne eine Repo-Konfiguration zu ändern.

### 3.4 Weitere belastbare Befunde

| # | Befund | Beleg |
|---|---|---|
| B4 | **Spec und Realität widersprechen sich.** `Evaluation_Dataset.md` erwartet 9 Anchors, 8 Felder, `blocker_count 2`, `warning_count 5`, 22 Findings. Die reale `EvaluationRunSummary.json` (23.07.) meldet 5 / — / 0 / 3 / 16. Nichts im Repo versöhnt das. | `docs/evaluation/Evaluation_Dataset.md` vs. `backend/var/evaluation/EvaluationRunSummary.json` |
| B5 | **Statuswechsel nicht propagiert.** `LIVE_RETEST_2026-07-23.md:55` erklärt `COMBINED_LIVE_E2E_PARTIAL_STRICT_GATES` als Ersatz für `COMBINED_LIVE_E2E_BLOCKED_BY_PROVIDER_TIMEOUT`; letzterer steht weiterhin an **11 Stellen in 7 Dokumenten**. Das Doc-Set behauptet beides gleichzeitig. | `LIVE_RETEST_2026-07-23.md` vs. `RUN_3_CLOSURE.md`, `KNOWN_LIVE_LIMITATIONS.md`, `RUN_4A_RESULT.md`, `RUN_4_RESULT.md`, `FINAL_MVP_LIMITATIONS.md`, `FINAL_MVP_ACCEPTANCE_REPORT.md`, `FINAL_UI_ACCEPTANCE_MATRIX.md` |
| B6 | **«ALL GREEN»-Widerspruch.** `Evaluation_Execution_Checklist.md:14`, `Supervised_Beta_Demo_Guide.md` und `README.md:125` verlangen «ALL GREEN»; `verify_all.ps1` und `demo-acceptance-report.md` sagen ausdrücklich, dass es das bewusst **nicht** gibt. | ebd. |
| B7 | **Referenziert, aber nicht vorhanden:** `backend/var/evaluation/role_model_eval/summary.json` (existiert nur als `role_model_eval_pilot/`). | `demo-acceptance-report.md`, `verify_all.ps1` |
| B8 | **Unreferenzierte Fehlerlogs.** Die vier `*.evaluation.*.log` (08.07.) zeigen `OperationalError: no such column: open_issues.fingerprint` und dreimal `500` auf `/review/status`. Kein Bericht erwähnt sie. | Repo-Root |
| B9 | **`model_quality_report.md` sagt `not_run`**, obwohl `model_quality_summary.json` (15.07.) einen echten Lauf belegt. | `docs/evaluation/model_quality_report.md` |
| B10 | **Testdaten-Marker-Check prüft nichts.** `check_testdata_markers.py` läuft grün mit **0 Markern**; der Katalog in `testdata-policy.md` ist leer und trägt ein `TODO(Owner)` samt Hinweis «leerer Katalog ergibt einen gruenen Check». Die Gate-Zeile «testdata markers: pass» ist damit inhaltsleer. | `docs/evaluation/testdata-policy.md`, `runs/GUARD-01/stdout.log` |

### 3.5 Klassifikation der Hauptberichte

| Bericht | Datum | Commit | Befehl | Klassifikation |
|---|---|---|---|---|
| `FINAL_MVP_ACCEPTANCE_REPORT.md` | ✅ | ✅ | ✅ | `repository-claim-only` (kein Gate-Log; Phase E ausgenommen) |
| `RUN_4_RESULT.md` | ✅ | ✅ | ✅ | `repository-claim-only` |
| `RUN_4A_RESULT.md` | ✅ | ❌ | ✅ | `executed-version-unclear` |
| `RUN_4A_UI_REVIEW.md` | ✅ | ✅ | ✅ | `repository-claim-only` + 27 Screenshots |
| `RUN_3_RESULT.md` | ❌ | ❌ | ❌ | `repository-claim-only` — nennt dennoch Kosten auf 6 Nachkommastellen |
| `LIVE_RETEST_2026-07-23.md` | ✅ | ❌ | ✅ | **`executed-and-versioned`** (durch getrackte Ledger gestützt) |
| `LIVE_WEB_SMOKE_REPORT.md` | ✅ | — | generiert | **`executed-and-versioned`** |
| `LIVE_LLM_SMOKE_REPORT.md` | ✅ | — | generiert | **`executed-and-versioned`** |
| `eval2_real_provider_smoke_report.md` | ✅ | ✅ | ✅ | **`executed-and-versioned`** — benennt den Anthropic-Fehlschlag offen |
| `baseline-report.md` + `baseline-f1-result.json` | ✅ | — | ✅ | **`executed-and-versioned`** — einzige vollständig versionierte Paarung |
| `model_quality_report.md` | ❌ | ❌ | ✅ | `stale` (siehe B9) |
| `metrics.md` | — | — | — | `static-audit` — jede Metrik «Skeleton, noch keine echte Bewertung» |
| `Evaluation_Execution_Checklist.md`, `Evaluation_Session_Protocol.md`, `Supervised_Beta_Demo_Guide.md` | — | — | ✅ | `configuration-only` — alle Haken ungesetzt |
| `User_Evaluation_Questionnaire.md`, `Baseline_Comparison_Template.md`, `blind_rubric_*` | — | — | — | `configuration-only` — Instrumente ohne Antworten |
| `docs/milestones/**` (27), `docs/audits/**` (7) | teils | teils | teils | `repository-internal-report` / `static-audit` |

**Ausdrücklich zu würdigen:** `LIVE_RETEST_2026-07-23.md` dokumentiert
Fehlversuche einzeln mit Reason-Codes; `LIVE_LLM_HUMAN_REVIEW.md` verweigert
korrekt eine Bewertung («kein Review-Set erzeugt»); im Pilot-Ordner markieren
zwei `INVALID.json` einen Harness-Fehler ausdrücklich als **nicht** zur
Modellbewertung geeignet. Das ist gute wissenschaftliche Praxis.

## 4. Reuse-Entscheidung je Artefakt

Maßstab ist nicht das Alter, sondern ob seit Erzeugung Code geändert wurde, von
dem das Artefakt abhängt. Der HEAD-Commit `8416914` (105 Dateien, +6386/−2907)
enthält **eine neue Migration** (`c4d7e1f9a2b3_usage_exact_costs_usd`) und
ändert `evaluation/pricing.py`, `evaluation/reprice.py`, `db/models.py`,
`api/costs.py` sowie 16 Backend-Testdateien.

| Artefakt | Datum | Entscheidung | Begründung |
|---|---|---|---|
| `docs/evaluation/cases/**` | — | **wiederverwendet** | Eingaben/Goldstandards, versionsunabhängig |
| `baseline-f1-result.json` + `baseline-report.md` | 07.07. | **historisch** | einzige versionierte Rohdatei |
| `LIVE_WEB_SMOKE_REPORT.md`, `LIVE_LLM_SMOKE_REPORT.md`, `LIVE_RETEST_2026-07-23.md` | 23.07. | **historisch** | echte Provider-Läufe, **nicht reproduzierbar** (kostenpflichtig) |
| `eval2_real_provider_smoke_report.md`, `r5_5_*`, `r5_9_*`, `supervisor_eval_report.md` | 08.–09.07. | **historisch** | reale Läufe mit genannten Befehlen |
| `role_model_eval_pilot/**` | 16.–17.07. | **historisch** | reichhaltigste echte Messung (119 Calls, CHF 3.02); `INVALID.json` respektiert |
| `docs/assets/**` (66 PNG) | 23.07. | **historisch, mit Vorbehalt** | zeigen den Stand **vor** der UI-Bereinigung vom 25.07. → nicht aktueller UI-Stand |
| `EvaluationRunSummary.{json,md}` | 23.07. | **neu erhoben** | Schema-Migration + Pricing-Änderung danach |
| `provider_preflight.json` | 23.07. | **nicht erhoben** | bräuchte reale Provider → `blocked` |
| `model_quality_summary.json` | 15.07. | **nicht erhoben** | kostenpflichtig → `blocked` |
| Backend/Frontend/E2E-Ergebnisse | — | **neu erhoben** | es existierte **kein** Artefakt |
| `verify_all`-Gate | — | **neu erhoben, mit Log** | einziger erfasster Lauf war ROT |

## 5. Zusammenfassung

Die **Testsubstanz ist stark**: 1514 Backend-Fälle, 631 Frontend-Fälle, 72 E2E-Fälle,
ein hermetischer Provider-Guard mit eigenem Regressionstest, ein fail-closed
Preismodell, ein Contract-Validator über 9 Registries.

Die **Beweisführung darüber war schwach**: kein CI, kein Gate-Log, keine
versionierten Maschinenartefakte, keine JUnit-Ausgabe, widersprüchliche
Statusmarker und eine Gate-Zeile, die nichts prüft.

Dieser Lauf schliesst die Beweislücke für den deterministischen Teil, ohne eine
einzige Produktzeile zu ändern.
