# RUN 4A — UI-Review-Protokoll

Stand: 23. Juli 2026
Prüfgegenstand: RUN-4A-Stand `a81767d` (+ Hygiene-Commit `6bd6c3c`).
Methode: werkzeuggestützter Review entlang der Human-Review-Checkliste —
interaktive Browser-Prüfung (Playwright, `e2e/run4a-review.spec.ts`, opt-in
`RUN4A_REVIEW=1`) gegen lokale Server mit Fake-Providern und Demo-Seed,
plus die 18 statischen Screenshots (`docs/assets/run4a/`), 9 interaktive
Evidenz-Screenshots (`docs/assets/run4a/review-evidence/`), Vitest-Suite
(540 Tests grün) und Code-/Doku-Referenzen. Keine externen Provider-Calls.

Prüfmethoden-Kürzel: **I** = interaktiv (Playwright), **S** = Screenshot,
**T** = Vitest, **C** = Code-/Doku-Referenz.

## §0 Repository-Hygiene — pass

- `git diff --check`: sauber (Exit 0).
- Die ungeklärte Änderung an `docs/LIVE_LLM_SMOKE_REPORT.md` wurde
  klassifiziert: **legitimer, automatisch generierter Bericht des letzten
  blockierten Live-Versuchs** (`2026-07-22T22:34:46Z`, `provider_timeout` —
  der Nachweis hinter `COMBINED_LIVE_E2E_BLOCKED_BY_PROVIDER_TIMEOUT`), der
  jedoch den in der Akzeptanzmatrix referenzierten Gate-C-Bericht überschrieb.
  Handling: beide Stände wortgleich in einer Datei erhalten (Stub oben,
  Gate-C historisch darunter), separater Commit `6bd6c3c`
  `docs(run3c): preserve gate-c report and record provider-timeout attempt`.
  Kein Ergebnis umgedeutet.
- `git status --short` danach: **leer** — RUN-4B-Voraussetzung erfüllt.
  (Die `.pytest_cache/`-Permission-Warnung ist ein OneDrive-Verzeichnislock,
  kein Working-Tree-Eintrag; dokumentiert in `RUN_4A_RESULT.md` §5.)

## §1 Viewports — pass

18 statische Screenshots decken 6 Screens × 1440×900 / 1280×800 / 768×1024 ab
(`docs/assets/run4a/*.png`); die interaktiven Nachweise liefen bei 1280×720
(Playwright-Default) zusätzlich. [S]

## §2 Import — pass

| Punkt | Verdikt | Evidenz |
|---|---|---|
| Bearbeiten / PDF-Wert wiederherstellen / Übernahme zurücknehmen erreichbar | pass | [I,S] `import-entschieden-reversible-aktionen.png`: alle drei Buttons nach «Übernommen» sichtbar; Undo interaktiv ausgeführt → Kandidat wieder offen; [T] `import-review.test.tsx` |
| Konflikt auflösen und erneut übernehmen | pass | [I,S] `import-konflikt-bestaetigung.png`: Dialog «Bestehenden Entwurf ersetzen?» mit expliziter Bestätigung, danach erneut übernommen (RUN-2B-Pfad live belegt) |
| Projektdauer verständlich | pass | [S] strukturierte Werte im Klartext (`import-entschieden-…png`: «Management-Stunden 300 / Gesamtstunden 4300»); Dauer-Vergleich (`comparison_only`, Klartextsätze) [T] `import-review.test.tsx` + RUN-2B-Backend-Suite — die Fixture liefert keinen Datums-Konfliktfall im Browser, daher test-evidenziert |
| Keine technischen IDs/Hashes im Standardfluss | pass | [I] Assertion: `INTRO.APP.*` und `innolink-narrative-v2` nicht sichtbar; [T] «nur unter zugeklappten Technische Details» |
| Kompakt und scanbar | pass | [S] `import-1440x900.png`/`import-candidates-offen.png`: 1 Hinweiskarte, Kandidaten mit Label/Status/Fundstelle/Aktionen |

## §3 Quellen — pass

| Punkt | Verdikt | Evidenz |
|---|---|---|
| Drei Gruppen klar getrennt | pass | [S] `quellen-1440x900.png`: «Primärer Innolink-Antrag» / «Projektunterlagen» (+ «Öffentliche Recherche» bei public_source-Quellen); [T] `source-table.test.tsx` |
| Keine Rolle aus Dateinamen | pass | [C] `lib/sources-view.ts` nutzt nur `primary_application_source_id` + `data_classification.origin`; [T] `sources-view.test.ts`: public_source mit projektähnlichem Dateinamen → Öffentliche Recherche |
| Verwendung sichtbar | pass | [S] Zweck-Sätze je Gruppe («Verwendet für Import und Antragsanalyse.» usw.) |
| Supporting ≠ Application Evidence | pass | [C] Backend `evidence/scope_policy.py` (`used_as_requirement_evidence=false`, RUN-2B EVD-01/02 `passed`); UI-Gruppe «Projektunterlagen — Verwendet als Entwurfskontext.» behauptet nie Application Evidence |

## §4 Anforderungen — pass

| Punkt | Verdikt | Evidenz |
|---|---|---|
| `Erfüllt + Review offen` bleibt `Erfüllt` | pass | [T] `live-requirements.test.tsx` («nie Teilweise erfüllt», Sekundärchip «Maschinell geprüft · Bestätigung offen»); RUN-2A-Regression unverändert |
| `Nicht geprüft` nie 0/Nichterfüllung | pass | [T] `live-review.test.tsx` (not_run ≠ 0), `canonical-status.test.tsx`; [S] `anforderungen-detail-aufgeklappt.png`: Kacheln mit Icon + Text |
| Guidance getrennt von Quoten | pass | [T] `live-requirements.test.tsx` (guidance-notes, Quote 1/1 ohne Guidance) |
| Offizielle Quelle + Fundstelle erreichbar | pass | [T] `live-requirements.test.tsx`: «Quelle: …», Zitat, Registry-Version, genau ein Link «Offizielle Regel öffnen» nur bei URL — die Demo-Seed-Regeln führen keine `source_url`, daher test-evidenziert, nicht browser-reproduziert |
| Interne IDs nur in Auditdetails | pass | [I] Assertion `REQ.INNO.*` nicht sichtbar; [S] Detailansicht zeigt «Nicht erfüllt — Die Regel ist verletzt.» + Systembefund statt Codes |

## §5 Evidenz — pass

| Punkt | Verdikt | Evidenz |
|---|---|---|
| Stufen sichtbar + verständlich | pass | [I,S] `evidenz-belegstufen-definitionen.png`: «Was bedeuten die Belegstufen?» aufgeklappt mit Kurzdefinitionen aller Stufen; [T] `support-status-badge.test.tsx` (grün exklusiv «Stark gestützt») |
| Application Evidence nur Primary Application | pass | [C] `backend/app/evidence/scope_policy.py` (eingefrorene primäre Antragversion; RUN-2B `passed`) — RUN 4A hat den Scope nicht berührt |
| Rule Evidence = offizielle Regelquelle | pass | [C,T] `RuleEvidenceDto` («Kuratierter Registry-Auszug») + §4-Link |
| External Evidence als extern erkennbar | pass | [C] RUN-3B-Scope (nur Markt/SOTA/Partner bzw. gewählter Drafting-Kontext) unverändert; Recherche-Ergebnisse tragen Herkunfts-URL + Modul |
| Keine RAG-/Anchor-/Fragment-Sprache im Hauptfluss | pass | [T] Assertions (kein Roh-Enum); [C] `formatFundstelle`/`formatReviewer` neutralisieren technische Bezüge; «EvidenceAnchor/Fragment/Embedding» werden nirgends gerendert |

## §6 Marktvergleich — pass (test-/code-evidenziert)

Die drei Zustände sind im Offline-Setup nicht alle real erzeugbar (kein
Live-Provider); Evidenz daher aus der Komponenten-Testsuite mit
MSW-Fixtures — ehrlich ausgewiesen, kein Browser-Nachweis behauptet.

| Punkt | Verdikt | Evidenz |
|---|---|---|
| complete/limited/insufficient klar unterschiedlich | pass | [T] `market-comparison-section.test.tsx`: Statusbadge («Zur menschlichen Prüfung bereit» / «Begrenzte externe Evidenz» / «Zu wenig geeignete geprüfte Quellen») + unterschiedliche Hinweistexte VOR der Tabelle |
| limited ohne Items nie leere Erfolgstabelle | pass | [T] `item_count: 0` → Warnzustand + Evidenzlücken, keine Tabelle |
| Keine unbelegten Anbieter/Preise/Marktanteile | pass | [T,C] nicht belegte Zellen «nicht öffentlich belegt»/«unbestätigt»; No-Leak-Assertions (kein Provider/Modell/%) |
| Max. fünf Konsequenzen | pass | [T] sechste Konsequenz wird nicht gerendert |
| Review startet keine zweite Analyse | pass | [C] Editor-/Review-Pfade lesen nur `getLatestComparison`; Erzeugung ausschliesslich über den Quellen-Screen-Button mit sichtbarem `disabledReason` |

## §7 Qualitätsübersicht — pass

| Punkt | Verdikt | Evidenz |
|---|---|---|
| Vier primäre Kennzahlen | pass | [S] `review-1440x900.png`: Formale Blocker 9 / Fehlende Pflichtangaben 0 / Wichtige Qualitätsrisiken 5 / Offene menschliche Prüfungen 5 |
| Max. zehn Aufgaben | pass | [T] `fix-queue.test.tsx` (12 → 10); [S] priorisierte Liste mit Deep-Links |
| Jede Kennzahl führt zu Aktion | pass | [S,T] Blocker → «Zum ersten Blocker springen»/Aufgaben-Deep-Links «Im Entwurf öffnen»; Kennzahl-Hilfen (StatusHelp) erklären den nächsten Schritt |
| Reliability-Jargon nur Auditdetails | pass | [I,S] `qualitaet-technische-details-aufgeklappt.png` (claimgenaue Zahl nur aufgeklappt); [T] `quality-summary.test.tsx` (Jargon nicht sichtbar im Standardfluss) |
| `not_run` klar «Nicht geprüft» | pass | [T] `live-review.test.tsx`: Kennzahlen ohne ausgeführte Prüfung zeigen den Text «Nicht geprüft», nie 0 |

## §8 Recherche — pass

| Punkt | Verdikt | Evidenz |
|---|---|---|
| Nur ein Modul-Auswahlmuster | pass | [I] Formular offen ⇒ «Ergebnisse nach Modul» nicht vorhanden (Count 0); [T] `public-research-panel.test.tsx` |
| Ziel/Region/vier Bereiche/Suchbegriffe verständlich | pass | [I,S] `recherche-brief-formular-unicode.png`: Leitfrage, Beispiele, vier Modul-Checkboxen, optionale Suchbegriffe aufklappbar |
| Unicode/Umlaute/Leerzeichen/Paste korrekt | pass | [I] Eingabe «… Zürich/DACH (B2B) ✓ émission» bleibt wortgleich erhalten; [T] `research-text.test.ts` (Normalisierung erst beim Speichern) |
| Providerfehler ruhig und ehrlich | pass | [T] Unavailable-Banner «… Ihre Daten wurden nicht verändert.», Badge «Vorübergehend nicht verfügbar», kein Rohstatus — im Fake-Setup nicht erzwingbar, daher test-evidenziert |

## §9 Accessibility — pass

| Punkt | Verdikt | Evidenz |
|---|---|---|
| Tab-Reihenfolge logisch | pass | [I] 12 Tab-Schritte auf /review erreichen ≥ 8 interaktive Elemente in visueller Reihenfolge (Sequenz als Test-Annotation protokolliert) |
| Fokus sichtbar | pass | [I,S] `a11y-review-fokus-sichtbar.png`; `focus-visible:ring`-Muster in allen berührten Komponenten |
| Dialoge halten Fokus / geben zurück | pass mit Hinweis | [I] Fokus liegt nach dem Öffnen im Dialog (`document.activeElement` im `role="dialog"`), Escape schliesst (`a11y-quellen-details-dialog.png`); die Fokus-Rückgabe an den Auslöser ist base-ui-Standardverhalten und wurde nicht separat asserted (Hinweis, unkritisch) |
| Status nicht nur Farbe | pass | [S] alle Status tragen Icon + Text (Kacheln, Badges, Stepper); [C] dataviz-Kommentar in `review-progress-card.tsx` (feste Segmentreihenfolge + Legende) |
| Überschriftenhierarchie | pass | [I] genau ein `h1` auf /quellen und /review (asserted); h2/h3-Struktur in den Sektionen |
| Tabellen auf 768×1024 nutzbar | pass | [S] `quellen-768x1024.png`, `review-768x1024.png`; Markttabelle in `overflow-x-auto` (kein Seiten-Scroll) |
| Buttons mit klaren Verben | pass | [S] «Übernehmen», «PDF-Wert wiederherstellen», «Offizielle Regel öffnen», «Im Entwurf öffnen» … |

## Unkritische Hinweise (kein Blocker, P2)

1. Fokus-Rückgabe nach Dialog-Schluss nicht separat asserted (§9, base-ui-Standard).
2. Markt-Zustände und Recherche-Providerfehler nur test-evidenziert (offline nicht real erzeugbar) — Browser-Nachweis gehört zum Live-/Final-Lauf.
3. Regelquellen-Link nur test-evidenziert (Demo-Registry ohne `source_url`).
4. Vorbestehender Demo-Seed-Intake-Banner auf /quellen (`RUN_4A_RESULT.md` §6.6).
5. Mock-/Demo-Komponenten-Divergenz und Editor-Read-only-Marktansichten (P2, `RUN_4A_RESULT.md` §6).
6. Offene UX-Owner-Frage `open` → «Prüfung nötig» bleibt zur Bestätigung (`RUN_4A_RESULT.md` §6.1) — die gewählte Darstellung ist die ehrliche und blockiert RUN 4B nicht.

## Verdikt (§10)

Alle Checklistenpunkte bestanden; kein kritischer Befund. Die Live-Statuswahrheit
bleibt unverändert (`COMBINED_LIVE_E2E_BLOCKED_BY_PROVIDER_TIMEOUT`; Browser-01
final erst mit RUN 4B / Final-Acceptance).

```text
RUN_4A_UI_REVIEW_PASSED
RUN_4B_AUTHORIZED
```
