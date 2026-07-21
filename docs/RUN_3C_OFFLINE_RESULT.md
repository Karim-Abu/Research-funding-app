# RUN 3C Phase 1 – Offline-Ergebnis

Stand: 21. Juli 2026

Status: Offline-Implementierung und deterministische Sicherheitsgates
abgeschlossen. Echte LLM-Qualität ist nicht geprüft.

## 1. Ausgangspunkt und Haltepunkte

- RUN-3B-Ausgangscommit: `8e3cf210445b4b255f0df7924664812eb37f6e5e`.
- RUN-3B-Alembic-Head: `b2d4f6a8c013`.
- Neuer Alembic-Head: `c3e5a7b9d024`.
- Die vollständige Offline-Baseline vor Produktänderungen war grün
  (`scripts/verify_all.ps1`, 607,3 Sekunden).
- Der getrackte Smoke-Orchestrator wurde zuerst offline getestet und committed.
- Der ausdrücklich freigegebene Live-Web-Smoke bestand vor RUN 3C Phase 1.
- In Phase 1 wurden keine echten LLM-Aufrufe ausgeführt.
- RUN 4 wurde nicht begonnen.

`IMPLEMENTATION_PLAN.md` und `E2E_ACCEPTANCE_MATRIX.md` waren weiterhin nicht
im Repository vorhanden. Es wurden keine Ersatzanforderungen erfunden; die
Matrix unten ordnet die vom RUN-3C-Plan verlangten IDs den tatsächlich
ausgeführten Regressionen zu.

## 2. Live-Web-Gate

Der Smoke verwendete ausschließlich den bestehenden Firecrawl-Adapter und den
produktiven Brief-/Planner-/Firewall-/Approval-/Executor-/Importpfad mit einer
temporären Datenbank außerhalb des Repositorys. Es gab keinen Fake-Fallback.

| Messwert | Ergebnis |
|---|---|
| Status | `passed` |
| Provider | `firecrawl` |
| Execution Mode | `live` |
| Calls | 3 |
| Dauer | 7.583 ms |
| Öffentliche Domain | `www.bfe.admin.ch` |
| Firewall | `allow`, Risiko `low` |
| Approval | `used` |
| Kandidat vor Import | nachgewiesen |
| Expliziter Import | nachgewiesen |
| SourceVersion/Provenienz | vorhanden |
| Search-Snippet als Evidence | nein |
| Fake-Fallback | nein |

Der vollständige redigierte Metadatenbericht steht in
`docs/LIVE_WEB_SMOKE_REPORT.md`. Die importierte SourceVersion war nach dem
Import korrekt `unreviewed`; sie wird daher vom RUN-3C-Context-Builder erst
nach einer separaten menschlichen Content Review auswählbar. Der Smoke selbst
hatte Import und Provenienz, nicht die fachliche Reviewentscheidung, zum Ziel.

## 3. Umgesetzter Offline-Umfang

### Kontext und Verträge

- Der bestehende `field_drafting_context` ist zum zentralen
  `SuggestionContextBuilder` erweitert.
- `SuggestionContextManifest@v1` persistiert nur IDs, Versionen und Hashes.
- Requirements, Rules und Feldinstruktionen werden aus vorhandenen Portal- und
  YAML-Registry-Metadaten abgeleitet.
- Primary-Application-Evidence ist an die eingefrorene Antragversion gebunden.
- Supporting-/External-Anker müssen explizit ausgewählt, aktuell, geprüft und
  sicher sein; Snippets, Generated Outputs und Reviewtexte werden abgelehnt.
- Es gelangen höchstens fünf source-backed Market-Findings in den Kontext.
- Das Budget kürzt deterministisch nur an Satzgrenzen; nicht vollständig
  passende Anchors werden vollständig ausgelassen und im Manifest ausgewiesen.
- Pydantic, Runtime-OpenAPI, statische OpenAPI-/Schema-Verträge, BFF und
  TypeScript wurden additiv erweitert.

### Grounding und Missing Inputs

- `FieldSuggestionOutput@v1` validiert die strukturierte Ausgabe.
- Der Server extrahiert konkrete Claims unabhängig von der Modell-Claim-Map.
- Unbelegte kritische Zahlen, Organisationen, Produkte, Markt-, Technologie-
  und Rechtsbehauptungen führen nach höchstens einem Repair über dieselbe Route
  zu `failed_grounding_validation`; es wird dann keine Suggestion gespeichert.
- Sprache und Unicode-Zeichenlimit werden serverseitig geprüft.
- Missing Inputs müssen an Manifest-Requirements gebunden sein und werden über
  einen stabilen Fingerprint als OpenIssues dedupliziert, aufgelöst, wieder
  geöffnet oder stale gesetzt.

### Versionierung, Idempotenz und UI

- Generate ist für migrierte Clients strikt idempotent; Legacy-Clients dürfen
  den Header vorläufig weglassen.
- Scoped Accept verlangt den Idempotency-Key und prüft Basisversion und
  Manifest erneut.
- Konkurrierende Replays erzeugen transaktional genau eine DraftVersion.
- Zentrale Read-/Accept-Staleness deckt Draft, Snapshot, Primary Application,
  SourceVersion, Anchor, MarketComparison, Registry und Feldinstruktion ab.
- Historische Suggestions und DraftVersions bleiben erhalten; die Migration
  bewahrt den ursprünglichen Suggestion-Status für einen verlustfreien
  Downgrade.
- Die UI zeigt Modus, optionale freigegebene Belege, Zeichen, Missing Inputs,
  Registry-Punkte, Warnungen und Staleness sowie Original und Vorschlag.
- Die bestehende Satz-Diff-/Teilübernahmelogik bleibt für RUN 4 erhalten.
  Manifestgebundene Suggestions erlauben nur die Vollübernahme.

## 4. Migration und Rollback

Revision `c3e5a7b9d024` auf `b2d4f6a8c013`:

- erstellt `suggestion_context_manifests`;
- ergänzt DraftSuggestion-Provenienz, strukturiertes Ergebnis, Qualitäts- und
  Stale-Metadaten;
- ergänzt OpenIssue-Feld-/Requirement-/Lifecycle-Metadaten;
- markiert historische Suggestions ohne Manifest als
  `expired/historical_context_unavailable` und bewahrt ihren Vorstatus;
- besitzt einen getesteten Downgrade zurück auf `b2d4f6a8c013`.

Fresh Upgrade sowie Up-Down-Up einschließlich historischem Backfill und
Statuswiederherstellung waren erfolgreich.

## 5. Akzeptanzmatrix

| ID | Nachweis | Status |
|---|---|---|
| AI-01 | feldbezogener strukturierter Vorschlagspfad und Manifest | offline `passed` |
| AI-02 | ausgewählte, scoped Anchors und Grounding | offline `passed` |
| AI-04 | expliziter Accept erzeugt neue DraftVersion | offline `passed` |
| AI-Q01–AI-Q10 | versioniertes synthetisches Evaluationsset | offline `passed` |
| SEC-02 | fremde/stale/generierte/quarantänisierte Inhalte fail-closed | offline `passed` |
| LIVE-01 | echter Firecrawl-Web-Smoke, expliziter Import, kein Fake | `passed` |
| LIVE-02 | echter LLM-Smoke | `not_run` |
| LIVE-03 | beaufsichtigter Live-Happy-Path | `not_run` |
| Menschliche Qualitätsbewertung | Nutzwert/Klarheit/Vollständigkeit | `not_run` |

## 6. Gemessene Tests und finales Gesamtgate

- Fokussierter A2-/RUN-3C-Pytestblock: 161 bestanden.
- Grounding plus synthetischer Datensatz: 21 bestanden.
- Kontext, OpenIssues und Migrations-Roundtrip: 11 bestanden.
- RUN-3C-API einschließlich parallelem Accept und Runtime-OpenAPI: 3 bestanden.
- Frontend Redraft/Dialog/Editor: 30 bestanden.
- BFF/Redraft/Dialog: 23 bestanden.
- ESLint: bestanden.
- TypeScript `--noEmit`: bestanden.
- Next.js-Produktionsbuild: bestanden (27 Sekunden).
- Statischer Vertragsvalidator: bestanden; 9 Dokumente, 58 Schemas,
  76 Requirements, 165 Portal-Felder und 83 API-Operationen.
- Vollständiges `scripts/verify_all.ps1`: Exit-Code 0, 648,8 Sekunden.
  Bestanden sind Testdatenmarker, Legacy-Guard, Fresh-Migration, gesamtes
  Pytest, DOCX-Render-Smoke, gesamtes Vitest, ESLint, TypeScript, Build,
  vollständiges Playwright mit einem Worker, zweiter Golden Path,
  funktionaler Importpfad, Review-Truth-Pfad und API-Smoke.

Die Tests meldeten bekannte nicht-blockierende Warnungen aus vorhandenen
Testfixtures (unter anderem MSW-Handler- und React-`act`-Hinweise). Kein
Pflichtgate war rot.

## 7. Commit-Serie bis zum Ergebnisdokument

- `b9fed4e` – getracktes, offline getestetes Live-Web-Smoke-Harness.
- `a64b872` – redigierter bestandener Live-Web-Smoke-Bericht.
- `a5e1ff2` – hermetische Readiness-Isolation des Harness.
- `83c9d8e` – strikt metadatenbegrenztes Report-Rendering.
- `8b6f3a2` – Manifest, Migration und additive Verträge.
- `9a696dc` – Context Builder, Grounding, Staleness und OpenIssues.
- `a4b967c` – APIs, Idempotenz, Annahme und minimale UI.
- `67f1166` – versioniertes synthetisches Evaluationsset.
- `2ae4c34` – Runtime-OpenAPI- und BFF-Vertragsnachweise.

## 8. Hygiene, Diffstat und Grenzen

Der finale Scan ergab keine getrackte Datenbank, kein Log, kein
`private_inputs`-/`var`-Artefakt, keine `.env` und keine rohe Providerantwort.
Die drei Signaturtreffer wurden einzeln geprüft: zwei sind ausdrücklich
synthetische `sk-SECRET-*`-Canaries in Security-Tests; der dritte ist die
Zeichenfolge `fc-` innerhalb einer zulässigen redigierten Research-Task-UUID im
Live-Web-Smoke-Bericht. Sechs lokale DB-/Logdateien sind vorhanden, aber
ignoriert und ungetrackt; sie stammen zeitlich nicht aus dem Smoke-Harness.
Temporäre `innolink-live-web-*`-Verzeichnisse waren nach dem `finally`-Cleanup
nicht vorhanden.

Kumulativer Produkt-, Vertrags- und Testdiff gegen RUN 3B ohne die drei
Abschlussdokumente: 33 Dateien, 3.591 Einfügungen und 67 Löschungen.
Einschließlich der Abschlussdokumente umfasst RUN 3C 36 Dateien, 4.000
Einfügungen und 67 Löschungen.

Unverändert beziehungsweise nicht begonnen:

- kein vollständiger DeepL-/Write-Diff-Editor;
- keine Änderung der Qualitätsübersicht;
- keine neue Provider-, Research-, Market- oder Evidence-Domäne;
- keine Live-LLM-Calls und keine Behauptung bestandener echter KI-Qualität;
- keine Phase 2 und kein RUN 4.

Die verbleibende fachliche Unsicherheit ist bewusst: deterministische
Grounding-Gates erkennen viele konkrete Claims, ersetzen aber keine
menschliche Prüfung der semantischen Richtigkeit und des Nutzwerts.
