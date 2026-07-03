# Milestone 10.4 — Tiptap Rich-Text-Editor für das Entwurfsfeld

## 1. Ziel & Rahmen
Das grosse Entwurfsfeld (bisher nacktes `<textarea>`) wurde durch einen dokumentartigen
**Tiptap-Rich-Text-Editor mit Toolbar** ersetzt — ohne Bruch bestehender Funktionen und ohne
Backend-/Contract-Änderung.

**Harte Randbedingung:** Backend und Innolink-Portal sind reiner Text. Zeichenlimit,
Platzhalter-Erkennung, Copy-to-Portal, Export und KI-Diff laufen weiterhin ausschliesslich auf
Plaintext.

**Entscheidung des Product Owners (verbindlich umgesetzt):** Plaintext bleibt die einzige
fachliche Wahrheit und wird unverändert gespeichert. Tiptap-Formatierungen werden nur als
temporärer Editor-State in **sessionStorage** gehalten (kein Markdown, kein HTML/JSON im Backend),
damit sie Feldwechsel und Reload **innerhalb derselben Browser-Sitzung** überstehen.

## 2. Architektur
- **`components/editor/rich-text-editor.tsx`** — gekapselte Client-Component
  (`immediatelyRender: false`). Kanonischer Wert nach aussen = **Plaintext** über
  `onChange(plainText)`. Der Editor ist bzgl. Tippen unkontrolliert (Tiptap besitzt seinen
  Content); der Server-Text wird nur bei Feldwechsel / Save / A2-Accept / Konflikt neu gesetzt →
  keine setContent/onUpdate-Schleifen. Exponiert ein imperatives Handle
  (`focus`, `getPlainText`, `insertTextAtCursor`, `selectPlaceholder`, `clearFormatCache`) —
  ersetzt die frühere `textareaRef`-Kopplung.
- **`editor-toolbar.tsx` / `editor-toolbar-button.tsx`** — kompakte, umbrechende Toolbar:
  Undo/Redo · Absatz/Überschrift H1–H3 · Fett · Kursiv · Unterstrichen · Durchgestrichen ·
  Aufzählung · Nummerierte Liste · Ausrichtung L/Z/R/Blocksatz · Hervorheben · Textfarbe
  (Presets) · Link · Formatierung entfernen. Aktive Marks über `useEditorState` + `aria-pressed`;
  Tooltips/`aria-label`.
- **`lib/rich-editor-content.ts`** (rein, unit-getestet) — `normalizePortalPlainText`,
  `serializeTiptapToPortalPlainText`, `buildTiptapContentFromPlainText`, Link-Validierung
  (`isSafeLinkHref`, `normalizeLinkHref`). Plaintext-Regeln: Überschriften → normale Zeile,
  Absätze leerzeilengetrennt, Bullet → `- …`, Ordered → `1. …`, Fett/Farbe/Highlight erzeugen
  **keine** Sonderzeichen, `[[Angabe ergänzen: …]]` bleibt wörtlich.
- **`lib/rich-editor-cache.ts`** — sessionStorage-Cache
  `{ schemaVersion, projectId, fieldId, serverTextHash, plainTextSnapshot, tiptapJson, updatedAt }`
  mit Hash-Guard (djb2 über normalisierten Plaintext) und `isRichCacheAllowed(dataClass)`.
- **`components/editor/draft-workspace-shell.tsx`** — Textarea → RichTextEditor; Prop
  `textareaRef` → `editorRef` (+ `serverText`/`projectId`/`dataClass`); `jumpToPlaceholder` nutzt
  das Handle; Ctrl/⌘+S, spellcheck/lang wandern in den Editor; UI-Hinweis + Link
  „Format-Zwischenspeicher löschen".
- **`components/editor/live-editor.tsx`** — `editorRef`-Handle; `insertMarketArgument` fügt via
  Handle am Cursor ein; „Zum Platzhalter" nutzt `selectPlaceholder`; `serverText` =
  `current_version.text`, `projectId` = aktives Projekt.
- **`app/globals.css`** — eng unter `.rf-rich-editor` gescopeter Block für Überschriften/Listen/
  Links/Zitat/Empty-Placeholder (Tailwind-Preflight flacht sie sonst ab; kein anderer Screen
  betroffen).

## 3. Kernverhalten (nach Spec)
- **Laden:** serverText → `serverTextHash` → Cache-Treffer (project+field+hash) lädt `tiptapJson`,
  sonst Aufbau aus Plaintext; ungültiger Cache wird verworfen. **Cache-Restore synchronisiert den
  Parent-State:** weicht der wiederhergestellte Plaintext vom serverText ab, wird sofort
  `onChange(restoredPlainText)` ausgelöst — Zähler, Platzhalter-Banner, Save-Button und KI-Diff
  lesen denselben Text wie der Editor.
- **Schreiben:** onUpdate → Plaintext serialisieren → **sofort** `onChange` (Zähler/Platzhalter
  live) + **debounced 500 ms** Cache-Write.
- **Speichern:** nur Plaintext an die bestehende Save-Logik; danach Cache unter neuem
  `serverTextHash` re-keyed (Formatierung bleibt erhalten). Backend/API unverändert.
- **Out-of-band (A2-Accept / Konflikt-Reload):** Server-Text ersetzt → Editor baut aus Plaintext
  neu; reine Persistenz (gleicher Text) behält die Formatierung.
- **Platzhalter (robust):** Erkennung/Zähler/Banner laufen **immer** auf dem Plaintext.
  Zusätzlich markiert eine ProseMirror-Decoration `[[…]]`/TODO/tbd innerhalb einzelner Textnodes,
  `selectPlaceholder` springt dorthin; über Formatierung gesplittete Platzhalter werden
  ausgelassen (kein Crash, sauberer Fokus-Fallback).
- **Link-Härtung:** `openOnClick:false`, `autolink:false`, nur `http/https/mailto`,
  `rel="noopener noreferrer nofollow"`, `validate` verwirft `javascript:`/`data:`; der Link-Dialog
  normalisiert/prüft die URL und lehnt ungültige Schemata mit Meldung ab.

## 4. Datenschutz / Governance (CLAUDEX §7)
Der Rich-Cache enthält Antragstext und wird wie der Draft behandelt: nur sessionStorage (weg beim
Tab-/Browser-Schliessen), nie geloggt, gelöscht bei **Logout** (`app-providers.tsx`) und
**Projektwechsel** (`app-shell.tsx`) sowie über „Format-Zwischenspeicher löschen".
`isRichCacheAllowed` deaktiviert den Cache für restricted/NDA/gesperrt.

## 5. Abhängigkeiten
Hinzugefügt (offizielle Tiptap v3.27, keine Pro/Cloud): `@tiptap/react`, `@tiptap/pm`,
`@tiptap/starter-kit` (bündelt u. a. Bold/Italic/Strike/Underline/Link/Listen/Heading/UndoRedo),
`@tiptap/extension-placeholder`, `@tiptap/extension-highlight`, `@tiptap/extension-text-style`,
`@tiptap/extension-color`, `@tiptap/extension-text-align`. (Separat installierte
`extension-underline`/`extension-link` wieder entfernt — in StarterKit v3 enthalten.)

## 6. Tests
- **Strategie:** ProseMirror rendert in jsdom unzuverlässig → in den vier LiveEditor-Unit-Tests
  ersetzt `vi.mock` den Editor durch einen Textarea-**Stub** (`test/mocks/rich-text-editor.tsx`)
  mit identischem aria-label, onChange (Plaintext) und Handle (native Selektion). Dadurch bleiben
  Wert-/Selektions-Assertions unverändert. Der echte Editor wird per Playwright abgedeckt.
- **Neu:** `test/rich-editor-content.test.ts` (Serialisierung, Listen-Marker, Heading→Plain,
  keine Sonderzeichen, `[[…]]`-Erhalt, Round-Trip, Link-Safety) und
  `test/rich-editor-cache.test.ts` (Hash-Stabilität, `isRichCacheAllowed(D3)=false`, read/write/
  clear, Hash-Mismatch-Invalidierung).
- **E2E:** `template-drafts.spec.ts` — Toolbar-Smoke (Button „Fett" sichtbar), echtes Tippen statt
  `fill()` (ProseMirror-sicher), `toHaveValue` → `toContainText`.

## 7. Verifikation
- `tsc --noEmit`: **pass**
- `eslint .`: **pass**
- `vitest run` (voll): **pass — 163/163** (13 neue)
- `next build`: **pass** (/editor prerendered)
- verify_all.ps1 (Backend-Tests, Migration, Build, Playwright, API-Smoke): _(Lauf-Ergebnis unten)_

### verify_all-Zusammenfassung (Lauf 2026-07-03, 22:31)
```
backend tests            : pass
migration                : pass
frontend tests (vitest)  : pass   (163/163)
build/typecheck/lint     : pass
Playwright               : pass   (28 passed, 1.3m — inkl. template-drafts mit echtem Tiptap)
API smoke                : pass   (18/18)
export smoke             : pass
no-raw-log               : pass
ALL GREEN
```

## 7a. Nachtrag — Fix Feldwechsel-Crash
Beim Feldwechsel trat `TypeError: Cannot read properties of null (reading 'can')` auf. Ursache:
`useEditor(…, [fieldKey])` zerstörte die Editor-Instanz bei jedem Feldwechsel und erzeugte sie
neu; die Toolbar (`useEditorState`) lief dabei kurz gegen den zerstörten Editor.
**Fix:** genau **eine** Editor-Instanz für die Lebensdauer der Komponente (`useEditor(…, [])`);
Feldwechsel tauscht nur den Inhalt via `editor.commands.setContent(…, { emitUpdate:false })`
(Tiptap-empfohlenes Muster) — kein Teardown mehr. Zusätzlich guarded der Toolbar-Selektor gegen
`editor.isDestroyed`. Neuer e2e-Schritt in `template-drafts.spec.ts` (Feldwechsel → Toolbar bleibt,
kein „Cannot read properties of null") sichert die Regression ab; zusätzlich im laufenden Frontend
mit echtem Tiptap gegengeprüft (5 Feldwechsel, keine `pageerror`).

## 8. Grenzen / bewusst (P-Labels)
- **P2:** Formatierung überlebt Tab-/Browser-Schliessung nicht (per Design); Server behält Plaintext.
- **P2:** D3/NDA-Gate ist als Hook vorhanden, greift aber erst mit einer restricted-Datenklasse —
  das Frontend-Enum kennt heute nur public/internal/confidential (D0–D2); im Editor liegt keine
  projektbezogene Datenklasse vor, daher wird der Cache aktuell für die Eval-Daten aktiviert.
- **P2:** Kein Markdown-Export, keine Tabellen/Bilder/Collaboration (v1), keine Zoom-Anzeige.
- Kommentare bleiben bewusst einfache Textareas.
