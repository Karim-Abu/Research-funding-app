# Repair-Milestone R3 — Import-First MVP (Innolink-Antragsimport)

**Scope:** Vollständige Umsetzung von R3 gemäss Prompt-Pack
`claude_code_prompt_pack_innolink_repair_v2.md` (R3.GATE, R3.1–R3.4) und
`docs/repair/roadmap-v2.md`. Ein Prompt = ein Commit. Ziel: ein begonnener
Innolink-Antrag (digitaler PDF-/Text-Export) wird als Quelle hochgeladen,
deterministisch auf die 8 MVP-Felder gemappt und **je Feld explizit von einem
Menschen entschieden** — kein LLM im Mapping, kein OCR, kein Auto-Accept.

## Branch / Commit-Basis

- Branch **`repair-v2`**; Basis-Tag **`repair-r2-done`** auf `2bacd23`,
  **`repair-r3-done`** auf diesem Stand. **Kein Push** (wartet auf Owner-GO).

## Gate-Entscheid E-01 (Voraussetzung, erfüllt)

Das PDF-Gate wurde am 2026-07-07 mit einem **echten Innolink-Portal-Export**
ausgeführt (lokal unter `private_inputs/`, per `.gitignore` ausgeschlossen —
keine Kennungen/Rohtexte im Repo, Details in
`docs/evaluation/pdf-import-gate-report.md`):

| Messung | usable-Quote | Befund |
|---|---|---|
| 1 — Spike unverändert | **1/8 = 12.5 %** | Vokabular-Lücke (echtes Portal-Wording weicht vom synthetischen Fixture ab), kein Strukturversagen |
| 2 — Spike + Portal-Vokabular (deterministisch) | **5/8 = 62.5 %** | 5× correct, 2× uncertain (Felder im Test-PDF leer — korrekt erkannt), 1× missed (Haupttitel ohne Label) |

Strukturbefund: Der echte Export ist **zeilenerhaltend** — die vom Spike als
dominant erwartete Fehlklasse «Zeilenverschmelzung» liegt nicht vor.
**Owner-Entscheid E-01 im Chat (2026-07-07): R3 bauen** (Messung 2 ≥ 60 %).
Vorbehalt: n = 1 Export; Varianz anderer Portal-Versionen unbekannt.

## Commits (ein Prompt = ein Commit)

| Commit | Prompt | Inhalt |
|---|---|---|
| `7344161` | R3.GATE | Spike additiv um reales Portal-Vokabular erweitert (synthetische Regression bleibt 8/8, degradierte Messlatte 0/8); Gate-Report mit Doppelmessung + Entscheid gefüllt |
| `ba4a505` | R3.1 | `backend/app/imports/mapping.py`: Spike sauber portiert; Extraktion via `ingestion.parsers.parse` (fail-closed, keine pypdf-Kopie); 8 Felder mit erzwungener Deckung zu `EXPORT_FIELD_LABELS`; 13 Tests (Spike-Regression, degradiert ⇒ uncertain, fail-closed, TXT) |
| `895d12c` | R3.1-Fix | PDF-Test-Fixtures als `binary` markiert (verhindert CRLF-Korruption bei `core.autocrlf=true`) |
| `6f9ef1d` | R3.2 | Tabelle `import_candidates` (additive Migration `a3f8c2d91e47` mit Downgrade), Endpoints erstellen/auflisten/entscheiden, Übernahme via bestehendem `drafts_repo.apply_update` (Stale/Recheck gratis), Konflikt-Semantik, Audit nur Zählwerte/IDs, Next.js-Proxy-Routen; 12 Tests + Migrations-Roundtrip |
| `a38d242` | R3.3 | Intake mit drei Startoptionen; `/import` + `import-review.tsx` (Upload, Status-Poll fail-closed, Review-Tabelle, Konflikt-Dialog, «Zur Fix Queue»); Flag `innolinkImport`; 8 Component-Tests + E2E Upload→Review→Übernahme→Fix Queue |
| `6b3781d` | R3.4 | No-Raw-Logging-Suite: Marker-PDF durch den kompletten Pfad inkl. Fehlerpfade; Marker in keinem Log/Audit/Control/Operation/Fehlertext; `redaction.py` unverändert (keine Lücke nachgewiesen) |

## Kernverhalten

### Import-Flow (HITL durchgehend)
1. **Upload = bestehender Quellen-Pfad** (`POST /projects/{id}/sources/files`):
   Grössen-/Typ-Guards, Klassifikations-Auflösung (restriktivste gewinnt) und
   Fail-closed-Verarbeitung (Scan/verschlüsselt ⇒ `needs_manual_input`, nie
   stillschweigend «verarbeitet») kommen unverändert von dort.
2. **Mapping** (`POST /projects/{id}/imports`): deterministisch (Label-Anker,
   Noise-Filter, Sektions-Stopper aus dem Gate-Spike), idempotent je
   Quellversion. Leere/strukturell unsichere Felder ⇒ `uncertain` — nie
   Fremdinhalt.
3. **Entscheidung je Kandidat** (`POST /imports/{id}/decision`):
   **Übernehmen** (nur mit abgeschlossener Analyse — Entwürfe sind
   run-gebunden; nutzt `apply_update`: Zeichenlimit, Optimistic Concurrency,
   `recheck_required`, Approval-Invalidierung) · **Als Quelle speichern**
   (Entscheid protokolliert; das Dokument liegt bereits als Quelle vor — kein
   Quell-Duplikat je Feld) · **Ignorieren**.
4. **Nie stilles Überschreiben:** existiert ein bearbeiteter Entwurf
   (`created_by != template`), wird der Kandidat `conflict` und die Übernahme
   verlangt eine explizite Bestätigung (`confirm_overwrite`).
5. **Kein Auto-Accept** — auch nicht bei hoher Konfidenz; `uncertain` ist
   visuell markiert, nie vorausgewählt, und ohne Entscheid bleibt alles
   `pending`.
6. Nach Abschluss führt der Flow zur **Fix Queue («Nächste Aufgaben», R2.5)**
   mit aktualisierter Lückenübersicht.

### Drei Startoptionen (Intake)
«Bestehenden Innolink-Antrag hochladen» → `/import` · «Mit Projektidee
starten» / «Aus Notizen & Quellen starten» → bisheriger Flow. Nur Auswahl +
Redirect; die Intake-Entschlackung bleibt R7.4.

### Feature-Flag
`innolinkImport` (Default AN; `NEXT_PUBLIC_INNOLINK_IMPORT=off` schaltet das
Intake auf Vor-R3-Verhalten zurück; API-Endpoints bleiben verfügbar).

### Provenienz-Entscheid (dokumentiert)
Übernommene Texte erzeugen eine DraftVersion mit `created_by="user"` (der
Mensch hat explizit entschieden); die Import-Provenienz liegt am Kandidaten
(`accepted_draft_version_id`) und im Audit. Das `CreatedBy`-Contract-Literal
wurde bewusst NICHT erweitert (kein Contract-Change ohne Owner).

## Datenschutz-/Governance-Bezug (manueller Security-Sweep)

- **Kein vertrauliches Material im Repo:** das echte Gate-PDF liegt
  ausschliesslich lokal (`private_inputs/`, gitignored); Gate-Report und
  Spike-Nachtrag enthalten keine Kennungen, Titel oder Textauszüge. Alle
  committeten Fixtures sind synthetisch (fiktives Projekt, Testdaten-Policy).
- **No-Raw-Logging belegt (R3.4):** Canary-Marker durchlaufen den kompletten
  Pfad; kein Marker in Logs (caplog DEBUG), Audit-Details, Control-Details,
  Operation-Feldern oder Problem-Fehlertexten. Import-Audit trägt nur
  IDs/Zählwerte (`safe_detail`-Disziplin).
- **Endpoints:** `require_session` (GET) bzw. `require_unsafe_guards` + 
  Idempotency-Key (POST), durchgehend Workspace-Scoping (`get_scoped`).
- **Do-not-touch unberührt:** `security/*`, `ingestion/*` (nur genutzt),
  finding_code-Formate, Scope-Hash, Zweig-Semantik, Node-Reihenfolge,
  Contract-Regelwerte. `redaction.py` unverändert.
- **Klassifikation:** Import-Quellen erben die restriktivste Einstufung über
  den bestehenden Upload-Pfad (`resolve_effective_classification`); kein
  neuer Klassifikationspfad, kein Downgrade.

## Tests

- **Backend neu:** 13 (Mapping R3.1) + 12 (API/Persistenz R3.2) + 3
  (No-Raw-Logging R3.4) = **28 neue Tests**; Migrations-Suite auf neuen Head
  `a3f8c2d91e47` erweitert (Roundtrip: Tabelle weg/da, R2.2-Spalten überleben
  den `-1`-Schritt, Row-Preservation).
- **Frontend neu:** 8 Component-Tests (`test/import-review.test.tsx`) —
  Entscheidungsaktionen, Unsicher-Markierung ohne Vorauswahl, Konflikt-Dialog
  mit `confirm_overwrite`, kein Auto-Accept, Sperre ohne Analyse.
- **E2E neu:** `e2e/import-flow.spec.ts` — Upload → 8 Kandidaten → Analyse
  starten → Übernahme → Fix Queue (im Throwaway-DB-Lauf).
- **Bestehende Tests angepasst (Ursache: neues Startoptions-Label enthält
  «Projektidee» und kollidierte mit `getByLabel(/Projektidee/)`):**
  `test/intake-partners.test.tsx`, `e2e/partner-budget.spec.ts`,
  `e2e/source-ingestion.spec.ts` — Umstellung auf rollenbasierte Queries
  (`getByRole("textbox", …)`), keine Assertion abgeschwächt.

## Verifikation (verify_all.ps1, wörtlich)

Kompletter Lauf am 2026-07-07 (HEAD `6b3781d`, Branch `repair-v2`), Throwaway-DB,
Fake-Provider; **erster Anlauf ALL GREEN**. API-Smoke 18/18; vitest 225/225
(51 Dateien); Playwright inkl. neuem `import-flow.spec.ts`.

```text
================ M10 VERIFICATION SUMMARY ================
backend tests            : pass
migration                : pass
frontend tests (vitest)  : pass
build/typecheck/lint     : pass
Playwright               : pass
API smoke                : pass
export smoke             : pass   (test_m10_smoke.py::test_export_all_types)
no-raw-log               : pass   (test_m10_smoke.py::test_no_raw_log)
testdata markers         : pass   (scripts/check_testdata_markers.py)
legacy status guard      : pass   (scripts/check_legacy_status_paths.py)
evaluation summary       : ...\backend\var\evaluation\EvaluationRunSummary.json
=========================================================
ALL GREEN
```

## Offene Punkte / Follow-ups

- **E-12 (Owner):** anonymisierte Fassung des Gate-PDFs als drittes
  Repo-Fixture erst nach menschlicher Review; bis dahin nur lokale
  Verifikation (im Gate-Report dokumentiert). Kein Test-Skip im Repo.
- **Owner-Review Migration `a3f8c2d91e47`** vor Merge/Push (rein additiv,
  Downgrade vorhanden, Roundtrip getestet).
- **Limitation Haupttitel:** `INTRO.APP.NAME` hat im echten Export kein
  Label ⇒ bleibt manuell (dokumentiert, kein Fix geplant).
- **n = 1:** genau ein echter Export gemessen; weitere Portal-Exporte sollten
  bei Verfügbarkeit lokal nachgemessen werden (Reproduktion im Gate-Report).
- **Marker-Scan-Verzeichnis:** `backend/tests/import_fixtures/` ist noch nicht
  in der Scan-Liste von `scripts/check_testdata_markers.py` (R0.4) —
  relevant erst, wenn der Owner den Marker-Katalog füllt.
- Bekannte Alt-Punkte: P1 flaky `test/draft-placeholder.test.tsx` (unter
  Volllast), P2 OneDrive-Locks auf `.next`; Owner-Entscheide E-02 u. a. offen.
- **Empfohlener nächster Slice: R4.4** (Browser-Storage-Security-P0, keine
  Owner-Abhängigkeiten).

## Einordnung (ohne Überclaims)

Der Import ist eine **Arbeitserleichterung mit menschlicher Kontrolle**: er
ordnet vorhandene Antragstexte deterministisch den Feldern zu und macht jeden
Schritt einzeln entscheidbar. Er prüft keine Inhalte, garantiert keine
Vollständigkeit und trifft keine Aussage zur Förderfähigkeit. Die Gate-Quote
(5/8 usable) stammt aus genau einem echten Export; leere und unsichere Felder
bleiben bewusst offen und werden vom bestehenden Review-/Fix-Queue-Fluss als
Aufgaben ausgewiesen.
