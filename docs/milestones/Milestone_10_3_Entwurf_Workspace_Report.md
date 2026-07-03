# Milestone 10.3 — Entwurf-Workspace Redesign (UX & Modi)

**Datum:** 2026-07-03
**Scope:** Frontend-only. Keine Backend-Änderung, keine Contract-Änderung, keine Migration,
keine neuen Dependencies. `final_backend_contracts_v1_1/` unangetastet.

## 1. Ausgangslage (Probleme aus dem User-Review)

1. Layout zu eng/fragmentiert — zu viele gleichzeitig offene Panels, kleines Textfeld für
   Felder mit bis zu 25'000 Zeichen.
2. KI-Vorschlag zu prominent, obwohl im Live-Modus nicht verbunden (tote Chips + zweiter,
   echter A2-Button unter dem Textfeld = zwei konkurrierende "KI-Vorschlag erstellen").
3. "Betroffene Anforderungen" im Kontextpanel immer leer/zu schwach.
4. "Zum Platzhalter springen" ohne spürbaren Nutzen (Cursor-Sprung statt Markierung,
   kein Umgang mit mehreren Platzhaltern).
5. Belege-Tab kryptisch ("Verknüpfung (Aktiv)" ohne Aussage/Quelle/Fundstelle/Aktion).
6. Kommentare halbfertig (kein Typ, "Erledigt" ohne Erklärung, Freigabe-Sperrgrund
   unvollständig).
7. Versionen-Tab immer leer → wirkt kaputt.
8. Markt-Tab ohne Handlung; Wettbewerbsvergleich passt nicht in 360 px Sidebar.
9. Kein Spellcheck (DE/EN) beim Schreiben.

## 2. Umgesetzte Änderungen

### 2.1 Modi & Layout (`components/editor/draft-workspace-shell.tsx`)
- **Kontextpanel-Default ist jetzt modusabhängig:** Bearbeiten und KI-Assist starten mit
  eingeklapptem Kontextpanel (ruhiger, breiter Editor); Prüfen erzwingt es offen (wie
  bisher). Ein Klick auf Ein-/Ausklappen speichert eine explizite User-Übersteuerung
  (`contextOverride: boolean | null`).
- **"KI-Assist öffnen"**-Kurzbefehl unter dem Editor (nur im Bearbeiten-Modus sichtbar,
  CSS-only) — der von dir gewünschte Weg von Modus 1 zu Modus 2.
- **Ctrl/Cmd+S speichert** (preventDefault; nur wenn Speichern möglich). Der
  Speichern-Button trägt den Tooltip "Speichern (Strg+S)".
- **Rechtschreibprüfung Deutsch / Englisch / Aus** als Toolbar-Gruppe: setzt `spellCheck`
  und `lang` ("de-CH"/"en") auf dem Textarea; Präferenz session-persistent
  (`sessionStorage: rf_editor_spellcheck`, hydratisiert nach Mount).
- Fokus-Modus, Feldnavigation-Collapse und Editor-Höhen (60vh / 52vh / 76vh) unverändert.

### 2.2 Platzhalter-UX (`lib/draft-view.ts` + Shell)
- Neue Helpers `placeholderMatches()` (alle Fundstellen als Ranges) und
  `selectTextareaRange()` (fokussieren + **Bereich selektieren** + scrollen — geteilt
  zwischen Banner und Review-Hinweis-Aktion).
- Banner zeigt jetzt die Anzahl ("1 offene Angabe im Text." / "N offene Angaben im Text.").
- Button-Logik: 1 Treffer → **"Platzhalter markieren"**; mehrere → **"Nächster
  Platzhalter"** (zyklisch, Reset bei Feldwechsel). Der Klick selektiert den Platzhalter
  sichtbar statt nur den Cursor zu setzen.

### 2.3 Eine ehrliche KI-Spalte im Live-Modus (`live-editor.tsx`, Shell-Slot `kiContent`)
- Der echte A2-Vorschlagsfluss (2 Felder: «Lösung & Innovation», «Wertschöpfung») ist
  **komplett in die KI-Vorschlag-Spalte des KI-Assist-Modus umgezogen** (Testids
  `a2-suggestion-control`/`a2-field-unavailable` und alle Texte unverändert).
- Die toten Mock-Chips ("Ziel des Vorschlags", deaktivierter Button, "…noch nicht
  verbunden") sind im Live-Modus **entfernt** → genau ein "KI-Vorschlag erstellen".
  `AI_LIVE_NOTICE` wurde damit verwaist und gelöscht.
- Neuer HITL-Hinweis in der Spalte: "Vorschläge werden nie automatisch übernommen — Sie
  prüfen, übernehmen oder verwerfen selbst."
- Unter dem Textfeld verbleiben nur noch Speicher-/Recheck-Hinweise (Vitest-relevant).
- Mock-Modus behält die simulierten Ziel-Chips (Shell-Fallback, wenn `kiContent` fehlt).

### 2.4 Belege-Tab: echte Beleg-Karten (`live-editor.tsx`, `lib/evidence.ts`)
Pro verknüpftem Beleg jetzt: **Aussage** (`claim_text` bzw. Anchor-Zitat), **Quelle**
(Name + Typ-Chip `EVIDENCE_SOURCE_TYPE_LABELS`, neu zentral in `lib/evidence.ts`),
**Fundstelle** (`formatFundstelle`), **Status** ("Fundstelle bestätigt" etc. +
"Veraltet"-Chip bei stale + Hinweis "fachliche Prüfung offen", solange nicht
menschlich geprüft), **Aktionen** [Quelle öffnen → externer Link bei URL-Quellen, sonst
`/quellen?tab=evidenz&anchor=…`-Deep-Link] und [Verknüpfung entfernen] (als Text-Aktion).
Darunter der Abschnitt **"Weitere Belege verknüpfen"** mit dem bestehenden
Verknüpfen-Workflow.

### 2.5 Anforderungen-Tab: Feld-Join (`live-editor.tsx`, `assistant-panel.tsx`-Slot)
- Client-Join: offene Review-Findings tragen `field_id` **und** `requirement_id` →
  Lookup in `listRequirements()`. Pro Zeile: Titel, Status-Badge (Erfüllt/Teilweise/…),
  "Beleg vorhanden"/"Noch kein Beleg verknüpft", "Menschliche Prüfung nötig",
  "Prüfung veraltet" bei stale, Link "In Anforderungen öffnen".
- Empty State mit Erklärung + Aktion: "Keine Anforderungen mit diesem Feld verknüpft.
  Dieses Feld kann trotzdem für die Fördervoraussetzungen relevant sein." +
  [Anforderungen prüfen].
- Bekannte Grenze (ehrlich): Der Contract kennt keine direkte Feld↔Anforderungs-Zuordnung;
  sichtbar sind Anforderungen mit aktuell offenem Finding auf dem Feld.

### 2.6 Versionen-Tab: Aktuelle Version statt Leere (`lib/draft-viewmodel.ts`)
- `liveFieldToViewModel` mappt `current_version` auf eine Karte: Herkunft
  (`CREATED_BY_LABELS`: agent → "KI-Vorschlag (übernommen)", user → "Manuell bearbeitet",
  template → "Strukturvorlage"), "Gespeichert am {de-CH-Zeitstempel}", Zeichenzahl,
  "Aktuell"-Chip. Aktualisiert sich bei jedem Speichern.
- Fussnote: "Versionshistorie ist in dieser Beta noch nicht verfügbar."

### 2.7 Kommentare (`live-editor.tsx`, `lib/review-view.ts`)
- **Kommentar-Typ** Hinweis / Frage / Änderung nötig (deine Entscheidung: Präfix-Lösung):
  Der Typ wird als sichtbares Präfix im Kommentartext gespeichert (`[Frage] …`) und beim
  Rendern als Badge angezeigt (`commentWithType`/`parseCommentType`). Keine
  Contract-Änderung — das Präfix ist Teil des Kommentartexts.
- **"Erledigt" mit Inline-Bestätigung:** "Als erledigt markieren? Der Hinweis wird aus der
  Liste entfernt." + Bestätigen/Abbrechen (kein versehentliches Dismiss mehr).
- **Freigabe-Sperrgründe vollständig:** bei `recheck_required` neu "Freigabe erst nach
  erneuter Prüfung möglich." + Link zur Qualitätsprüfung; der bestehende Blocker-Hinweis
  bleibt.
- Kein Status "In Bearbeitung" (Backend kennt nur offen/erledigt) — bewusst weggelassen.

### 2.8 Review-Hinweis → Textstelle (`live-editor.tsx`)
Finding-Karten erhalten eine kontextuelle Aktion: Platzhalter-Hinweise → **"Zum
Platzhalter"** (selektiert die Stelle im Editor via geteiltem Helper); Beleg-/Evidenz-
Hinweise → **"Belege öffnen"** (wechselt den Kontext-Tab; `AssistantPanel` dafür optional
controlled: `tab`/`onTabChange`, Reset bei Feldwechsel).

### 2.9 Markt: Status, Aktionen, breites Vergleichs-Sheet
- **Statuszeile** im Markt-Tab via `comparisonToMarketStatus()` (`lib/market-view.ts`):
  kein Vergleich/failed → "Nicht analysiert", stale → "Veraltet", sonst
  Belegt/Teilweise belegt/Quelle fehlt — konsistent mit `MARKET_STATUS_LABELS`.
- **[Marktvergleich öffnen]** → neues, breites Sheet
  `components/editor/market-comparison-sheet.tsx` (rechts, 760 px,
  `data-testid="market-comparison-sheet"`): Tabelle Wettbewerber/Zielgruppe/Stärke/
  Schwäche/Differenzierung/Quelle/Status aus `getLatestComparison`, plus offene
  Marktfragen.
- **[Als Argument übernehmen]** pro Zeile (nur belegte, nicht abgelehnte Einträge mit
  Differenzierungshinweis; sonst deaktiviert mit Begründung): fügt einen deutschen Satz
  (`marketArgumentSentence`) **in den lokalen, ungespeicherten Editor-Buffer** ein
  (HITL — Hinweis "Argument eingefügt — noch nicht gespeichert."). Statuswechsel
  (Übernehmen/Ablehnen) bleiben bewusst unter Quellen.
- **Gating:** `capabilities.features.market_comparison` && marktrelevantes Feld
  (VC/SOL). Capability aus → bisheriger ehrlicher Checklisten-Zustand; nicht
  marktrelevant → bisheriger Hinweis. `LiveMarketComparison` ist jetzt props-basiert
  (Fetch liegt im LiveEditor), mit Statuszeile + Aktionen.
- Label-Maps (Kategorie/Relation/Konfidenz/Status) zentral in `lib/market-comparison.ts`
  (vorher lokal in `market-comparison-section.tsx`); dabei zwei nicht existierende
  Design-Tokens korrigiert (`status-complete` → `status-fulfilled`,
  `text-status-incomplete` → `text-destructive`).

## 3. Geänderte Dateien

- `lib/draft-view.ts` — placeholderMatches/selectTextareaRange/placeholderCountText;
  PLACEHOLDER_PROBLEM + firstPlaceholderIndex entfernt (verwaist).
- `lib/draft-viewmodel.ts` — CREATED_BY_LABELS; versions[] aus current_version.
- `lib/evidence.ts` — EVIDENCE_SOURCE_TYPE_LABELS (zentralisiert).
- `lib/review-view.ts` — COMMENT_TYPES/commentWithType/parseCommentType.
- `lib/market-view.ts` — comparisonToMarketStatus/marketArgumentSentence.
- `lib/market-comparison.ts` — ITEM_CATEGORY/RELATION/CONFIDENCE/ITEM_STATUS-Labels + Styles.
- `lib/draft-ai-actions.ts` — AI_LIVE_NOTICE entfernt (verwaist).
- `components/editor/draft-workspace-shell.tsx` — Kontext-Default, Ctrl+S, Spellcheck,
  Platzhalter-Zyklus, `textareaRef?`/`kiContent?`-Props, Mock-KI-Props optional,
  "KI-Assist öffnen".
- `components/editor/live-editor.tsx` — A2-Umzug, Beleg-Karten, Anforderungen-Join,
  Kommentar-Typen + Bestätigung + Sperrgründe, Finding-Aktionen, Markt-Daten + Insert.
- `components/editor/assistant-panel.tsx` — controlled tab, `anforderungenContent`,
  `versionsFootnote`, erweitertes Markt-Prop.
- `components/editor/live-market-comparison.tsx` — props-basiert + Status + Aktionen.
- `components/editor/market-competition-panel.tsx` — Capability-Gate + Durchreichen.
- `components/editor/market-comparison-sheet.tsx` — **neu** (breites Vergleichs-Sheet).
- `components/quellen/live-evidence.tsx`, `components/quellen/market-comparison-section.tsx`
  — Import der zentralen Label-Maps (identische Strings).
- Tests: `test/live-editor.test.tsx`, `test/live-editor-a2.test.tsx` (Requirements-Handler,
  KI-Assist-Modusklick), `e2e/demo-dataset.spec.ts` (Prüfen-Klick vor Belege-Tab),
  **neu** `test/draft-placeholder.test.tsx`, **neu** `test/live-editor-context.test.tsx`.

## 4. Verifikation

| Prüfung | Ergebnis |
|---|---|
| `tsc --noEmit` | pass |
| `eslint .` | pass |
| Vitest (voll) | **150/150 pass** (37 Dateien; +8 neue Tests) |
| `next build` | pass |
| `scripts/verify_all.ps1` (Backend-Pytest, Migration, Vitest, Build, **Playwright komplett**, API-Smoke, EvaluationRunSummary; Wegwerf-DB `var/verify_e2e.db`) | ALL GREEN — siehe Abschnitt 4.1 |

### 4.1 verify_all-Zusammenfassung (Lauf 2026-07-03, 18:46)

```
backend tests            : pass
migration                : pass
frontend tests (vitest)  : pass
build/typecheck/lint     : pass
Playwright               : pass   (28 passed, 1.4m)
API smoke                : pass   (18/18)
export smoke             : pass   (test_m10_smoke.py::test_export_all_types)
no-raw-log               : pass   (test_m10_smoke.py::test_no_raw_log)
evaluation summary       : backend/var/evaluation/EvaluationRunSummary.json
ALL GREEN
```

Hinweis: Im ersten Lauf schlug **nur** `demo-dataset.spec.ts` fehl — ein
Strict-Mode-Flake: der lose Text-Selektor `getByText(/Produktionsanlagen (Demo)/)`
traf neben der Projektkarten-Überschrift auch einen unsichtbar gemounteten Eintrag
der Base-UI-Projektauswahl. Fix: Klicks auf `getByRole("heading", …)` gehärtet
(kein App-Fehler; Lauf 2 vollständig grün).

### 4.2 Neue/aktualisierte Testabdeckung
- Platzhalter: Ranges aller Varianten; Banner-Anzahl; zyklische **Selektion** über zwei
  Platzhalter; "Platzhalter markieren" bei genau einem Treffer.
- Anforderungen-Join: Zeile mit Titel/Teilweise/Beleg vorhanden/Öffnen; Empty State +
  "Anforderungen prüfen".
- Versionen: "Manuell bearbeitet" + "Aktuell" + "Gespeichert am …" + Beta-Fussnote.
- Kommentar-Typ: `[Frage]`-Präfix wird als Badge gerendert (Text ohne Präfix);
  gesendeter POST-Body enthält `[Änderung nötig] …`.
- Markt: Capability aus → kein "Marktvergleich öffnen"; Capability an → Sheet öffnet,
  "Als Argument übernehmen" fügt Satz in den Buffer ein → Editor dirty, nichts gespeichert.
- a2-Tests klicken jetzt realistisch zuerst den Modus "KI-Assist".
- e2e demo-dataset: wechselt vor dem Belege-Tab in den Prüfen-Modus (Panel-Default).

## 5. Manuelle Testschritte (Eval-Umgebung)

1. `/editor` öffnen → Bearbeiten-Modus: Kontextpanel eingeklappt, Editor breit;
   "KI-Assist öffnen" unter dem Textfeld.
2. Rechtschreibung auf Englisch stellen, englisches Wort tippen → Browser-Unterstreichung;
   Reload → Einstellung bleibt (Session).
3. Text mit 2 Platzhaltern: Banner "2 offene Angaben", zweimal "Nächster Platzhalter" →
   beide werden nacheinander **markiert**.
4. Strg+S bei geändertem Text → speichert + Recheck-Hinweis.
5. KI-Assist: bei «Wertschöpfung»/«Lösung & Innovation» KI-Vorschlag erstellen →
   Seite-an-Seite-Dialog; bei anderen Feldern ehrliche Nichtverfügbarkeits-Erklärung;
   keine toten Chips mehr.
6. Prüfen-Modus: Kontextpanel offen. Belege-Tab: Karten mit Aussage/Quelle/Fundstelle/
   Status; "Quelle öffnen" springt zur Evidenz; "Verknüpfung entfernen" wirkt.
7. Anforderungen-Tab: bei Feld mit Finding+requirement_id erscheint die Anforderung mit
   Status/Beleg; sonst Empty State mit [Anforderungen prüfen].
8. Kommentare: Typ "Frage" wählen, Kommentar senden → erscheint mit Frage-Badge;
   "Erledigt" verlangt Bestätigung; bei ungeprüften Änderungen erscheint
   "Freigabe erst nach erneuter Prüfung möglich." mit Review-Link.
9. Versionen-Tab: "Aktuelle Version"-Karte + Beta-Fussnote.
10. Markt-Tab (VC/SOL, Capability an): Statuszeile; "Marktvergleich öffnen" → breites
    Sheet; "Als Argument übernehmen" → Satz im Editor, Status "Änderungen",
    erst Speichern persistiert.

### 4.3 UI-UX-Review (ui-ux-pro-max als Prüfhilfe, CLAUDEX §9)
Checkliste (Hierarchie/Dichte/CTA-Klarheit/Disabled-States) über die geänderten Screens:
- **Behoben:** Deaktivierte Buttons verschlucken ihren `title`-Tooltip
  (`disabled:pointer-events-none` im Button-Basisstil) → das Markt-Sheet zeigt die
  Übernahme-Regel jetzt zusätzlich als sichtbare Fussnote unter der Tabelle.
- Bestanden: eine klare Primäraktion pro Bereich; Statusfarben konsistent; keine
  Emoji-Icons (Lucide); Hover-Feedback ohne Layout-Shift; Fokus-Outlines nicht entfernt.
- **P2 (app-weit, nicht M10.3):** Tailwind-v4-Default lässt Buttons ohne
  `cursor: pointer` (betrifft die ganze App, bestehendes Muster).

## 6. Risiken & bewusste Grenzen (P-Labels)

- **P2 (Backend-Follow-ups, ohne Contract nicht machbar):** echte Versionshistorie;
  Kommentar-Autor/-Zeitstempel beim Lesen + Erledigt-Archiv; Kommentar-Typ/-Status als
  echtes Feld; direkte Feld↔Anforderungs-Zuordnung; "Offene Marktfrage erstellen";
  Multi-Goal-KI-Ziele im Live-Modus (heute nur A2-Redraft auf 2 Feldern).
- **P2:** Text-Highlighting von Fundstellen im Prüfen-Modus (Textarea kann keine
  Inline-Highlights; würde einen Overlay-Editor erfordern).
- **P2:** Scroll-Position beim Platzhalter-Sprung ist zeilenbasiert geschätzt (wie bisher).
- Kontextpanel-Übersteuerung gilt pro Seitenaufruf (kein Persist) — bewusst, damit jeder
  Einstieg mit den ruhigen Defaults beginnt.

## 7. Nicht verändert

Backend, API-Contracts, Exporte (inkl. technical_evidence), Qualitätsprüfung (/review),
Anforderungen-Seite, Quellen-Seite (bis auf Label-Import), Mock-Workspace-Verhalten
(erbt nur Ctrl+S/Spellcheck/Platzhalter/Kontext-Default), M10.1-Garantien
(Stale-Reliability, No-Raw-Log) unangetastet.
