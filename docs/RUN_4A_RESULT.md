# RUN 4A — Ergebnis: Informationsarchitektur, Copy und ruhige Standardansichten

Stand: 23. Juli 2026
Scope: Frontend-only UI/UX-Finalisierung (RUN 4A). Keine Backend-, Contract-,
Provider-, Market-, Registry-, Evidence- oder Migrationsänderung. Keine
Live-Provider-Calls.

## Statuswahrheit (unverändert)

```text
RUN_3_TECHNICALLY_PARTIALLY_ACCEPTED
LIVE_WEB_CAPABILITY_VALIDATED
LIVE_LLM_CAPABILITY_VALIDATED
MARKET_SCOPE_OFFLINE_VALIDATED
COMBINED_LIVE_E2E_BLOCKED_BY_PROVIDER_TIMEOUT
```

RUN 4A behauptet keine bestandene Live-Abnahme und keine finale
Browser-E2E-Abnahme (Browser-01 bleibt `pending`, RUN 4B folgt separat).

## 1. Dokumentationskorrektur (erster Commit, separat)

`docs/E2E_ACCEPTANCE_MATRIX.md`:

- `AI-04` = Staleness bei Draft-/Run-/Source-/Registry-/Market-Änderung,
  `passed`, Nachweis ausschliesslich `docs/RUN_3C_OFFLINE_RESULT.md`
  (Staleness-Gates der Offline-Phase; der Dry-Run-Report enthält keinen
  Staleness-Nachweis und wurde als Quelle entfernt).
- `AI-ACCEPT-01` (neu) = Accept erzeugt idempotent genau eine neue
  DraftVersion, `passed`, erbt die bisherigen AI-04-Nachweise
  (`RUN_3C_PHASE2_DRY_RUN_RESULT.md` + `RUN_3C_OFFLINE_RESULT.md`).
- `AI-Q06` unverändert (synthetisches Evaluationsset). Keine historischen
  Ergebnisse umgedeutet.

## 2. Geänderte Screens und Komponenten

| Screen | Änderung | Dateien |
|---|---|---|
| Antrag importieren | Ein ruhiger Hinweis statt zwei Info-Karten; unbekannte strukturierte Schlüssel nie roh (snake_case) im Standardfluss; «Fundseite» → «Fundstelle»; alle RUN-2B-Aktionen (Bearbeiten / PDF-Wert wiederherstellen / Übernahme zurücknehmen) bleiben nach der Entscheidung erreichbar | `components/import/import-review.tsx` |
| Quellenliste | Neue Zweck-Gruppierung «Primärer Innolink-Antrag / Projektunterlagen / Öffentliche Recherche» ausschliesslich aus kanonischen Metadaten (`primary_application_source_id`, `data_classification.origin`) mit je einem Verwendungs-Satz; freundlicher Hinweis bei fehlendem/uneindeutigem Primärantrag; Mock-Modus bleibt flach | `lib/sources-view.ts` (neu), `components/quellen/source-table.tsx`, `app/quellen/page.tsx` |
| Öffentliche Recherche | RUN-3A-Formular unverändert; Roh-Enums (`source_quality`, `coverage_status`) und roher Firewall-Score «(N/10)» aus dem Standardfluss entfernt (Label-Maps); Provider-Badge für alle drei kanonischen Modi; ehrlicher Unavailable-Banner («…Ihre Daten wurden nicht verändert»); manueller Import auch ohne freigegebenen Brief; genau EINE Modul-Darstellung gleichzeitig (offenes Brief-Formular blendet den Ergebnisbereich aus) | `components/quellen/public-research-panel.tsx`, `components/research/query-approval-list.tsx`, `lib/research-brief.ts` |
| Anforderungsanalyse | 5er-Statuskatalog mit Kurzbegründung auf Detailebene; Sekundärstatus «Maschinell geprüft · Bestätigung offen»; Regelgrundlage mit «Quelle: …» und Link «Offizielle Regel öffnen» (nur bei Registry-URL); Guidance bleibt getrennt und zählt in keiner Quote | `lib/requirements.ts`, `lib/requirements-view.ts`, `components/anforderungen/live-requirements.tsx` |
| Evidenz | Supportleiter mit aufklappbaren Kurzdefinitionen je Stufe («Was bedeuten die Belegstufen?»); grün bleibt exklusiv «Stark gestützt»; «Textstelle gefunden» bleibt neutral | `lib/evidence-ladder.ts`, `components/quellen/live-evidence.tsx` |
| Markt- und Konkurrenzvergleich | Kompakte Tabelle (Anbieter/Alternative · Zielgruppe · Kernnutzen · Differenzierung · Geschäftsmodell · Schweiz-Relevanz · Belege · Status); Sekundärdimensionen aufklappbar pro Zeile; ehrlicher Statusbadge im Sektionskopf; Limitationshinweise VOR der Tabelle; leere limited/insufficient-Ergebnisse nie als Erfolg (Warnzustand + Evidenzlücken); max. 5 Konsequenzen («Was das für den Antrag bedeutet»); A11y-Labels je Zeilenaktion | `lib/market-comparison.ts`, `components/quellen/market-comparison-section.tsx` |
| Qualitätsübersicht | Vier primäre Kennzahlen (Formale Blocker / Fehlende Pflichtangaben / Wichtige Qualitätsrisiken / Offene menschliche Prüfungen) aus kanonischen Statusdaten; nicht ausgeführte Prüfungen zeigen «Nicht geprüft» statt 0; Aufgabenliste bis 10 Einträge mit Abschnitt und Aktion; Reliability-Jargon (Suffizienz, Konsensrisiko, Drift, Claim-Zahlen) in aufklappbare Audit-/Technik-Details verlagert (nicht gelöscht) | `components/review/live-review.tsx`, `components/review/review-progress-card.tsx`, `components/review/quality-summary.tsx`, `lib/review-view.ts` |
| Infrastruktur | ESLint ignoriert `.pytest_cache` (OneDrive-EPERM brach sonst den Lint-Lauf ab); opt-in Visual-Spec | `eslint.config.mjs`, `e2e/run4a-visual.spec.ts` (neu) |

Nicht verändert: Backend/BFF/DTOs/Routen, `WORKFLOW_STEPS` (6-Schritte-
Navigation), Routing, Dependencies, Mock-Demo-Komponenten, Editor-Read-only-
Marktansichten, kanonische Zähl-/Gate-Logik, Live-/Fake-Semantik,
`verify_all.ps1`.

## 3. Copy-/Statuskatalog (alt → neu)

Wichtig als Input für RUN-4B-E2E-Anpassungen (Text-Assertions):

| Ort | Alt | Neu |
|---|---|---|
| Requirement-Status `needs_input` | Angaben nötig | Nicht beurteilbar |
| Requirement-Status `blocked` | Blockiert | Nicht erfüllt |
| Requirement-Status `open` | Offen | Prüfung nötig |
| Requirement-Sekundärstatus | Maschinell geprüft · Menschliche Bestätigung offen | Maschinell geprüft · Bestätigung offen |
| Requirement-Detail | — | Neu: Label + Kurzbegründung (`STATUS_REASONS`) |
| Import-Fundstelle | Fundseite: … | Fundstelle: … |
| Import-Hinweise | 2 Info-Karten («N Kandidaten erkannt…» + Run-Hinweis) | 1 Karte; Run-Hinweis als zweiter Satz («Übernommene Inhalte fliessen …» unverändert) |
| Recherche-Badge (unavailable) | Nicht verfügbar | Vorübergehend nicht verfügbar |
| Recherche `source_quality` | Roh-Wert (de-underscored) | Wissenschaftliche Quelle / Offizielle Stelle / Institutionell (ungeprüft) / Noch nicht bewertet |
| Recherche `coverage_status` | Roh-Enum (`exact_quote_verified`) | Textstelle exakt gefunden / Nicht geprüft |
| Firewall-Risiko | Risiko niedrig (3/10) | Risiko niedrig (Score nur intern) |
| Markt-Spalten | Eintrag/Kategorie/Kurzbeschreibung/Relevanz/Differenzierungshinweis/Vergleichsdimensionen/Quelle/Status | Anbieter/Alternative · Zielgruppe · Kernnutzen · Differenzierung · Geschäftsmodell · Schweiz-Relevanz · Belege · Status |
| Markt `limited` | Begrenzter Vergleich: Es liegen nur zwei geeignete externe Quellen vor. | Begrenzte externe Evidenz: Es liegen geprüfte Marktquellen vor, aber der Konkurrenzvergleich ist noch nicht vollständig. |
| Markt `insufficient` | Zu wenige extern geprüfte Quellen: Es wurden keine Vergleichsaussagen erzeugt. | Für einen belastbaren Marktvergleich fehlen geeignete geprüfte Quellen. |
| Markt-Statusbadge | — | Neu: `COMPARISON_STATUS_LABELS` (Entwurf / Zur menschlichen Prüfung bereit / Begrenzte Datenlage-Badge «Begrenzte externe Evidenz» / Zu wenig geeignete geprüfte Quellen / Veraltet / Fehlgeschlagen) |
| Qualität Kennzahlen | Blockierende Aufgaben / Unterliegende Evidenzhinweise / Prüfung nötig | Formale Blocker / Fehlende Pflichtangaben / Wichtige Qualitätsrisiken / Offene menschliche Prüfungen (Evidenzhinweise in «Technische Details») |
| Qualität Jargon | «Beleg-Suffizienzprüfung … Konsensrisiko … Semantische Drift» sichtbar | Nur in «Technische Details (Audit)» (aufklappbar) |
| Nächste Aufgaben (Review) | Top 5 | Top 10 |

Kanonische Enums/Contracts sind unverändert — alle Änderungen sind reine
View-Model-/Anzeige-Strings.

## 4. Visuelle Nachweise

`docs/assets/run4a/` — 18 Screenshots (6 Screens × 1440×900 / 1280×800 /
768×1024), erzeugt mit `e2e/run4a-visual.spec.ts` (opt-in `RUN4A_VISUAL=1`)
gegen lokal gestartete Server (uvicorn :8000 + `next start` :3000,
Fake-Provider, Demo-Seed `python -m app.demo.seed --reset`, Wegwerf-DB
`backend/var/run4a_visual.db`). Keine externen Provider-Calls.

Screens: `dashboard`, `anforderungen`, `evidenz`, `quellen` (Zweck-Gruppierung
sichtbar), `import`, `review` (vier Kennzahlen + Top-Aufgaben sichtbar).

## 5. Tests

Neu/erweitert (alle grün):

- `test/requirements.test.ts` — 5er-Statuskatalog + Kurzbegründungen.
- `test/live-requirements.test.tsx` — Statussprache (open/blocked, nie
  Roh-Enums), Regelgrundlage mit genau einem «Offizielle Regel öffnen»-Link,
  `fulfilled + required` bleibt «Erfüllt», Guidance zählt in keiner Quote.
- `test/import-review.test.tsx` — reversible Aktionen nach Entscheidung
  sichtbar; Feld-ID/Mapping-Version nur im zugeklappten «Technische Details».
- `test/sources-view.test.ts` (neu) + `test/source-table.test.tsx` —
  Dreier-Gruppierung nur aus Metadaten (public_source mit projektähnlichem
  Namen → Öffentliche Recherche), Primärantrags-Hinweis, Mock bleibt flach.
- `test/public-research-panel.test.tsx` — keine Roh-Enums/Scores,
  Unavailable-Banner ohne Rohstatus + manueller Import ohne Brief, genau eine
  Modul-Darstellung; Unicode-/Whitespace-Verhalten unverändert grün.
- `test/live-evidence.test.tsx` + `test/support-status-badge.test.tsx` —
  Supportleiter-Definitionen sichtbar, `location_found` nie grün.
- `test/market-comparison-section.test.tsx` — Mandats-Spalten, max. 5
  Konsequenzen, Statusbadge, `limited` mit `item_count 0` nie als Erfolg,
  `insufficient`-Wortlaut.
- `test/live-review.test.tsx` + `test/quality-summary.test.tsx` +
  `test/fix-queue.test.tsx` — vier Kennzahlen, `not_run` ≠ 0, Jargon nur im
  `<details>`, max. 10 Aufgaben mit Aktion.

Gates (Frontend-only, offline):

```text
corepack pnpm lint            → pass (nach .pytest_cache-Ignore-Fix)
corepack pnpm exec tsc --noEmit → pass
corepack pnpm test            → 73 Dateien / 540 Tests pass
corepack pnpm build           → pass
```

Nicht ausgeführt in RUN 4A (bewusst, gemäss Mandat): `scripts/verify_all.ps1`
(erst am Ende von RUN 4B), Playwright-Gesamtlauf, Live-Provider-Smokes.

Host-Infrastruktur (ehrlich, kein Produktfehler): das Verzeichnis
`.pytest_cache/` im Repo-Root ist unter OneDrive zeitweise gesperrt (EPERM
beim scandir) und brach den ESLint-Gesamtlauf ab; behoben über einen
Ignore-Eintrag in `eslint.config.mjs`.

## 6. Offene UX-Fragen (für Review / RUN 4B)

1. **`open`-Label:** Der Mandats-Katalog nennt «Nicht erfüllt — Die Regel ist
   verletzt»; das Backend nutzt `open` aber auch für «menschliche Entscheidung
   nötig» und «semantisch nicht bewertet» (`backend/app/rules/aggregation.py`).
   RUN 4A labelt `open` deshalb ehrlich als «Prüfung nötig» und reserviert
   «Nicht erfüllt» für `blocked`. Owner-Bestätigung erbeten.
2. **Bucket-Kachel «Offen»:** Die 4er-Zusammenfassung (Tiles/Filter) behält
   «Offen» (fasst `open` + `needs_input`); die präzisen Labels erscheinen auf
   Detailebene. Alternative (Kachel «Prüfung nötig») wäre ein Owner-Entscheid.
3. **«Nicht konfiguriert» (Recherche):** Der Contract kennt nur
   `live | fake_demo | unavailable` — ein separater Zustand «Nicht
   konfiguriert» ist ohne additive Contract-Änderung nicht darstellbar
   (kein `UI_CONTRACT_GAP_FOUND`-Stopp nötig: `unavailable` deckt den Fall
   ehrlich als «Vorübergehend nicht verfügbar» ab).
4. **Mock-/Demo-Komponenten:** bewusst unangetastet (Divergenz zur neuen
   Live-Copy dokumentiert, P2).
5. **Editor-Read-only-Marktansichten** (`live-market-comparison.tsx`,
   `market-comparison-sheet.tsx`): profitieren von den neuen Status-Labels,
   wurden aber nicht auf die neue Tabellenstruktur umgebaut (P2, ggf. RUN 4B).
6. **Demo-Seed-Intake-Banner:** Auf `/quellen` erscheint für geseedete
   Demo-Projekte der Hinweis «Noch keine Projektangaben vorhanden» (Intake-
   Store ist browserseitig leer) — vorbestehendes Verhalten, nicht RUN 4A
   (P2, im Screenshot sichtbar).

## 7. Risiken

- Label-Änderungen (Katalog in §3) können bestehende Playwright-Text-
  Assertions in RUN 4B brechen — der Katalog ist die Anpassungsliste.
- `humanReviewCount`, `blocker_count`, `blocking_task_count`, Bucket-Folding
  und alle Gate-Kriterien sind unverändert (nur Anzeige-Strings).
- Neue Kennzahl «Wichtige Qualitätsrisiken» summiert offene Warnhinweise der
  kanonischen Prüfbereiche; sie ist bewusst KEINE neue fachliche Bewertung.

## 8. Abschlussstatus

Kein Anspruch auf finale E2E-/Live-/Produktabnahme. RUN 4B (Schreibassistent,
Vergleichsansicht, Browser-Flows) folgt nach dem UI-Review.

```text
RUN_4A_COMPLETE
READY_FOR_RUN_4A_UI_REVIEW
```
