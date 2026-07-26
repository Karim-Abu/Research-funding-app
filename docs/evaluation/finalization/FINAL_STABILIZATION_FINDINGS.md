---
title: "Final-Stabilisierung — Findings"
date: 2026-07-26
branch: stabilize/eval3-final-01
status: partial-paused
tags: [eval3, stabilization, findings]
---

# Final-Stabilisierung — Findings

Stand: 2026-07-26, Branch `stabilize/eval3-final-01` (4 Commits).
Vorlauf: [[EVAL3_TECHNICAL_VERIFICATION]] (EVAL3-PRE-01, unverändert erhalten).

> **Lauf pausiert.** Am Markt-UI wird parallel refaktoriert; der Baum ist zurzeit
> nicht übersetzbar (12 `tsc`-Fehler in `components/editor/live-market-comparison.tsx`,
> fremde Änderung). Phasen 5–8 (verify_all-Reparatur, Re-Verifikation, Tag)
> stehen aus. Details unten unter «Offen».

## 0. Der angenommene Ausgangsstand war überholt

Der Auftrag nannte 34 nicht committete Dateien. Tatsächlich vorgefunden:

- Der gesamte Stand war zwischenzeitlich als `956ed75` committet (106 Dateien).
- Seit PRE-01 war ein **Produktwechsel** dazugekommen (2026-07-26): der manuelle
  «Stützt / Teilweise / Stützt nicht»-Review-Schritt entfiel;
  `import_service._auto_review_if_safe` markiert importierte,
  nicht-quarantänisierte Treffer automatisch als `reviewed`/`supports`.
- Deshalb wurde **vor jeder Reparatur neu gemessen** (`PRE02-BACKEND-01`)
  statt auf den PRE-01-Zahlen aufzusetzen.

## 1. Findings

| ID | Befund | Kategorie | reproduzierbar | Ursache | gewünschtes Verhalten | Datei | Fix |
|---|---|---|---|---|---|---|---|
| F-01 | `test_live_readiness::test_fresh_persisted_route_preflight_expires` erwartet `pricing_version "test-v1"` | `stale-test` | ja | `resolve_cost` ist seit `8416914` USD-first; die injizierte CHF-Tabelle bepreist nichts mehr → `price_version=None` → Fallback | Route über eine echte Katalog-Id armieren | `backend/tests/test_live_readiness.py` | **behoben** |
| F-02 | `test_eval2_real_smoke::…meters_schema_failure` erwartet Modell der angefragten Route | `stale-test` | ja | `gateway` verbucht seit `8416914` `result.model` (provider-bestätigt); der nackte `FakeProvider` meldet `"fake"` | Adapter echot eine unterscheidbare Id | `backend/tests/test_eval2_real_smoke.py` | **behoben** |
| F-03 | `test_live_llm_phase2_full_dry_run` bricht mit `unknown_price` ab | `stale-test` | ja | Harness prüft vor jedem Call den Preis; die Fantasie-Modelle sind nicht katalogisiert | Katalog-Ids im Kind-Environment | `backend/tests/test_live_llm_phase2_full_dry_run.py` | **behoben** |
| F-04 | `test_a2_generation::test_preflighted_synthetic_live_a2…` → `live_price_metadata_missing` | `stale-test` | ja | dieselbe Ursache wie F-01, über `route_configuration_reason` | Katalog-Ids, `requested != actual` erhalten | `backend/tests/test_a2_generation.py` | **behoben** |
| **F-05** | **Erfundene Zahlen passieren den Halluzinationsschutz sporadisch** | **`product-defect`** | ja (~5 %/Lauf) | `allowed_facts` baute die Erlaubt-Basis aus dem rohen INPUT-Payload; UUID-Ziffern und Telemetrie galten als erlaubte Zahlen, `_is_derivable` erzeugte daraus weitere | nur inhaltstragende Felder dürfen Zahlen erlauben | `backend/app/agents/field_drafting_context.py` | **behoben** |
| F-06 | `test_demo_seed::test_isolated_test_db…` schlägt in der Vollsuite fehl | `test-isolation-defect` | ja | `_verify_project_presence` zählt unter `APP_ENV=test` alle Projekte; die sessionweite DB enthält fremde Testprojekte | Test läuft auf eigener DB, Produktregel unangetastet | `backend/tests/test_demo_seed.py` | **behoben** |
| **F-07** | **A1-Route in der laufenden App nicht verfügbar** | **`product-defect`** | ja | `backend/.env` konfiguriert `claude-haiku-4-5-20251001`; diese Id fehlte im USD-Katalog → `live_price_metadata_missing` → Route `not_configured` | Route ist bepreisbar | `backend/app/evaluation/pricing.py` | **behoben** |
| F-08 | Golden-Path bricht nach der UI-Bereinigung | `incorrect-test-expectation` | ja | `getByText("Freigegeben")` traf case-insensitiv den Fliesstext «Firewall: **freigegeben**», nicht das Badge; zusätzlich verlor der Zeilenfilter die Zeile bei Statuswechsel | Status wird am Badge geprüft | `e2e/golden-path.spec.ts`, `components/research/query-approval-list.tsx` | **behoben** |
| **F-09** | **128 MB DB-Sicherungen mit vertraulichen Echtprojekten im Repo** | **`product-defect` (Datenhygiene)** | ja | `.gitignore`-Regel `*.db` greift nicht bei Zeitstempel-Suffix | keine DB im Repo | `backend/.gitignore` | **teilweise behoben** — siehe §2 |
| F-10 | Readiness-Fenster 40×2 s, sequenziell, `catch {}` stumm | `environment-defect` | ja | fixes Zeitfenster zu kurz für diese Umgebung | konfigurierbar, je Dienst, mit Grund | `scripts/verify_all.ps1:129-136` | **offen** |
| F-11 | Serverstart ohne `-PassThru`/Umleitung → Absturz unsichtbar | `gate-reporting-defect` | ja | keine PIDs, keine Ausgabe | PIDs + Logs je Lauf | `scripts/verify_all.ps1:122,125` | **offen** |
| F-12 | verwaiste Server nach Gate-Lauf | `environment-defect` | ja | **Race**, nicht Locale: `Stop-Servers` lief, bevor die Prozesse existierten | PID-basiertes, idempotentes Cleanup | `scripts/verify_all.ps1:40-47` | **offen** |
| F-13 | `export smoke` / `no-raw-log` = Alias auf `$R.backend` | `gate-reporting-defect` | ja | `$exportR = $R.backend` | eigene Testergebnisse | `scripts/verify_all.ps1:176` | **offen** |
| F-14 | `"skip"` besteht das Gate | `gate-reporting-defect` | ja | Filter prüft nur `FAIL*` | Abbruch zählt als rot | `scripts/verify_all.ps1:239-242` | **offen** |
| F-15 | kein `exit 0` auf dem grünen Pfad | `gate-reporting-defect` | ja | letzter `$LASTEXITCODE` schlägt durch | grün ⇒ 0 | `scripts/verify_all.ps1:247` | **offen** |
| F-16 | `role_model_eval/summary.json` existiert nie | `gate-reporting-defect` | ja | Pfad zeigt auf ein nie erzeugtes File (nur `..._pilot/`) | korrekter Pfad | `scripts/verify_all.ps1:187` | **offen** |
| F-17 | Alembic-/Seed-Exitcodes verworfen | `gate-reporting-defect` | ja | Rückgabewerte nicht ausgewertet | Fehler färbt das Gate | `scripts/verify_all.ps1:105-106` | **offen** |
| F-18 | `AGENT_MODEL_*_ID` unter Windows nicht neutralisiert | `environment-defect` | ja | `.ps1` kann leere Strings nicht setzen; `.sh` räumt sie ab | Hermetik auf beiden Plattformen | `scripts/verify_all.ps1:78` | **offen** |
| F-19 | `verify_all.sh:54` `grep -E "LISTENING"` | `environment-defect` | ja | deutsches Windows meldet `ABHÖREN` | locale-unabhängig | `scripts/verify_all.sh:54` | **offen** |
| F-20 | Marker-Guard grün mit 0 Markern | `accepted-limitation` | ja | Katalog in `testdata-policy.md` bewusst leer (`TODO(Owner)`) | Owner-Entscheid | — | **offen (bewusst)** |
| F-21 | Dataset-Spec ≠ Messung (5 Kennzahlen) | `specification-drift` | ja | Spec nie nachgeführt | Spec an Realität angleichen oder Abweichung erklären | `docs/evaluation/Evaluation_Dataset.md` | **offen** |
| F-22 | 64 Portal-Quality-Gates contract-only | `scope-gap` | ja | `loader.py` liest nur `official_core_rules` | bewusst nicht implementiert | — | **akzeptiert** |
| F-23 | keine parallelen KI-Textvarianten | `scope-gap` | ja | Funktion nie gebaut | bewusst nicht implementiert | — | **akzeptiert** |
| F-24 | PRE-01 §3.1 nannte die Locale-Falle als Ursache der verwaisten Server | `corrected-finding` | — | `.ps1` nutzt `Get-NetTCPConnection -State Listen` (typisiert, locale-unabhängig); die Locale-Falle steckt nur in der `.sh` | Korrektur dokumentieren, PRE-01 nicht umschreiben | — | **korrigiert (hier)** |
| F-25 | Dashboard-Vitest sporadisch rot | `test-isolation-defect` | teilweise (1 bzw. 3 Fehler in zwei Vollläufen, isoliert grün) | nicht untersucht — ausserhalb des beauftragten Umfangs | eigener Arbeitsschritt | `test/dashboard.test.tsx` | **offen** |

## 2. F-09 im Detail — Datenhygiene

| Datei | Grösse | Zustand |
|---|---|---|
| `backend/app.db.bak-20260726010529` | 50,0 MB | war in `956ed75`; **vor dem Push aus dem Commit entfernt** |
| `backend/app.db.bak-2026-07-23` | 37,0 MB | in `30f6ded`, **bereits auf `origin/main`** |
| `backend/app.db.bak-market-runid-2026-07-24` | 40,8 MB | in `8416914`, **bereits auf `origin/main`** |

Jede enthält 401–405 Projekte, davon **6 `confidential/real_project`** und
1 `public/real_project`. Keine Secrets, keine `.env` im Commit (geprüft).

Erledigt: alle drei aus dem Arbeitsbaum genommen, `backend/.gitignore` fängt
`app.db.bak-*` ab, Dateien lokal erhalten.

**Offen:** Die beiden älteren Blobs bleiben in der Historie erreichbar. Das
Repository ist laut Owner privat und nur ihm zugänglich, die Dringlichkeit
daher begrenzt. Eine Bereinigung erfordert einen History-Rewrite:

```
git filter-repo --path-glob 'backend/app.db*' --invert-paths
git push --force-with-lease origin main
```

Das invalidiert alle bestehenden Commit-Hashes — auch die in EVAL3-PRE-01
zitierten (`8416914`). Deshalb bewusst **nicht** ohne separate Freigabe.

## 3. Fix-Nachweise

| Test | ursprünglicher Fehler | Ursache | Änderung | isoliert | Vollsuite |
|---|---|---|---|---|---|
| `test_live_readiness::…preflight_expires` | `'2026-07-25.1' == 'test-v1'` | F-01 | Katalog-Id `gpt-5.6-luna`, Erwartung `2026-07-24.gpt56-luna` | ✅ 26 Tests | ✅ |
| `test_eval2_real_smoke::…schema_failure` | `'fake' == 'claude-haiku-4-5-20251001'` | F-02 | Adapter echot `actual-anthropic-model` | ✅ 12 Tests | ✅ |
| `test_live_llm_phase2_full_dry_run` | Exit 1, `reason_code=unknown_price` | F-03 | Katalog-Ids, inertes CHF-Mapping entfernt | ✅ 2 Tests | ✅ |
| `test_a2_generation::…truthfully_model_generated` | `live_price_metadata_missing` | F-04 | `gpt-5.6-terra` / `gpt-5.6-sol` | ✅ 20 Tests | ✅ |
| `test_demo_seed::test_isolated_test_db…` | `expected exactly two projects` | F-06 | eigene Wegwerf-DB via `tmp_path` | ✅ 8 Tests | ✅ |
| `test_a2_sections[…invented_numeric_token]` | `succeeded == failed` | F-05 | `_facts_only` filtert Kennungen aus der Erlaubt-Basis | ✅ | ✅ |
| `test_eval1_pricing::test_missing_price…` | *neu* durch F-07-Fix | Beispiel-Id wurde katalogisiert | Id → `model-without-catalogue-entry` | ✅ | ✅ |
| `test_eval1_usage_records::…unknown_price` | *neu* durch F-07-Fix | dito | dito | ✅ | ✅ |

**Keine Assertion wurde entfernt oder abgeschwächt.** Die `unknown_price`-
Abdeckung blieb erhalten, indem die Beispiel-Id umbenannt wurde statt die
Zusicherung zu ändern. `requested != actual` blieb in allen Preflight-Tests
erhalten, damit weiterhin belegt ist, dass das tatsächlich bestätigte Modell
verbucht wird.

## 4. Messungen

| Lauf | Ergebnis | Artefakt |
|---|---|---|
| `PRE02-BACKEND-01` (vor Reparatur) | **6 Fehler**, 1514 Tests, 4 skipped | `runs/PRE02-BACKEND-01/` |
| `FIX-BACKEND-01` (Zwischenstand) | 2 Fehler (Folge des Katalogeintrags) | `runs/FIX-BACKEND-01/` |
| **`FIX-BACKEND-02`** (nach Reparatur) | **1514 Tests, 0 Fehler, 4 skipped, 375 s** | `runs/FIX-BACKEND-02/` |
| `FIX-VITEST-01 / -02` | 1 bzw. 3 Fehler (F-25, isoliert grün) | `runs/FIX-VITEST-*/` |
| `tsc` / `lint` | grün — **vor** dem fremden Markt-Umbau | — |

## 5. Offen — Voraussetzung für EVAL3-FINAL-01

1. **Markt-Refactor abschliessen.** `components/editor/live-market-comparison.tsx`
   referenziert 12 Symbole, die der gekürzte Import-Block nicht mehr bereitstellt
   (`marketPictureFrom`, `cn`, `MarketComparisonBasis`, `judgmentToneClass`,
   `JUDGMENT_STATUS_LABELS`, `MARKET_STALE_BADGE`, `MarketPictureList`,
   `MarketGapList`, `marketGaps`, `marketStaleExplanation`, `CONFIDENCE_LABELS`,
   `marketStaleExplanation`). Solange `tsc` rot ist, sind Frontend-, E2E- und
   Gate-Messungen wertlos.
2. **Phase 5** — `verify_all.ps1` reparieren (F-10 bis F-19).
3. **Phase 6** — Re-Verifikation mit dem reparierten Gate.
4. **Phase 7** — Tag `EVAL3-FINAL-01` auf einem grünen, sauberen Baum.
5. **Phase 8** — FINAL-Bericht und Delta zu EVAL3-PRE-01.

Solange 1 offen ist, wäre jedes Einfrieren ein Einfrieren eines defekten Standes.
