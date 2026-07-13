# Demo-Acceptance-Report — Golden Path reproduzierbar & demonstrierbar

Nachweis, dass der Golden Path reproduzierbar und demonstrierbar ist. Evidenz
verweist auf Tests, Skripte und Dokumente im Repo. Fake-Provider, keine externen
Schlüssel. Datum des letzten Nachweislaufs: 2026-07-13.

## Zusammenfassung je Aufgabenpunkt

| # | Aufgabe | Ergebnis | Evidenz |
|---|---------|----------|---------|
| 1 | Playwright-Golden-Path (Fake-LLM + Fake-Web, deterministisch, ohne Keys) | **Pass** | [`e2e/golden-path.spec.ts`](../../e2e/golden-path.spec.ts) + [`e2e/helpers.ts`](../../e2e/helpers.ts); lokal 2× grün (17,5 s / 21,7 s / 22,1 s). |
| 2 | Separater opt-in Real-Provider-Smoke; Ausfall macht Gate nicht rot, wird klar berichtet | **Pass** | [`scripts/run_provider_availability_smoke.py`](../../scripts/run_provider_availability_smoke.py) → `backend/var/evaluation/provider_availability_summary.md`; ohne Opt-in 3× «übersprungen», Exit 0. |
| 3 | Demo-/Dummy-/synthetic_eval-/Preis-unbekannt-Texte aus dem Standardmodus entfernen | **Pass** | Sechs Workflow-Phasen im Live-Modus bereits sauber; Eval-Ansichten (`/admin`, `/kosten`, `/antragsentwurf`) hinter Flag [`lib/flags.ts`](../../lib/flags.ts) `evalViews` (Default aus) — Sidebar-Link in [`components/shell/sidebar.tsx`](../../components/shell/sidebar.tsx) ausgeblendet. |
| 4 | Loading-/Empty-/Error-/Retry-Zustände der sechs Phasen | **Pass** | Bestehende Retries verifiziert (s. Checkliste); ergänzt: Budget-Precheck-/Ladefehler und Partner-Ladefehler mit «Erneut versuchen» ([`components/partner/budget-form.tsx`](../../components/partner/budget-form.tsx), [`components/partner/partner-manager.tsx`](../../components/partner/partner-manager.tsx)). |
| 5 | Modalhöhe, sticky Footer, Tastaturbedienung, lange 25'000-Zeichen-Felder | **Pass** | [`e2e/ui-states.spec.ts`](../../e2e/ui-states.spec.ts): Dialog ≤ Viewport, Footer sichtbar, Escape schliesst; SOL-Feld (Limit 25'000) mit Limit-Warnung + deaktiviertem Speichern. |
| 6 | Production-Build-Hänger beheben oder Ursache mit minimalem Fix dokumentieren | **Pass** | Kein Hänger reproduzierbar: `corepack pnpm build` läuft mit frischem `.next` in ~50 s sauber. Ursache des bekannten Fehlers ist ein OneDrive-`EPERM`-Lock auf stalem `.next` (Milestone_9D_1). Minimaler Fix: `.next`-Bereinigung vor dem Build in beiden `verify_all`-Skripten. |
| 7 | `scripts/verify_all.sh` als Abschlussgate | **Pass** | [`scripts/verify_all.sh`](../../scripts/verify_all.sh) + [`.ps1`](../../scripts/verify_all.ps1) um `.next`-Cleanup und Golden-Path-2.-Lauf ergänzt; Abschlussgate-Ergebnis unten. |
| 8 | `docs/demo/demo-runbook.md` | **Pass** | [`demo-runbook.md`](demo-runbook.md) (Voraussetzungen, .env ohne Secrets, Startbefehle, Health-Check, 10-Min-Ablauf, Fallback, Backup-Run, Limitationen). |
| 9 | `docs/demo/demo-acceptance-report.md` mit Pass/Fail + Evidenz | **Pass** | Dieses Dokument. |
| 10 | README für frischen Rechner (Frontend, Backend, Migration, Seed, Live-Modus) | **Pass** | [`README.md`](../../README.md). |

## Akzeptanzkriterium

- **Golden Path läuft zweimal hintereinander auf einer frischen Demo-DB:**
  erfüllt. Die Playwright-Suite im Gate ist Lauf 1; die `verify_all`-Skripte
  hängen einen expliziten zweiten Golden-Path-Lauf an (Summary-Zeile «golden
  path (2nd run)»). Eindeutige, zeitgestempelte Projekttitel machen den zweiten
  Lauf kollisionsfrei. Lokal zusätzlich mit `--repeat-each=2` bestätigt (2/2 grün).
- **Provider-Ausfall:** ein klar gekennzeichneter Fake-/manueller Fallback bleibt
  verfügbar; der Fake-Provider ist Demo-Default und in der UI ehrlich als
  Test-/Synthetik-Pfad beschriftet — keine Täuschung über die Datenquelle.

## Zustands-Checkliste der sechs Phasen (Aufgabe 4)

| Phase | Loading | Empty | Error | Retry |
|-------|---------|-------|-------|-------|
| Projekt & Unterlagen (Intake/Import/Quellen) | ✓ (Import-Skeleton/Phasen) | ✓ | ✓ | ✓ (`UploadErrorNotice`, Intake-Fehlerbanner) |
| Partner & Budget | ✓ | ✓ («Noch keine Partner erfasst») | ✓ | ✓ **neu** (Budget-Precheck/-Ladefehler, Partner-Ladefehler) |
| Analyse & Recherche (Anforderungen) | ✓ | ✓ | ✓ | ✓ (`live-requirements.tsx`) |
| Antragsentwurf (Editor) | ✓ | ✓ | ✓ | ✓ (`live-editor.tsx`) |
| Qualitätsprüfung (Review) | ✓ | ✓ | ✓ | ✓ (`live-review.tsx`) |
| Innolink-Übernahme (Export/Kopieransicht) | ✓ | ✓ | ✓ | ✓ (`export-screen.tsx`) |

## Echtes Innolink-PDF (lokal verifiziert, nicht committet)

Das echte SEDATE-PDF liegt git-ignoriert unter `private_inputs/`. Der
**produktive** Import-Code ([`backend/app/imports/mapping.py`](../../backend/app/imports/mapping.py))
liefert darauf **5 von 8 Feldern automatisch nutzbar** (deckungsgleich mit
[`pdf-import-gate-report.md`](../evaluation/pdf-import-gate-report.md)):

| Feld | Konfidenz | Zeichen |
|------|-----------|---------|
| INTRO.APP.NAME | nicht gefunden (kein Label im Export) | – |
| INTRO.APP.NAME_EN | found | 6 |
| INTRO.APP.ABSTRACT | found | 297 |
| INTRO.APP.EXECUTIVE_SUMMARY | found | 1586 |
| ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS | uncertain (Feld leer) | 0 |
| VC.BUSINESS_TARGETS_MODEL.EDITOR | found | 22283 |
| SOL.INNOVATION_SOLUTION.EDITOR | found | 20738 |
| PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION | uncertain (Feld leer) | 0 |

Reproduktion (lokal, kein Repo-Artefakt mit Inhalt):
`backend\.venv\Scripts\python.exe spike\map_pdf.py "<pfad-zum-pdf>"`.
Der E2E-Test nutzt bewusst das **synthetische** Fixture (`spike/fixtures/innolink_sample.pdf`,
8/8), damit keine echten Antragsdaten ins Repo gelangen (Testdaten-Policy E-12).

## Abschlussgate `verify_all`

`scripts/verify_all.sh` am 2026-07-13, Exit 0, **ALL GREEN**:

```
================ M10 VERIFICATION SUMMARY ================
backend tests            : pass
migration                : pass
frontend tests (vitest)  : pass        (61 Dateien, 388 Tests)
build/typecheck/lint     : pass
Playwright               : pass        (42 Tests, inkl. golden-path #9, ui-states #41/#42)
golden path (2nd run)    : pass        (e2e/golden-path.spec.ts, 2. Lauf auf frischer DB)
API smoke                : pass        (18/18)
export smoke             : pass        (test_m10_smoke.py::test_export_all_types)
no-raw-log               : pass        (test_m10_smoke.py::test_no_raw_log)
testdata markers         : pass        (scripts/check_testdata_markers.py)
legacy status guard      : pass        (scripts/check_legacy_status_paths.py)
evaluation summary       : backend/var/evaluation/EvaluationRunSummary.json
=========================================================
ALL GREEN
```

Damit ist das Akzeptanzkriterium belegt: Der Golden Path lief innerhalb **eines**
Gate-Durchgangs auf **einer frischen** `verify_e2e.db` **zweimal** durch — als
Test #9 der Playwright-Suite (Lauf 1) und als expliziter zweiter Lauf danach.

## Manuelle Prüfschritte

- Runbook Abschnitt 5 Schritt für Schritt in einer Live-Vorführung nachvollziehen.
- Weitere Beispiel-PDFs in `private_inputs/` ablegen und mit `spike/map_pdf.py`
  messen; Quote im Gate-Report ergänzen.
