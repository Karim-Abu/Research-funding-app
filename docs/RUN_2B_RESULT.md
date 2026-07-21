# RUN 2B – Ergebnis

Stand: 21. Juli 2026
Status: abgeschlossen
Ausgangscommit: `d04e77776c2505de4e67ac17ca1950a3142b9ebd`
Migrations-Head: `f7b9d2c4a681` auf `e4a7c2f9b6d1`

RUN 2B wurde vollständig umgesetzt und vor RUN 3 beendet. Live-Provider,
Marktvergleichslogik, KI-Diff-Editor und Qualitätsübersicht wurden nicht geändert.

## Verbindliche Quellen und Scope

Gelesen und als Rahmen beziehungsweise Arbeitsauftrag verwendet wurden der
bereitgestellte Masterprompt, der bereitgestellte RUN-2B-Prompt,
`docs/IMPLEMENTATION_DISCOVERY.md`, `docs/RUN_2A_RESULT.md` sowie die Verträge unter
`final_backend_contracts_v1_1/`.

`IMPLEMENTATION_PLAN.md` und `E2E_ACCEPTANCE_MATRIX.md` waren weder im Repository
noch in den bereitgestellten Anhängen vorhanden. Es wurden daraus keine
Ersatzanforderungen erfunden. Die untenstehende Abnahmematrix ordnet ausschließlich
die im RUN-2B-Auftrag vorgegebenen IDs den implementierten Regressionstests zu.

## Commit-Serie

| Commit | Inhalt |
|---|---|
| `5e614fe` | Getrackte lokale Datenbank, Logs und Rohprompt entfernt; lokale Artefakte gezielt ignoriert |
| `eaa9376` | Import-E2E auf fachliche Request- und UI-Signale synchronisiert |
| `d912974` | Zentrale, kalendarische Projektdauer-Ableitung |
| `f8121d5` | Reversible Importrevisionen, Primary-Application-Scope und Rule Evidence |
| `22f64ec` | Stabilitätsregression für die erste primäre Antragsquelle |
| `f4dd25c` | Aktuelle Konfliktrevision in der UI sowie fachlich aktualisierte E2E-Gegenpins |

## Preflight und Import-Flake

Die Commitbasis wurde vor Produktänderungen auf
`d04e77776c2505de4e67ac17ca1950a3142b9ebd` geprüft. Die getrackte `app.db` wurde
vor dem Entfernen nach
`C:\Users\karim\OneDrive - FHNW\Documents\Bachelorthesis\App\.local-backups\run-2b-preflight-20260720\app.db`
gesichert. Getrackte lokale Logs und
`.claude/Prompt/claude_code_prompt_pack_innolink_repair_v2.md` wurden entfernt.
`.env.local`, `backend/.env`, `private_inputs/` und ungetrackte lokale Testdaten
blieben unangetastet. Es gab keinen History-Rewrite.

Der Signatur-Scan über getrackte und gestagte Inhalte ergab keine produktiven
Secrets. Die zwei zuvor auffälligen Signaturen sind ausdrücklich als Testwerte in
Security-Tests verifiziert. `.gitignore` ignoriert nun lokale Datenbanken, Logs,
lokale Claude-Einstellungen und Rohprompts gezielt.

Root Cause des Import-Flakes: Der Test begann seine UI-Erwartung während der
asynchronen Ingestion und der anschließenden synchronen PDF-Neuzuordnung. Unter
wiederholter I/O-Last war der 60-Sekunden-UI-Wait nicht an das abgeschlossene
Mapping gekoppelt. Zusätzlich konnte der CSRF-Bootstrap eine frühe Reload-Race
auslösen.

Die Korrektur registriert das Response-Promise vor dem Upload, wartet fachlich auf
`POST /api/projects/{id}/imports` mit Status 201 und prüft anschließend das
Verschwinden des Fortschrittszustands sowie das sichtbare Import-Review. Es wurden
weder `waitForTimeout` beziehungsweise neue statische Sleeps noch eine reine
Timeout-Erhöhung eingeführt.

Vor den Produktänderungen bestanden der Import-Repeatlauf mit 40/40 Tests und die
vollständige Playwright-Suite mit 48/48 Tests, jeweils mit einem Worker.

## Zentrale Projektdauer

`backend/app/projects/duration.py` ist die einzige fachliche Ableitung für
`duration_months`, `duration_status` und `duration_reason_code`:

- Vollständige Kalendermonate zählen einschließlich beider Randmonate.
- Fehlendes Start- oder Enddatum ergibt `not_derivable` ohne Dauerwert.
- Ein Enddatum vor dem Startdatum wird mit HTTP 422 und
  `project_date_range_invalid` abgelehnt.
- Nicht bündige Monatsgrenzen ergeben `review_required` mit
  `duration_boundary_conflict`; es wird kein gerundeter Wert ausgegeben.
- Ein PDF-Dauerkandidat bleibt mit Raw-Wert und Fundstelle erhalten, ist aber
  `comparison_only`. Er kann nicht separat übernommen werden und erzeugt je nach
  Vergleich Match, `duration_conflict`, `not_derivable` oder Grenzkonflikt.

Die bestehende DB-Spalte `duration_months` bleibt nur aus Kompatibilitätsgründen
erhalten. API, Regelinput, Run-Snapshot und Export lesen oder schreiben sie nicht
mehr als Wahrheit. Ein PATCH auf das Feld wird mit `duration_read_only`
abgelehnt. Änderungen an Start- oder Enddatum laufen über den zentralen
Projektmutationsdienst und invalidieren aktuelle Runs, Budgetprüfungen,
Freigaben und abhängige Exporte als stale beziehungsweise recheck-required;
historische Artefakte bleiben unverändert.

Die Regressionen decken unter anderem 18 Monate, Einzelmonat, Jahreswechsel,
Schaltjahr, fehlende und verkehrte Daten, Teilmonate, PDF-Match/-Konflikt sowie
Parität von API, Regeln, Snapshot und Export ab.

## Reversible Importentscheidungen

Die Migration ergänzt narrative und strukturierte Kandidatenrevisionen sowie
`project_field_revisions`. Bestehende Kandidaten und Projektfeldwerte werden in
Revision 1 überführt. Raw-Extraktion, ältere Draft-Versionen, Runs und Exporte
werden nicht umgeschrieben.

Jede Revision speichert Status, Aktion, versionierten Benutzerwert, Zielversion,
Actor und Zeitpunkt. Partnerziele erhalten einen monotonen Ressourcenstand;
strukturierte Revisionen speichern den vorherigen Zielzustand. Narrative
Übernahmen referenzieren die vorherige und die erzeugte `DraftVersion`. D2-Inhalte
bleiben in den fachlichen Revisionstabellen und erscheinen weder im Audit noch in
Logs.

### Zustandsmaschine

| Ausgang | Aktion | Ergebnis |
|---|---|---|
| `pending` | Erstentscheidung per `POST .../decision` | `accepted`, `ignored`, `saved_as_source` oder fachlicher `conflict` |
| entschieden oder `conflict` | Bearbeiten per `PATCH .../decision` | neue Revision; `accepted_original` oder `accepted_modified` |
| entschieden | `POST .../reset` | neue bewusste Übernahme des unveränderten PDF-Raw-Werts |
| entschieden | identischer Reset/Zielzustand | HTTP 200, gleiche Revision, `idempotent_replay=true` |
| entschieden | `POST .../undo` und Zielrevision unverändert | vorheriger Projektfeld-, Partner- oder Draftstand; Kandidat wieder offen |
| entschieden | `POST .../undo` nach späterer manueller Zieländerung | Nutzerwert bleibt; `conflict` mit `manual_resolution_required` |

Alle Mutationen prüfen `Idempotency-Key`, `project_id`, `source_id` und
`expected_revision_id`. Antworten enthalten `current_revision_id`,
`revision_number`, `acceptance_state`, erlaubte Folgeaktionen und einen
Konfliktgrund. `decision=accepted` bleibt kompatibel. Fehler werden typisiert als
`import_candidate_not_found`, `import_invalid_transition`,
`import_revision_conflict` oder `import_project_source_mismatch`.

Die UI bietet nach einer Entscheidung weiterhin „Bearbeiten“, „PDF-Wert
wiederherstellen“ und „Übernahme zurücknehmen“ an. Nach einem 409-Konflikt lädt
sie die vom Server erzeugte Konfliktrevision neu; die Bestätigung kann deshalb
nicht versehentlich mit einer veralteten erwarteten Revision senden.

AuditEvents enthalten ausschließlich Kandidaten-, Revisions- und Ziel-IDs,
Statuswechsel, Reason-Code, Actor und Zeitpunkt, niemals Raw- oder bearbeiteten
Antragstext.

## Primary Application und Evidence-Scoping

`Project.primary_application_source_id` wurde additiv ergänzt. Der erste
erfolgreich gemappte Innolink-Antrag wird automatisch gesetzt; weitere Imports
ersetzen ihn nicht. Die explizite Auswahl erfolgt über
`PUT /projects/{id}/primary-application` mit Workspace-/Projektprüfung,
Idempotenz und erwarteter bisheriger Zuordnung.

Der Legacy-Backfill setzt genau eine Quelle mit Importkandidaten. Keine Quelle
ergibt `not_configured`, mehrere uneindeutige Quellen ergeben `needs_selection`.
Run-Snapshots verwenden Schema v3 und frieren die primäre Source-ID sowie exakt
eine Source-Version ein. Eine explizite Run-Auswahl ohne diese Version wird
abgelehnt; ohne gültige Konfiguration läuft die Regelanalyse fail-closed ohne
Application Evidence.

`backend/app/evidence/scope_policy.py` wird von deterministischer Discovery und
A1-Requirement-Mapping gemeinsam verwendet:

- Application Evidence stammt ausschließlich aus der eingefrorenen primären
  Antragversion.
- Importierte öffentliche Quellen bleiben External Evidence in den bestehenden
  Markt-/SOTA-/Partnerpfaden.
- Begleitdokumente bleiben Drafting-Kontext mit
  `used_as_requirement_evidence=false`.
- Generated Output, Reviews und KI-Texte werden vor Retrieval mit
  `generated_or_review_content` abgelehnt.
- Cross-Project-, Cross-Run-, Source- und Versionsabweichungen werden fail-closed
  abgelehnt.

Evidence-Links enthalten additiv `run_id`, `source_id`, `source_version_id`,
`fragment_id` und `scope`. Abgelehnte Kandidaten speichern maschinenlesbare
Reason-Codes; ruhige deutsche Texte werden zentral daraus erzeugt. Die typisierten
Validatoren prüfen Zahl samt Einheit/Nenner oder Operator, Datum/Dauer, konkrete
Organisation, Research-/Implementation-Rolle, Scope und Generated Content.
`location_found` bleibt neutral und erzeugt nie automatisch Support.

Rule Evidence ist von Application Evidence getrennt. `source_refs`, URLs und
Registry-Version stammen direkt aus der eingefrorenen YAML-Registry. Mangels
eigenem Zitatfeld wird die unveränderte Regel-`description` als `evidence_quote`
ausgegeben und in der UI als „kuratierter Registry-Auszug“ bezeichnet. Externe
Zitate werden nicht rekonstruiert.

Der allgemeine Drafting-Kontext und das Marktvergleichsdesign wurden nicht
verändert.

## Verträge, API und Migration

Pydantic-Modelle, TypeScript-Clients/Bridge-Routen und
`final_backend_contracts_v1_1/openapi-v1_1.yaml` wurden additiv erweitert. Der
bestehende Importpfad bleibt erhalten; es wurde kein paralleler Importpfad
eingeführt.

Relevante Endpunkte:

- `POST|PATCH /imports/{id}/decision`
- `POST /imports/{id}/reset`
- `POST /imports/{id}/undo`
- `POST|PATCH /structured-imports/{id}/decision`
- `POST /structured-imports/{id}/reset`
- `POST /structured-imports/{id}/undo`
- `PUT /projects/{id}/primary-application`

Alembic-Revision `f7b9d2c4a681` hat Up-/Downgrade und den beschriebenen
deterministischen Backfill. Fresh-DB, Upgrade, Downgrade auf `e4a7c2f9b6d1` und
erneutes Upgrade wurden getestet. Der Downgrade entfernt nur die additiven
RUN-2B-Spalten/-Tabellen/-Indizes; historische Vor-RUN-2B-Daten bleiben erhalten.

## Abnahmematrix

| ID | Fachliche Abnahme | Regressionen |
|---|---|---|
| `IMP-02` | Edit erzeugt eine neue Revision | `backend/tests/test_import_revisions.py`, `test/import-review.test.tsx` |
| `IMP-03` | PDF-Reset, idempotenter Replay und erneute Übernahme | `backend/tests/test_import_revisions.py`, `e2e/import-functional.spec.ts` |
| `IMP-04` | Undo, Restore-Konflikt, historische Drafts und Staleness | `backend/tests/test_import_revisions.py` |
| `SRC-01` | Genau ein stabiler primärer Antrag; explizite Auswahl versioniert | `backend/tests/test_run2b_evidence_scope.py`, `e2e/evidence.spec.ts` |
| `SRC-02` | Supplementary und External werden nicht als Application Evidence verwendet | `backend/tests/test_run2b_evidence_scope.py`, `e2e/evidence.spec.ts` |
| `SRC-03` | Cross-Scope sowie Generated-/Review-Inhalte ausgeschlossen | `backend/tests/test_run2b_evidence_scope.py` |
| `EVD-01` | Separate Rule Evidence aus der YAML-Registry | `backend/tests/test_run2b_evidence_scope.py`, `e2e/evidence.spec.ts` |
| `EVD-02` | Typisierte fachliche Ablehnung unpassender Evidenz | `backend/tests/test_run2b_evidence_scope.py`, `backend/tests/test_evidence_verification.py` |

Die RUN-2B-XFAILs wurden als normale Regressionen ausgeführt. Bestehende
Gegenpins wurden fachlich an die read-only Dauer und die explizite primäre
Antragsquelle angepasst, nicht entfernt oder abgeschwächt.

## Tatsächliche Testresultate

| Gate | Ergebnis | Laufzeit/Anmerkung |
|---|---|---|
| Preflight Import-Repeat, 10 Wiederholungen, 1 Worker | 40/40 bestanden | vor Produktänderungen |
| Preflight komplette Playwright-Suite, 1 Worker | 48/48 bestanden | vor Produktänderungen |
| Alembic Fresh/Up-Down-Up | bestanden | Roundtrip-Test einzeln 1/1 in 9,95 s; Migrationstests 3/3 |
| Gezielte Import-Review-Vitest-Suite | 18/18 bestanden | 10,69 s |
| Vollständiges Pytest | 1.376 bestanden, 4 übersprungen | Exit 0, 417,6 s; die vier Skips sind ausschließlich Real-Provider-Smokes |
| Vollständiges Vitest | 508/508 in 70 Dateien bestanden | Exit 0, 41,7 s |
| ESLint | bestanden | 9,5 s |
| TypeScript `tsc --noEmit` | bestanden | 7,1 s |
| Next.js Production Build | bestanden | 29,7 s |
| Finaler Import-Repeat, 10 Wiederholungen, 1 Worker | 40/40 bestanden | 2,2 min |
| Final komplette Playwright-Suite, 1 Worker | 48/48 bestanden | 2,7 min |
| `scripts/verify_all.ps1` | vollständig grün, Exit 0 | 624,7 s; einschließlich DOCX, zweitem Golden Path, Import, Review-Truth und API-Smoke |
| Live-Provider-Smokes | `not_run` | bewusst opt-in; nicht als bestanden gewertet |

Das Gesamtgate verwendete ausschließlich Fake-Provider und eine frische,
wegwerfbare SQLite-Datenbank. `scripts/verify_all.ps1` nutzt für Pytest eine
repositorylokale Tempbasis, um den bekannten Windows-Berechtigungsfehler unter
`%TEMP%` zu vermeiden; Assertions und Timeouts wurden dadurch nicht verändert.

## Risiken und bewusste Grenzen

- Die alte `duration_months`-Spalte bleibt für Schema-Kompatibilität vorhanden,
  ist aber keine fachliche Wahrheit mehr.
- Uneindeutige Legacy-Projekte bleiben bewusst `needs_selection`; es wird keine
  Quelle geraten.
- Ein Undo nach einer späteren manuellen Zieländerung überschreibt den
  Nutzerwert bewusst nicht und erfordert manuelle Auflösung.
- Live-Modell-, Live-Firecrawl-, Provider-Preflight- und supervised-live E2E
  wurden nicht ausgeführt. RUN 2B enthält keine Aussage über deren Erfolg.
- Die bekannten Vitest-Warnungen zu nicht gemockten Nebenabfragen und React
  `act(...)` bestanden bereits; sie machen das Gate nicht rot und wurden in RUN
  2B nicht erweitert.

## Kumulativer Diffstat

Gegen `d04e77776c2505de4e67ac17ca1950a3142b9ebd` einschließlich dieses
Ergebnisdokuments:

```text
88 files changed, 5068 insertions(+), 1170 deletions(-)
```

Die Löschungen enthalten insbesondere den getrackten Rohprompt sowie lokale
Datenbank- und Logartefakte aus dem Preflight. Abschließend wurden
`git diff --check`, Secret-Signatur-Scan, Commitbasis und Working Tree erneut
geprüft.

RUN 3 wurde nicht begonnen.
