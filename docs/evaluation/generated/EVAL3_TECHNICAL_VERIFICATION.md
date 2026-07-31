---
title: "EVAL3 — Technical Verification"
date: 2026-07-25
commit: 8416914
status: executed
tags: [eval3, verification, test-results, reproducibility]
---

# EVAL3 — Technical Verification

Ergebnisse aller in diesem Lauf ausgeführten Verifikationen. **Jede Zahl ist auf
eine Datei unter `runs/<RUN_ID>/` zurückführbar.** Nichts ist aus bestehenden
Berichten übernommen.

Ausgangszustand: [[EVALUATION_BASELINE]] · Plan: [[EVAL3_EXECUTION_PLAN]] ·
Bestandsaufnahme: [[TECHNICAL_EVIDENCE_INVENTORY]]

## 1. Gesamtergebnis

> **Das deterministische Gesamtgate ist ROT.**
> `scripts/verify_all.ps1` endet mit Exit 1. Ursachen: eine reale
> Backend-Testregression **und** zwei Umgebungsprobleme, die klar davon zu
> trennen sind.

| Lauf | Ergebnis | Exit | Kernzahlen | Artefakt |
|---|---|---|---|---|
| `CONTRACT-01` Contract-Validator | **PASS** | 0 | 9 Dokumente · 76 Requirements · 165 Portalfelder · 83 API-Operationen · 13 Profile · 19 Tools · 29 Controls · 58 Schemas | `runs/CONTRACT-01/` |
| `GUARD-01` Testdaten-Marker | **PASS** | 0 | **0 Marker, 0 Allowlist** — prüft faktisch nichts | `runs/GUARD-01/` |
| `GUARD-02` Legacy-Status-Guard | **PASS** | 0 | 3 Allowlist-Dateien, Paritätstest vorhanden | `runs/GUARD-02/` |
| `MIGRATE-01` Migration frische DB | **PASS** | 0 | 40 Migrationen bis `c4d7e1f9a2b3` | `runs/MIGRATE-01/` |
| `BACKEND-01` pytest | **FAIL** | 1 | **1514 Tests · 6 failures · 0 errors · 4 skipped · 550,0 s** | `runs/BACKEND-01/` + `junit.xml` |
| `LINT-01` ESLint | **PASS** | 0 | keine Befunde | `runs/LINT-01/` |
| `TSC-01` Typecheck | **PASS** | 0 | keine Fehler | `runs/TSC-01/` |
| `VITEST-01` Frontend-Tests | **PASS** | 0 | **78 Dateien · 631 Tests · 0 failures · 34,3 s** | `runs/VITEST-01/` + `junit.xml` |
| `BUILD-01` Production-Build | **PASS** | 0 | 31 Seiten, kompiliert in 8,4 s | `runs/BUILD-01/` |
| `E2E-01` Playwright (gezielt) | **FAIL** | 1 | **10 Tests · 9 passed · 1 failed · 50,0 s** | `runs/E2E-01/` + `junit.xml` + `attribution.md` |
| `GATE-01` verify_all.ps1 | **ROT** | 1 | 14 Gate-Zeilen, 6 Kategorien | `runs/GATE-01/verify_all.log` |
| `EVAL-SUMMARY` `python -m app.evaluation` | **PASS** | 0 | Schema `evaluation-run-summary-1` | `runs/EVAL-SUMMARY/` |
| `R-COVERAGE` Requirement-Join | **PASS** | 0 | 76 Requirements, 12 auswertbar | `requirement_coverage.json` |

## 2. Backend-Regression (echt)

`runs/BACKEND-01/failures.md` enthält die Analyse. Kurzfassung:

| Test | Voll-Suite | isoliert | Einordnung |
|---|---|---|---|
| `test_live_readiness.py::test_fresh_persisted_route_preflight_expires` | FAIL | FAIL | **deterministisch** — `assert row.pricing_version == "test-v1"` erhält `'2026-07-25.1'` |
| `test_eval2_real_smoke.py::test_run_llm_case_with_fake_adapter_meters_schema_failure` | FAIL | FAIL | deterministisch |
| `test_live_llm_phase2_full_dry_run.py::test_phase2_prepare_web_resume_llm_full_offline_dry_run` | FAIL | FAIL | deterministisch |
| `test_a2_generation.py::test_preflighted_synthetic_live_a2_is_truthfully_model_generated` | FAIL | FAIL | deterministisch |
| `test_a2_generation.py::test_missing_input_metadata_cannot_introduce_a_new_number` | FAIL | PASS | **reihenfolgeabhängig** |
| `test_demo_seed.py::test_isolated_test_db_requires_exactly_two_demo_projects` | FAIL | PASS | **reihenfolgeabhängig** |

**Unabhängige Bestätigung der Instabilität:** Der Gate-Lauf (`GATE-01`) fuhr
dieselbe Suite erneut und meldete **5** statt 6 Fehlschläge — es fehlte genau
`test_missing_input_metadata_cannot_introduce_a_new_number`. Zwei Läufe
derselben unveränderten Suite liefern also unterschiedliche Ergebnisse. Das ist
ein Befund über die **Testsuite**, nicht über das Produkt.

Der deterministische Kern (`test_live_readiness.py`) hängt direkt am
HEAD-Commit: `PRICE_TABLE_VERSION` wurde dort auf `2026-07-25.1` gesetzt,
der Test erwartet weiterhin eine gepatchte Version.

**Nichts wurde repariert, kein Test angepasst.**

## 3. Umgebungsprobleme (klar getrennt vom Produkt)

### 3.1 Gate-E2E lief nicht — Server nicht rechtzeitig bereit

`GATE-01` meldet für alle vier E2E-Zeilen `FAIL(servers not ready)`.
`verify_all.ps1` wartet fest **40 × 2 s = 80 s** auf HTTP 200 von
`:8000/api/v1/health` und `:3000/login`.

Nachgemessen: die vom Gate gestarteten Prozesse existierten laut
`Win32_Process.CreationDate` erst um **23:31:17** (uvicorn) bzw. **23:31:33**
(next) — das Gate hatte um **23:29:43** bereits aufgegeben. Auf diesem
OneDrive-gebundenen Arbeitsverzeichnis reicht das Fenster nicht.

Zusätzlich wurden die Prozesse vom `finally`-Block **nicht beendet** — sie liefen
verwaist weiter und mussten manuell gestoppt werden. Das entspricht der in
`RUN_4_RESULT.md` dokumentierten `netstat`-Locale-Falle (deutsches Windows meldet
`ABHÖREN` statt `LISTENING`).

**Konsequenz:** Die E2E-Zeilen in `GATE-01` sind `not-executed`, **nicht**
`failed`. Sie wurden über `E2E-01` separat nachgeholt (§4).

### 3.2 DOCX-Render-Smoke lief und bestand

`tests/test_docx_render_smoke.py` benötigt Microsoft Word und überspringt sich
bewusst nicht. Word ist vorhanden; die Gate-Zeile meldet **pass**. Damit ist die
entsprechende `FAIL`-Zeile aus dem historischen Log vom 22.07. auf dieser
Maschine **nicht** reproduzierbar.

### 3.3 Zwei Gate-Zeilen sind fehlerhaft abgeleitet

`verify_all.ps1` setzt `$exportR = $R.backend` und `$norawR = $R.backend`. Die
Zeilen `export smoke` und `no-raw-log` zeigen daher **immer** den Status der
gesamten Backend-Suite, nicht ihr eigenes Ergebnis. Im Gate stehen sie auf
`FAIL`, obwohl `test_m10_smoke.py::test_export_all_types` und `::test_no_raw_log`
in `BACKEND-01` **nicht** unter den Fehlschlägen sind, also bestanden haben.

Das ist ein **Reporting-Fehler des Gates**, kein Produktfehler — und er macht
das Gate an dieser Stelle unbrauchbar als Nachweis.

## 4. E2E — nachgeholt und mit Ursachenzuordnung

`E2E-01` (6 Specs, eigene Server, Fake-Provider erzwungen):
**9 passed, 1 failed.**

Bestanden: `privacy-firewall` (4), `evidence` (1), `export` (1),
`review-truth` (1), `ui-states` (2).
Fehlgeschlagen: `golden-path.spec.ts:221`.

**Ursache kontrolliert ermittelt** (`runs/E2E-01/attribution.md`):

| Stand von `components/research/query-approval-list.tsx` | golden-path |
|---|---|
| Working-Tree-Fassung (UI-Bereinigung, nicht committet) | **FAIL** |
| Originalfassung aus Commit `8416914` | **PASS** (9,5 s) |
| Working-Tree-Fassung wiederhergestellt | Ausgangszustand |

Playwright vergleicht bei `getByText()` case-insensitiv als Teilstring. Die
Assertion `getByText("Freigegeben")` traf in der Originalfassung den Fliesstext
`Firewall: **freigegeben**`, nicht das Status-Badge. Die UI-Bereinigung blendet
diesen im `allow`-Fall aus — damit entfällt der Teilstring.

**Einordnung:** Regression durch die **nicht committete** UI-Bereinigung, nicht
durch den Commit-Stand. Die Vitest-Suite blieb dabei vollständig grün; der
Fehler war ausschliesslich über Playwright sichtbar. Der Test ist zudem fragil,
weil er einen Status über zufällig gleichlautenden Fliesstext prüft.

Der Working Tree wurde danach exakt wiederhergestellt (unverändert 34 Dateien).
**Nicht behoben** — Empfehlung als eigener Schritt, P0 vor einem Merge.

## 5. EvaluationRunSummary — Spec gegen Realität

`EVAL-SUMMARY` erzeugte den Datensatz frisch gegen den heutigen Stand
(Migration `c4d7e1f9a2b3`, Preistabelle `2026-07-25.1`).

| Kennzahl | `Evaluation_Dataset.md` erwartet | gemessen 2026-07-25 | |
|---|---|---|---|
| `source_count` | 5 | **5** | ✅ |
| `draft_field_count` | 8 | **8** | ✅ |
| `reliability_claim_count` | 10 | **10** | ✅ |
| `supported_claims` | 1 | **1** | ✅ |
| `weakly_supported_claims` | 1 | **1** | ✅ |
| `unsupported_claims` | 2 | **2** | ✅ |
| `evidence_coverage` | 0.5 | **0.5** | ✅ |
| `evidence_sufficiency_pass_rate` | 0.5 | **0.5** | ✅ |
| `reliability_quality_flag` | risky | **risky** | ✅ |
| **verifizierte Anchors** | **9** | `exact_verified_anchor_count` **1** (`evidence_anchor_count` 5) | ❌ |
| **`blocker_count`** | **2** | **0** | ❌ |
| **`warning_count`** | **5** | **3** | ❌ |
| **`requirement_count`** | 11 (Thesis-Mapping) | **9** | ❌ |
| **`review_finding_count`** | 22 (Beispiel) | **16** | ❌ |

Die Abweichungen sind **identisch** zu denen des Laufs vom 23.07. Es handelt sich
also nicht um einen Ausreisser, sondern um eine **dauerhafte Diskrepanz zwischen
der dokumentierten Datensatz-Spezifikation und dem tatsächlichen Verhalten**.

Besonders relevant für die Arbeit: `Evaluation_Dataset.md` und
`Thesis_Evaluation_Mapping.md` nennen `blocker_count 2` als erwartetes Signal für
RQ3 («Reliability safety»). Gemessen wird **0**. Wer diese Erwartung zitiert,
zitiert eine Spezifikation, keine Messung.

`estimated_cost` bleibt korrekt ein Platzhalter (`placeholder: true`,
`value_chf: null`) — es wurde keine CHF-Zahl erfunden.

## 6. Requirement-Coverage

Details: [[EVAL3_REQUIREMENT_COVERAGE]], Rohdaten `requirement_coverage.json`.

| Kennzahl | gegen alle 76 | gegen die 12 auswertbaren |
|---|---|---|
| Implementation Coverage | **12/76 = 15,8 %** | **12/12 = 100,0 %** |
| Test Coverage | **8/76 = 10,5 %** | **8/12 = 66,7 %** |

Severity (programmatisch geparst, nicht abgeschrieben): 52 `blocker`,
18 `warning`, 6 `info`. Typ: 42 `hard`, 20 `semantic`, 14 `hybrid`.

Der niedrige Wert gegen 76 ist **kein Qualitätsmangel der Implementierung**,
sondern Folge davon, dass 64 Requirements auf die nie implementierten
`QG.*`-Quality-Gates verweisen (siehe [[EVAL2_IMPLEMENTATION_RECONCILIATION]]
FDC-13). Beide Nenner werden deshalb getrennt ausgewiesen.

## 7. Lückenklassifikation

| Dimension | Status |
|---|---|
| Contract-Validierung | vorhanden und ausgeführt |
| Migration | vorhanden und ausgeführt |
| Backend-Unit/Integration | vorhanden und ausgeführt — **mit Fehlern** |
| Frontend Lint/Typecheck/Unit/Build | vorhanden und ausgeführt |
| E2E Golden Path / Security / Evidence / Export / Recovery | vorhanden und ausgeführt (über `E2E-01`) |
| E2E im Gesamtgate | vorhanden, **nicht ausführbar** in dieser Umgebung (Readiness-Fenster) |
| Evaluationsmetriken | vorhanden und ausgeführt |
| Requirement-Coverage | **Messdaten fehlten** → Kategorie B, Harness neu erstellt |
| Reale Provider-Qualität (A1/A2/A3) | `blocked-requires-explicit-live-approval` |
| Firecrawl-Live-Recherche | `blocked-requires-explicit-live-approval` |
| Provider-Preflight | `blocked-requires-explicit-live-approval` |
| Fachliche Korrektheit der KI-Vorschläge | `not-measurable-with-current-gold-standard` |
| Private Innolink-Abnahme | `not-reproducible` (benötigt nicht eingecheckte Echtdaten) |

### Kategorie B — neu erstellter Harness

`scripts/evaluation/requirement_coverage.py` — **neu für diesen Lauf**.
Liest ausschliesslich die Contract-YAMLs und die Testbäume, importiert die App
nicht, verändert keine Runtime-Logik, schreibt nur nach
`docs/evaluation/generated/`. Der Implementierungsnachweis prüft, ob der
`condition.type` einer Regel einen Handler in `app/rules/handlers.py::HANDLERS`
besitzt — nicht, ob die Regel-ID im Code vorkommt (die Engine ist
datengetrieben, `app/rules/engine.py:90`).

### Kategorie C — blockiert, mit Angabe des Nötigen

| Messung | Befehl | Voraussetzung | Warum nicht lokal |
|---|---|---|---|
| Reale A1/A2/A3-Qualität | `scripts/run_role_model_eval.py pilot` | `RUN_REAL_PROVIDER_SMOKE=true`, `AI_EVAL_MODE=real`, Key, Cap CHF 12 / 24 Calls | erfordert kostenpflichtige Provider-Calls |
| Real-Provider-Smoke | `scripts/run_real_provider_smoke.py --case F1 --provider …` | wie oben, 1 Call/Provider | dito |
| Live-Firecrawl | `scripts/run_live_research_smoke.py` | `FIRECRAWL_API_KEY`, `WEB_RESEARCH_FAKE_PROVIDER` aus | echter Web-Abruf |
| Provider-Preflight | `scripts/run_provider_preflight.py` | Keys | Ping gegen reale Endpunkte |

Historische Ergebnisse dieser Kategorien bleiben als **historische Evidenz**
erhalten (siehe [[TECHNICAL_EVIDENCE_INVENTORY]] §4) und werden nicht als
aktueller Stand ausgegeben.

### Kategorie D — kein Goldstandard

Fachliche Korrektheit der erzeugten Antragstexte. Vorhanden sind Gold-Dateien
für F1/F2/H1 (`docs/evaluation/cases/`) und deterministische Metriken
(`model_quality.py`: `terms_preserved`, `no_invented_numbers`, …). Ein
fachlicher Referenzentwurf, gegen den inhaltliche Richtigkeit messbar wäre,
existiert nicht. **Es wurde keine Ersatzmetrik erfunden.**

## 8. Bewertung

**Die Testsubstanz ist stark.** 1514 Backend-Fälle, 631 Frontend-Fälle,
72 E2E-Fälle, ein hermetischer Provider-Guard mit eigenem Regressionstest
(`test_env_hermetic.py`), eine fail-closed Preistabelle mit `effective_from`,
ein Contract-Validator über 9 Registries. Das ist für eine Bachelorarbeit
überdurchschnittlich.

**Die Beweisführung darüber war schwach.** Vor diesem Lauf existierte kein
CI, kein Gate-Protokoll, keine versionierten Maschinenartefakte und keine
JUnit-Ausgabe. Die zentrale Aussage «TECHNISCHES GATE GRÜN» war eine Abschrift;
der einzige je erfasste Gate-Lauf endete ROT. Dieser Lauf schliesst die Lücke
für den deterministischen Teil.

**Der heutige Stand ist rot** — aus drei klar getrennten Gründen:

1. eine echte Testregression im Backend (4 deterministische Fehler, davon einer
   direkt durch die Preistabellen-Änderung des HEAD-Commits),
2. zwei reihenfolgeabhängige Tests, die die Suite unzuverlässig machen,
3. eine Regression aus der **nicht committeten** UI-Bereinigung, die nur
   Playwright sichtbar macht.

Hinzu kommen drei Mängel der Verifikationsinfrastruktur selbst: ein
Readiness-Fenster, das auf dieser Maschine zu kurz ist; eine Aufräumroutine, die
verwaiste Server hinterlässt; und zwei Gate-Zeilen, die den Status der gesamten
Backend-Suite kopieren statt ihr eigenes Ergebnis zu melden.

Für die Arbeit lässt sich das ehrlich und vertretbar formulieren: das System ist
substanziell getestet, aber der **Nachweis** dieser Tests war bis zu diesem Lauf
nicht belastbar geführt — und der aktuelle Arbeitsstand ist nicht grün.
