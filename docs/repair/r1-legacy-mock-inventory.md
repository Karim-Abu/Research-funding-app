# R1.1 — Legacy-Mock-Inventar

Stand: 2026-07-07 · Branch `repair-v2` · Keine funktionalen Änderungen (reines Inventar).

Mechanik: `lib/app-mode.ts` führt `LIVE_RESOURCES` (session, me, capabilities, projects,
sources, runs, operations, partners, requirements, evidence, fields, review, exports).
`isMock("legacy")` ist **per Konstruktion immer true** («legacy» steht nie im Set) —
jeder solche Zweig ist ein permanenter Mock-Pfad. Die Seiten verzweigen zusätzlich auf
`mode === "live"` und rendern dann Live-Komponenten; die Mock-Bodies (mit den
Legacy-Funktionen) sind nur im Mock-/Demo-Modus erreichbar.

## A. `isMock("legacy")`-Stellen (16)

| # | Datei:Zeile | Funktion/Komponente | Mock-Bedingung | Aktiver Screen betroffen (live) | Live-Ersatz vorhanden | Risiko | Empfohlene Änderung (R1.2/R1.3) |
|---|---|---|---|---|---|---|---|
| 1 | `lib/app-mode.ts:44` | `isMock()` Definition | — | — | — | — | Behalten; R1.4-Guard prüft nur Aufrufstellen in aktiven Statuskomponenten |
| 2 | `lib/api.ts:189` | `startRun` (Mock-Run-Engine) | immer true | nein — `app/quellen/page.tsx:507` nur im Mock-Zweig (`liveMode`-Guard Z. 440/421) | ja: `lib/runs.ts::createRun` | niedrig | Demo-only markieren, R1.4-Allowlist |
| 3 | `lib/api.ts:210` | `getRun` (Mock-Polling) | immer true | nein — Polling nur aus Mock-Start (Z. 380/510) | ja: `lib/operations.ts::pollOperation` | niedrig | Demo-only markieren |
| 4 | `lib/api.ts:225` | `stopRun` | immer true | nein (`liveMode`-Guard Z. 526) | ja: `cancelRun` | niedrig | Demo-only markieren |
| 5 | `lib/api.ts:236` | `resumeRun` | immer true | nein (`liveMode`-Guard Z. 544) | teilweise (live kennt kein Resume — Verhalten weicht ab) | niedrig | Demo-only markieren; Abweichung dokumentieren |
| 6 | `lib/api.ts:256` | `getProjectState` → `mockRequirements` | immer true | nein — nur `MockAnforderungen` (`app/anforderungen/page.tsx:89`; live rendert `LiveRequirements`) | ja: `lib/requirements.ts` | **mittel** (liefert Anforderungs-Status im Demo-Modus — Statusquelle) | Demo-only markieren; keine aktiven Screens umstellen nötig |
| 7 | `lib/api.ts:537` | `getRunFields` (Mock-Review-Singleton) | immer true | nein direkt — Konsumenten sind Mock-Bodies: `app/export/page.tsx:88`, `app/review/page.tsx:96`, `app/portal-transfer/page.tsx:183` | ja: `lib/review.ts::getReviewPackage`, `lib/fields.ts` | **mittel** (Quelle der Mock-Blockerzahl via `countOpenBlockers`) | Demo-only markieren; Live-Screens in R1.3 auf Status-View |
| 8 | `lib/api.ts:550` | `submitReview` | immer true | nein — `ReviewScreen` nur im Mock-Body (`app/review/page.tsx:136`) | ja: human-decisions (`lib/review.ts`) | niedrig | Demo-only markieren |
| 9 | `lib/api.ts:588` | `redraftField` | immer true | **toter Code** — kein Import in app/components | ja: `lib/redraft.ts` | niedrig | Entfernen empfohlen (separater Aufräum-Commit, nicht in R1.3 mischen) |
| 10 | `lib/api.ts:613` | `submitFeedback` | immer true | **unklar** — `FeedbackDialog` hängt in `ExportScreen` (Mock-Body); im Live-Modus existiert kein Feedback-Endpoint | **nein** (kein Live-Endpoint) | unklar | Owner-Entscheid: Feedback-Funktion im Live-Modus gewünscht? Sonst Demo-only |
| 11 | `lib/api.ts:629` | `uploadSource` | immer true | nein — Quellen-Upload live über `lib/sources.ts` | ja | niedrig | Demo-only markieren |
| 12 | `lib/api.ts:650` | `patchSection` | immer true | **toter Code** — kein Import | ja (Feld-PATCH `lib/fields.ts`) | niedrig | Entfernen empfohlen |
| 13 | `lib/api.ts:664` | `acceptSuggestion` | immer true | **toter Code** — `live-editor.tsx:260` definiert eine eigene, lokale Funktion gleichen Namens | ja | niedrig | Entfernen empfohlen |
| 14 | `components/export/export-screen.tsx:491` | Copy-Delay-Simulation | immer true (`? 300 : 0`) | nein — `ExportScreen` nur im Mock-Body von `app/export/page.tsx:130` | ja: `LiveExport`/`portal-transfer` | niedrig | Demo-only markieren |
| 15 | `components/export/export-screen.tsx:498` | Mock-Copy-Erfolg | immer true | nein (wie #14) | ja | niedrig | Demo-only markieren |
| 16 | `components/export/export-screen.tsx:509` | Mock-Copy-Protokoll | immer true | nein (wie #14) | ja | niedrig | Demo-only markieren |

## B. Statusquellen der vier Screens im LIVE-Modus (Kernbefund für R1.2/R1.3)

Kein `isMock("legacy")`, aber **fünf verschiedene Blocker-Definitionen** — deckungsgleich
mit der Baseline-Divergenz 0/2/18/12/18 (`docs/evaluation/baseline-report.md` §1):

| Screen | Datei | Heutige Quelle/Definition | Risiko | Empfehlung R1.3 |
|---|---|---|---|---|
| Dashboard | `app/page.tsx` + `lib/dashboard.ts::summarizeProjects` + `lib/projects.ts::toCardStatus` | zählt Projekte mit `warning_badge == run_stopped` — inhaltliche Blocker erscheinen nie | **hoch** | Kanonischen Status-View je Projekt anzeigen (blocker_count des aktiven Runs) |
| Anforderungen | `components/anforderungen/live-requirements.tsx` | eigene Bucket-Zählung `summary.blocked` über Requirement-Rows | **hoch** | Kopfzahl aus Status-View; Detail-Buckets dürfen bleiben |
| Qualitätsprüfung | `components/review/live-review.tsx` | `pkg.blocker_count` (ReviewPackage) direkt | mittel | Auf Status-View-Client umstellen (gleiche Zahl, eine Quelle) |
| Qualitätsprüfung (Kacheln) | `components/review/quality-summary.tsx` + Reliability-View | `RunQualitySummary.blocker_count` (12) ≠ ReviewPackage (18) | **hoch** | R1.2 klärt: ReviewPackage-Zählung ist kanonisch; Kacheln als Teilmenge kennzeichnen oder aus View lesen |
| Export | `components/export/live-export.tsx` + `lib/export-view.ts::summarizeExportReadiness` | `pkg.blocker_count`, client-seitig gemappt; Mock-Body nutzt separat `countOpenBlockers` (`lib/api.ts:531`) | mittel | `openBlockerCount`-Prop deprecaten; Status-View-Client |

## C. Mock-Daten-Importe auf Seiten/Komponenten (Kontext)

| Stelle | Befund | Risiko |
|---|---|---|
| `components/shell/app-shell.tsx` | erhält Mock-`user`/`projects` als Props, überschreibt sie aber im Live-Modus selbst (Session-User + `listProjects`, Z. 41–103) | niedrig (kein aktiver Mock-Pfad) |
| `app/page.tsx:96–98` | AppShell-Props aus `lib/mock-data` (im Live-Modus von der Shell überschrieben) | niedrig |
| `components/dashboard/project-card.tsx:25`, `components/shell/workflow-stepper.tsx:8` | `workflowSteps` aus mock-data = statische Schrittstruktur (Labels), keine Statusdaten | niedrig |
| `app/kosten/page.tsx`, `components/kosten/kosten-screen.tsx` | Kosten-Screen komplett Mock (`kosten-mock-data`), keine Live-Variante | mittel (eigener Screen, zeigt Fantasiezahlen) — Demo-only kennzeichnen |
| `app/ki-team/page.tsx`, `lib/ki-team-data.ts` | neuer Screen, vollständig statische Daten | unklar (Owner: Demo oder produktiv geplant?) |
| `app/hilfe/page.tsx`, `components/shell/placeholder-screen.tsx`, `components/partner/partner-manager.tsx:10`, `app/intake/page.tsx:3` | Shell-Props aus mock-data (nur Navigation/Anzeige) | niedrig |
| `components/anforderungen/requirements-screen.tsx`, `components/editor/draft-workspace.tsx`, `components/quellen/source-table.tsx`, `components/review/review-screen.tsx`, `components/export/export-screen.tsx` | Mock-Screens (nur im Mock-Modus gerendert) | niedrig |

## D. Konsequenzen für die nächsten Prompts

1. **R1.2 (Backend-Status-View):** kanonische Zählung = bestehende ReviewPackage-Zählung
   (`backend/app/review/package.py`); Reliability-Zahlen sind Teilmengen und dürfen die
   Kopfzahl nicht ersetzen.
2. **R1.3 (Frontend):** vier Live-Screens (Dashboard, LiveRequirements-Kopf, LiveReview,
   LiveExport) auf einen gemeinsamen Status-View-Client umstellen; `openBlockerCount`-Prop
   von `ExportScreen` deprecaten; Mock-Bodies bleiben Demo-only und werden klar markiert.
3. **R1.4 (Guard):** Allowlist = Mock-Bodies/Demo-Dateien aus Tabelle A (Zeilen «Demo-only
   markieren»); neue `isMock("legacy")`-Aufrufe in aktiven Statuskomponenten ⇒ Fail.
4. **Owner-Entscheide offen:** #10 Feedback im Live-Modus; Zukunft `app/kosten` und
   `app/ki-team` (Demo oder produktiv).
5. **Toter Code** (#9, #12, #13): Entfernung als separater kleiner Aufräum-Commit nach R1.3
   empfohlen — nicht Teil des R1.3-Scopes.
