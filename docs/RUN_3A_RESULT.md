# RUN 3A - Ergebnis

Matrix-Korrektur fuer den verbindlichen RUN-3-Plan:

| ID | Verbindlicher Nachweis |
|---|---|
| `UX-RES-01` | Unicode-/Whitespace-Policy inklusive Paste, Bearbeitung in der Mitte und Reload |
| `UX-RES-02` | Vereinfachtes Rechercheformular ohne Pflicht-Ontologie |

Diese Zuordnung ersetzt die beiden spaeter im historischen Abschlussabschnitt
vertauschten UX-Zeilen.

Stand: 21. Juli 2026

Status: abgeschlossen, vor RUN 3B gestoppt
Ausgangscommit: `f2246d914aa827e4d38e9046bfd9f976a01dda3f`
Migrations-Head: `a1c3e5f7b902` auf `f7b9d2c4a681`

RUN 3A wurde als eigenständiger Offline-Slice umgesetzt. Er umfasst nur
Provider-/Capability-Readiness, das vereinfachte Rechercheformular,
Unicode-/Whitespace-Korrekturen sowie die notwendigen additiven Verträge und
die reversible Migration. Query Planner, Query Firewall, Approval,
Firecrawl-Livepfad, Quellenimport, Marktvergleich und LLM-Vorschläge wurden
nicht begonnen.

Es wurden keine echten Provider-Calls und kein externer Netzwerkzugriff
ausgeführt. Providerpfade in Tests verwendeten ausschließlich Testadapter und
Fakes.

## Verbindliche Quellen und Scope

Verwendet wurden der Masterprompt, der RUN-3-Prompt mit Execution Override,
`docs/IMPLEMENTATION_DISCOVERY.md`, `docs/RUN_2A_RESULT.md`,
`docs/RUN_2B_RESULT.md` und die Verträge unter
`final_backend_contracts_v1_1/`.

`IMPLEMENTATION_PLAN.md` und `E2E_ACCEPTANCE_MATRIX.md` fehlen weiterhin im
Repository. Daraus wurden keine Ersatzanforderungen erfunden.

## Preflight und Repository-Hygiene

- `HEAD` entsprach exakt dem vorgeschriebenen Ausgangscommit; der Working Tree
  war zu Beginn sauber.
- Der Scan getrackter Dateinamen fand nur `.env.example` und
  `backend/.env.example`, aber keine lokale Datenbank, kein Log, keinen
  Rohprompt und kein Providerantwort-Artefakt.
- Der Signatur-Scan fand keine produktiven Secrets. Die zwei bekannten
  `sk-SECRET-*`-Treffer sind absichtliche Canary-Testwerte in Security-Tests.
- Lokale `.env`-Dateien und ignorierte Testartefakte blieben ungetrackt.
- `git diff --check` war vor dem Commit fehlerfrei.

Die erste Offline-Baseline traf auf einen Infrastrukturfehler im Test-Runner:
`scripts/verify_all.ps1` verwendete feste, nach einem abgebrochenen Lauf
wiederverwendete Pytest-Basetemp-Verzeichnisse. Unter OneDrive führte der stale
Zustand zu Zugriffsfehlern. Der Runner verwendet nun pro Prozess eindeutige
Basetemp-Pfade aus PID und Lauf-Token. Tests wurden nicht abgeschwächt und
produktive Timeouts nicht erhöht. Der vollständige offizielle Offline-Gate-Lauf
bestand anschließend mit Exitcode 0.

## Abgeleitete Provider- und Capability-Readiness

Readiness wird aus der bestehenden Preflight-Domäne abgeleitet und nicht als
zweite Wahrheit persistiert. Grundlage sind Laufmodus, Settings, Agent-Registry,
Pricing-Version, Route und der aktuelle `ProviderPreflightResult`.

| Status | Ableitung |
|---|---|
| `disabled` | Feature oder Route ist deaktiviert |
| `fake` | Der konfigurierte Ausführungspfad ist Fake/Test |
| `not_configured` | Für Live fehlen notwendige Konfigurationsteile |
| `configured_unverified` | Kein frischer, zur aktuellen Route passender Preflight |
| `ready` | Live konfiguriert und durch passenden frischen Preflight bestätigt |
| `degraded` | Retrybarer Rate-Limit-, Timeout- oder temporärer Providerfehler |
| `error` | Nicht retrybarer Auth-, Schema- oder Live-/Fake-Konflikt |

`ProviderPreflightResult` speichert additiv Reason-Code, Retrybarkeit, einen
sicheren Konfigurations-Fingerprint sowie Registry- und Pricing-Version. Der
Fingerprint enthält keine Secrets. `GET /capabilities` liefert additiv
featurebezogene Readiness für Webrecherche, Marktvergleich und Feldvorschläge.
`/admin/live-system-status` liefert die abgeleiteten Route- und
Firecrawl-Zustände. Bestehende Response-Felder bleiben kompatibel.

## Vereinfachter Recherchebrief

`ResearchBrief` enthält additiv `research_goal` und optionale `search_tags`.
Die bisherigen Felder bleiben für bestehende Clients erhalten. Die normale UI
zeigt nur Ziel, Region, vier Recherchebereiche und optionale Suchbegriffe in
einer sekundären Einstellung. Eine Pflicht-Ontologie und die gleichzeitige
doppelte Darstellung derselben Module als Checkboxen und Navigationstabs wurden
entfernt.

Bestehende Briefs erhalten einen deterministischen Backfill aus
Anwendungsdomäne und Technologieklasse; Zielsegmente und Kompetenzbedarfe werden
dedupliziert als Tags übernommen. Bis RUN 3B projiziert der bestehende Service
neue Ziele intern kompatibel auf die vom bisherigen Planner gelesenen
Legacy-Felder. Die eigentliche Query-Erzeugung wurde nicht geändert.

## Unicode- und Whitespace-Policy

Frontend und Backend normalisieren nach derselben Regel:

1. Unicode NFC;
2. nur führende und nachfolgende Whitespaces entfernen;
3. interne Leerzeichen, Satzzeichen und Groß-/Kleinschreibung erhalten;
4. Validierung und Tag-Commit erst beim Speichern;
5. Zeichenlängen nach Unicode-Codepoints statt UTF-16-Code-Units.

Es gibt keine `keydown`-Blockade und keine Regex-Sperre während der Texteingabe.
Paste, Backspace und Bearbeitung in der Mitte bleiben möglich. Tests decken den
vollständigen Text
`KI-gestützte Datenanalyse für Schweizer KMU – Zürich/DACH (B2B)`, Umlaute,
`ß`, Bindestrich, Gedankenstrich, Slash, Klammern, Doppelpunkt, kombinierende
Unicode-Zeichen und XSS-sichere Darstellung ab.

## Migration und Verträge

Die reversible Revision
`a1c3e5f7b902_run_3a_readiness_research_brief.py` erweitert ausschließlich:

- `provider_preflight_results` um die notwendigen Ableitungsmetadaten;
- `research_briefs` um `research_goal` und `search_tags`;
- den deterministischen Legacy-Backfill.

Fresh-Migration, Upgrade, Downgrade, erneutes Upgrade und Backfill sind durch
Regressionstests abgedeckt. Pydantic-Verträge, Laufzeit-OpenAPI, der statische
Capabilities-Vertrag, BFF-/TypeScript-Typen und UI wurden additiv aktualisiert.

## Geänderte Bereiche

- Backend: Preflight-Ableitung, Capability-/Admin-Endpunkte,
  Research-Brief-Vertrag und -Service, zentrale Textnormalisierung und Modelle.
- Datenbank: eine kleine reversible RUN-3A-Migration.
- Frontend: vereinfachtes Rechercheformular, Unicode-Helfer,
  Readiness-Anzeige und additive Clienttypen.
- Verträge: additive Capability-/Readiness-Schemas.
- Tests: Backend-, Migration-, Frontend- und Golden-Path-Regressionen.
- Testinfrastruktur: kollisionsfreie Pytest-Basetemp-Pfade im offiziellen
  Verifikationsskript.

## Test- und Abnahmeergebnisse

| Gate | Ergebnis | Details |
|---|---|---|
| Gezielte Backend-/Migrationstests | bestanden | 43 Tests |
| Gezielte Frontendtests | bestanden | 13 Tests |
| Vollständiges Pytest ohne separaten DOCX-Smoke | bestanden | 100 %, 4 erwartete Skips, ca. 261 s |
| DOCX-Render-Smoke | bestanden | 1 Test, ca. 17,1 s |
| Vollständiges Vitest | bestanden | Exit 0, ca. 42,6 s |
| ESLint | bestanden | Exit 0, ca. 10,5 s |
| TypeScript | bestanden | Exit 0, ca. 6,2 s |
| Produktions-Build | bestanden | Exit 0, ca. 30,8 s |
| Vertragsvalidator | bestanden | 9 Dokumente, 13 Profile, 19 Tools, 29 Controls, 56 Schemas, 76 Requirements, 165 Portalfelder, 81 API-Operationen |
| Migration Fresh/Up-Down-Up | bestanden | Head `a1c3e5f7b902` |
| Playwright mit einem Worker | bestanden | Teil des offiziellen Gesamt-Gates |
| `scripts/verify_all.ps1` | bestanden | Exit 0, ca. 661,3 s; deterministisches Gate grün |
| Finaler Diff-/Secret-/Datenleckscan | bestanden | keine produktiven Secrets oder neu getrackten lokalen Daten |

Der Gesamt-Gate-Lauf umfasst zusätzlich Migration, Golden Path im zweiten Lauf,
funktionalen Import, Review-Truth, API-Smoke, Export-/No-Raw-Log-Prüfungen,
Testdatenmarker und Legacy-Status-Guard. Das Skript liefert Exitcode 0 nur, wenn
alle verpflichtenden Offline-Kategorien ohne `FAIL` abgeschlossen sind.

Zuordnung der RUN-3A-Abnahme:

| ID/Bereich | Nachweis |
|---|---|
| `UX-RES-01` | Vereinfachtes Ziel-/Region-/Modul-/Tag-Formular und UI-Regressionen |
| `UX-RES-02` | Gemeinsame Unicode-/Whitespace-Policy, Codepoint-Zählung und Eingabetests |
| Readiness | Ableitungs-, Ablauf-, Fingerprint-, Pricing- und Statustests |
| Fake-Konflikt | Eindeutige Fake-/Live-Zustände und Capability-Regressionen |
| Preflight | Passender, abgelaufener, retrybarer und nicht retrybarer Preflight |
| No Network | Ausschließlich Testadapter; keine externen Calls im Slice |

## Nicht ausgeführte Live-Kategorien

| Kategorie | Zustand |
|---|---|
| Live-Web-Smoke | `not_run` |
| Live-LLM-Smoke | `not_run` |
| Supervised Live E2E | `not_run` |
| Echter Provider-Preflight | `not_run` |
| Fake-Fallback in einem Live-Lauf | nicht beobachtet; es gab keinen Live-Lauf |

Diese Zustände sind keine bestandene Live-Abnahme. RUN 3A behauptet nicht, dass
Live-Webrecherche oder Live-KI funktionieren.

## Risiken und bewusste Restpunkte

- Der public-safe Query Planner sowie Firewall und Approval gehören erst zu
  RUN 3B.
- Die interne Legacy-Projektion hält den bisherigen Offline-Planner kompatibel.
  Sie ist kein zweiter Recherchepfad und wird in RUN 3B durch die geplante
  zielbasierte Query-Erzeugung abgelöst.
- Readiness bestätigt nur einen frischen passenden Preflight. Da RUN 3A keine
  realen Provider-Calls erlaubt, wurde keine Live-Bereitschaft empirisch
  bestätigt.
- Live-Provider, Marktvergleich, Quellenimport, LLM-Ausgabe, KI-Diff-Editor und
  Qualitätsübersicht blieben außerhalb dieses Slices.

## Diffstat

Kumulativer Diffstat gegen
`f2246d914aa827e4d38e9046bfd9f976a01dda3f`:
26 Dateien geändert, 1.083 Einfügungen, 187 Löschungen.

RUN 3A endet mit diesem Ergebnisdokument und einem eigenen Commit. RUN 3B wurde
nicht begonnen und erfordert eine neue ausdrückliche Bestätigung.
