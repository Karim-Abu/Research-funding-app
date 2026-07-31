# UI-Bereinigung — Dichte, Wiederholungen und lange Erklärtexte

Stand: 25. Juli 2026
Scope: **frontend-only**. Keine Backend-, Contract-, DTO-, Routen-, Migrations-
oder Provider-Änderung. Keine neuen Dependencies. Mock-/Demo-Komponenten
unangetastet (RUN-4A-Entscheid gilt weiter).

Anlass: Die Oberfläche zeigte zu viel auf einmal — dieselbe Information mehrfach,
gestapelte Erklärsätze, Sekundärdetails gleichrangig neben den Kernaussagen.
RUN 4A hatte Roh-Enums und Jargon entfernt; der verbleibende Effekt war
**strukturelle Redundanz**: dieselben Daten an drei bis vier Stellen, teils im
selben Dialog.

## 1. Fünf Leitregeln

| # | Regel |
|---|---|
| R1 | Ein Abschnittskopf trägt höchstens **einen** Erklärsatz. |
| R2 | Eine Information erscheint pro Ansicht **genau einmal**; das Badge gewinnt gegen Fliesstext. |
| R3 | Pro Karte **ein** Aufklapper für Sekundäres. |
| R4 | Backend-generierte Listen: **3 sichtbar**, Rest hinter «Weitere N … anzeigen». |
| R5 | Statuslabels ausschliesslich aus den zentralen Maps. |

Nichts mit rechtlichem oder epistemischem Gehalt wurde gestrichen — nur
zusammengezogen, gekürzt oder an den Ort der Handlung verschoben. Der vollständige
Alt-→-Neu-Katalog steht in `docs/repair/message-catalog.md` (Nachtrag 2026-07-25).

## 2. Zwei Befunde jenseits der Kosmetik

**B1 — Doppelte Evidenzlücken im Marktvergleich-Dialog.**
`market-comparison-sheet.tsx` rendert `comparison.research_gaps` **und** im
`JudgmentCard` zusätzlich `judgment.open_evidence_gaps`. Backend
`market/judgment.py:230` baut `open_evidence_gaps` als **Obermenge** von
`research_gaps` — beide Listen im selben Dialog überschneiden sich zwangsläufig.
Gelöst über den neuen Selektor `marketGaps()` (`lib/market-view.ts`): eine Liste
je Fläche, Urteilsliste bevorzugt, Fallback auf `research_gaps` (damit eine leere
Urteilsliste vorhandene Lücken nie versteckt).

**B2 — Marktaussagen als «Wettbewerber» dargestellt (P1, Ehrlichkeit).**
Lagen keine Lösungskandidaten vor, fiel das Sheet auf die Fallback-Tabelle zurück
und zeigte Marktstatistiken (z. B. «Swiss biotech sector revenue 2023») unter der
Spalte **«Wettbewerber / Lösung»**. Auf `/quellen` war das bereits korrigiert;
der Kommentar in `lib/market-comparison.ts` benannte den Fehler ausdrücklich —
das Sheet zog nicht nach. Marktaussagen werden jetzt auch dort über
`candidateTypeOf()` herausgefiltert; bleibt die Tabelle leer, erscheint der
ehrliche Hinweis statt einer leeren Erfolgstabelle.

## 3. Zwei geprüfte Gegen-Entscheide

- **`market-competition-panel.tsx` wurde NICHT gelöscht.** Der Verdacht «toter
  Mock-Code» hielt der Prüfung nicht stand: `/editor` → `draft-workspace.tsx:342`
  liefert echte Mock-Daten. `MARKET_STATUS_LABELS`, `MARKET_STATUS_STYLE` und
  `summarizeMarketReadiness` bleiben deshalb ebenfalls erhalten.
- **Belegstufen-Labels bleiben bewusst asymmetrisch.** Die verknüpfte Belegliste
  trägt weiter das lange Label («Textstelle gefunden – fachliche Prüfung offen»),
  die sekundäre Auswahlliste die Kurzform. Eine Vereinheitlichung auf die Kurzform
  hätte einen epistemischen Vorbehalt auf der Primärfläche entfernt — Konsistenz
  rechtfertigt das nicht. Im Code als Kommentar festgehalten.

## 4. Geänderte Dateien

**Neu:** `components/editor/market-blocks.tsx` — `MarketPictureList` und
`MarketGapList` (`compact`-Prop nach dem Vorbild `MarketComparisonBasis`),
verwendet von Quellen-Sektion, Sheet und Editor-Rail.

| Bereich | Dateien |
|---|---|
| Öffentliche Recherche | `components/quellen/public-research-panel.tsx`, `components/research/query-approval-list.tsx`, `components/editor/market-research-panel.tsx` |
| Markt | `components/quellen/market-comparison-section.tsx`, `components/editor/market-comparison-sheet.tsx`, `components/editor/live-market-comparison.tsx`, `components/editor/market-comparison-basis.tsx`, `lib/market-view.ts`, `lib/market-comparison.ts` |
| Fördervoraussetzungen | `components/anforderungen/live-requirements.tsx`, `components/anforderungen/requirements-controls.tsx`, `lib/requirements-view.ts`, `lib/requirements.ts`, `lib/review-view.ts` |
| PRÜFEN-Sidebar | `components/editor/live-editor.tsx`, `components/editor/draft-workspace-shell.tsx`, `lib/evidence-ladder.ts`, `lib/evidence.ts` |

**Entfernte, nachweislich ungenutzte Exporte:** `COMPARISON_STATUS_LABELS`,
`marketArgumentSentence`, `marketStatusToLabel`, `marketStatusToStyle`,
`comparisonToMarketStatus`, `REVIEW_STATUS_LABELS`, `BASIS_LABELS`,
`VERIFIED_EXPLANATION`.

## 5. Tests

Neu (4 Fälle):

- `test/market-view.test.ts` — zeilenübergreifende Marktbild-Dedupe; eine Rubrik
  bleibt erhalten, sobald sie einen eigenen Wert trägt; `marketGaps()` mit
  Obermenge und Fallback.
- `test/market-comparison-sheet.test.tsx` — Evidenzlücken erscheinen genau
  einmal; Marktaussagen nie unter «Wettbewerber / Lösung».
- `test/live-requirements.test.tsx` — wortgleiche Regelzitate zusammengefasst
  (Eintrag mit URL gewinnt); Begründung aufgeklappt genau einmal.

Angepasst (Copy folgt der neuen Fassung, Testabsicht unverändert):
`test/evidence.test.ts`, `test/live-editor-a2.test.tsx`,
`test/market-research-panel.test.tsx`.

Unverändert grün und bewusst nicht angefasst: alle gepinnten Statusbegriffe
(«Systembefund», «Warum relevant?», «Regelgrundlage», «Kuratierter
Registry-Auszug», «Nicht beurteilbar», «Technische Details», die sechs Tab-Labels,
«Textstelle gefunden – fachliche Prüfung offen», «Widersprüchlich/unklar»,
«Keine Rohprojektidee, Partnernamen, Budgets oder Kontaktangaben», …).

## 6. Gates

```text
corepack pnpm exec tsc --noEmit → pass
corepack pnpm lint              → pass
corepack pnpm test              → pass (78 Dateien / 631 Tests)
corepack pnpm build             → pass
```

Hinweis zum Build: der erste Lauf brach mit `EPERM … unlink .next/server/app/import`
ab — ein OneDrive-Verzeichnislock, kein Produktfehler (gleiche Klasse wie der in
`RUN_4A_RESULT.md` §5 dokumentierte `.pytest_cache`-Fall). Nach `rm -rf .next`
lief der Build durch.

**Nicht ausgeführt:** Playwright-Gesamtlauf (braucht laufende Server + Live-Preflight)
und `scripts/verify_all.ps1`. Die betroffenen Text-Assertions sind im
Message-Katalog benannt; e2e-gepinnte Strings wurden bewusst wörtlich erhalten.

## 7. Risiken

- Playwright-Specs prüfen Copy teils über Teilstrings. Erhalten wurden alle in
  `e2e/` gefundenen Pins; ein Gesamtlauf steht aber noch aus.
- Die Marktdateien trugen beim Start einen unfertigen WIP-Stand
  (`market_comparison_v3.md`, Backend-Prompt-Snapshots). Die Bereinigung setzt
  darauf auf; der WIP wurde nicht rückgängig gemacht und ist weiterhin
  uncommittet.
- Die entfernte Begründungs-Vorschau in der zugeklappten Anforderungszeile
  reduziert Scanbarkeit im zugeklappten Zustand nicht (sie bleibt dort) —
  ausgeblendet wird sie nur, solange die Zeile offen ist.

## 8. Offen (freigabepflichtig, nicht umgesetzt)

- **P1** — Die langen «Offene Evidenzlücken»-Sätze entstehen in
  `backend/app/market/executor.py` und `judgment.py`. Das Frontend kappt und
  dedupliziert nur; kürzere Sätze wären eine Backend-/Prompt-Änderung.
- **P1** — Sauberer wäre, wenn `open_evidence_gaps` nur die *zusätzlichen* Lücken
  lieferte statt der Obermenge (Contract-Änderung).
- **P2** — Divergenz zwischen Mock-Modus-Copy und Live-Copy besteht weiter.
- **P2** — `App/backend/app/market/service.py` liegt als verwaiste Kopie
  ausserhalb des Repos.
