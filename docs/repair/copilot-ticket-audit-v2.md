# Copilot-Ticket-Audit v2

Audit der 24 v1-Tickets. Kategorien: **sicher** (Copilot geeignet) · **splitten** · **menschliche Vorarbeit** · **Architekturentscheid zuerst** · **Tests zuerst** (vor Implementation) · **human-led** (Copilot nur Zuarbeit).

## 1. Audit-Tabelle

| Ticket | Urteil | Befund | Massnahme |
|---|---|---|---|
| T-1.1 Legacy-Inventar | sicher | klar begrenzt, kein Backend | unverändert |
| T-1.2 ReviewPackage-View | sicher + Review | Zähllogik ist heikel; Wiederverwendung bestehender Funktionen ist vorgeschrieben | Merge-Gate: Paritätstest; menschliches Review der Zählpfade |
| T-1.3 FE-Umstellung | sicher | hängt an 1.2 | unverändert |
| T-2.1 Finding-Migration | menschliche Vorarbeit | Migration auf SQLite; Audit-Historie betroffen | Datenmodell-Review vor Umsetzung; nur additive Spalten; Roundtrip-Test zuerst |
| T-2.2 Fingerprint+Befüllung | **splitten** | 3 Module (neu, gate.py, checks.py) in einem Ticket; Idempotenz-Risiko | T-2.2a `fingerprint.py` pure + Tests (TDD); T-2.2b Befüllung gate.py; T-2.2c Befüllung checks.py. Do-not-touch: finding_code-Format |
| T-2.3 Gruppierung+Queue | sicher | nach 2.2 | unverändert |
| T-2.4 UI-Gruppierung | sicher | Flag vorhanden | unverändert |
| T-2.5 Regelmeldungen | sicher + Textfreigabe | Risiko: Copilot erfindet Förderaussagen | Meldungstexte kommen aus human-freigegebenem Katalog; Copilot verdrahtet nur |
| T-2.6 Registry-Metadaten | **human-led** | Inhalte (Quelle, last_checked) sind Datenpflege, nicht Code | Copilot: nur Loader-Validierung + Anzeige; Metadaten-Inhalte Mensch |
| T-3.1 UI-Modi | Architekturentscheid zuerst | Mapping-Tabelle + Bestandsmigration alt→neu ist Policy | Mensch legt Tabelle+Migrationszuordnung fest; danach Copilot |
| T-3.2 Policy-Matrix+Reasons | **splitten** + Tests zuerst | BE-Matrix und Reason-Codes sind zwei Risiken | T-3.2a Kombinationsmatrix-Tests (zuerst) + BE-Matrix; T-3.2b Reason-Codes + FE-CTA-Mapping |
| T-3.3 NDA-Gate Editor | sicher | E2E Pflicht | unverändert |
| T-4.1 advisory-facts-Rename | sicher | klein, klar | unverändert |
| T-4.2 A2-Profile 6 Felder | **splitten** | 6 Profile in einem Ticket = grosser Prompt-Diff | 3 Tickets à 2 Felder; je Feld Limit-Test zuerst; Abstract/Exec-Summary-Paar zuerst (härteste Limits) |
| T-4.3 Platzhalter-Menü | **splitten** (klein) | FE-Menü + API-Zusatz (OpenIssue) mischen Schichten | T-4.3a API «Frage an Nutzer»; T-4.3b FE-Menü |
| T-4.4 Empty-State-CTAs | sicher | reine FE-Matrix | unverändert |
| T-5.1 EvidenceStatus-Enum | Tests zuerst | Ableitungstabelle ist die Fachlogik | Kombinationsmatrix als Tests vor Implementation; dann Copilot sehr geeignet |
| T-5.2 Claim-Panel+Microcopy | sicher | — | unverändert |
| T-5.3 Copy-Stufen | sicher | — | unverändert |
| T-6.1 BudgetItem+Migration | Architekturentscheid + menschliche Vorarbeit | Aggregat-read-only-Regel ist Datenmodell-Entscheid | Review des Modells vor Ticket; Migration human-reviewt |
| T-6.2 Rechner+Live-UI | **splitten** + Tests zuerst | Rechnerkern und FE trennen; Formel-Parität mit Regel-Handlern kritisch | T-6.2a Rechnerkern TDD (Goldwerte, gemeinsamer Kern mit Handlern, Import-Graph-Test); T-6.2b FE-Anzeige |
| T-6.3 Intake-Entschlackung | Architekturentscheid zuerst | Migrationszuordnung Bestandsdaten | Mensch definiert Zuordnung; dann Copilot |
| T-6.4 Attachment-Gates | sicher | Contract-basiert, deterministisch | unverändert |
| T-7.1 Import komplett | **splitten** | BE-Mapping + API + FE-Review-UI in einem = zu gross | T-7.1a BE-Mapping (Spike portieren, Fixtures-TDD); T-7.1b ImportCandidate-API + Persistenz; T-7.1c FE-Review-Tabelle + Intake-Startoptionen. Gate (R0) davor |
| T-8.1 Query-Planner+Freigabe | **splitten** + Tests zuerst (Pflicht) | Sicherheitskritisch | T-8.1a Leakage-Negativsuite (vor jeder Implementation, Merge-Stopper); T-8.1b Planner; T-8.1c Freigabe-UI. Do-not-touch: search_query_firewall.py |
| T-8.2 D0-Quellen+Panel | sicher | nach 8.1 | unverändert |
| T-8.3 Rubric-Heuristiken | sicher + Textfreigabe | Fixtures zuerst; Texte human | v0-Teil (3 Heuristiken) wandert nach R6 |
| T-8.4 Evaluationsset | **human-led** | Goldstandard-Urteile und Anonymisierung sind Expertenarbeit | Copilot: nur Auswertungsskript + CI-Smoke; Fälle/Gold human (ab R0) |

**Gestrichen/verschoben:** kein v1-Ticket gestrichen. Verschoben: T-8.4→R0/R9 (Harness/Auswertung), T-8.3-v0→R6, T-7.x→R3.

## 2. Neue Tickets (v2)

| Ticket | Milestone | Inhalt | Copilot? |
|---|---|---|---|
| T-0.1 | R0 | Eval-Harness-Skelett + CI-Smoke (Fake-Modus) | ja |
| T-0.2 | R0 | Synthetischer Goldfall 1 (Feldmapping+Findings) | human-led (Copilot: Format) |
| T-0.3 | R0 | Gate-Report-Vorlage + PDF-Gate-Lauf dokumentieren | human |
| T-1.4 | R1 | Status-Paritätstest als CI-Merge-Gate verankern | ja |
| T-4.5 | R4 | ProviderPolicy-Konfig + Doku gemäss E-02 | human definiert, Copilot verdrahtet |
| T-5.4 | R5 | AIProposal-Schema pinnen (operation.result → typisiert) | ja |
| T-5.5 | R5 | Prompt-Snapshot-Regressionstests + Versions-Bump-Regel | ja |
| T-5.6 | R5 | Injection-Fixture-Suite (5 Muster) als Merge-Gate | Fixtures human-kuratiert; Runner Copilot |
| T-3.4 | R3 | No-Raw-Logging-Erweiterung Import-Pfad (safe_detail) + Tests | ja, mit Security-Review |
| T-5.7 | R5 | No-Raw-Logging-Erweiterung A2-Kontext/Fehlerpfade + Tests | ja, mit Security-Review |
| T-9.1 | R9 | Security-Gate-Checkliste abarbeiten (je Punkt Testnachweis) | teils; Bewertung human |
| T-9.2 | R9 | Rollen-Endpoint-Matrix + 403-Tests | ja, Review human |
| T-9.3 | R9 | Performance-Smoke (Grossfixture) + Messreport | ja |
| T-9.4 | R9 | Reload-Guard ungespeicherte Änderungen (app-shell) | ja |
| T-9.5 | R9 | Disclaimer-Katalog + grep-Tests | ja, Texte human-freigegeben |
| T-9.6 | R9 | A11y-Lint + Kurzcheck-Protokoll | ja |
| T-9.7 | R9 (optional) | Agent-Trace-Ansicht (Run-Stufen, Agentenbeiträge, HITL-Punkte, read-only aus Audit/Invocations) | ja |
| T-9.8 | R9 | Finale Evaluation ausführen + Bericht | human-led |

## 3. Reihenfolge (verbindlich)

R0: T-0.1→T-0.3 · R1: T-1.1→T-1.2→T-1.3→T-1.4 · R2: T-2.1→T-2.2a→T-2.2b→T-2.2c→T-2.3→T-2.4 (parallel: T-2.5 nach Textfreigabe, T-2.6 human) · R3: T-7.1a→T-7.1b→T-7.1c→T-3.4 (oder R3'-Tickets) · R4: T-3.1→T-3.2a→T-3.2b→T-3.3→T-4.5 · R5: T-4.1→T-5.4→T-5.5→T-4.2(×3)→T-4.3a→T-4.3b→T-4.4→T-5.6→T-5.7 · R6: T-5.1→T-5.2→T-5.3→T-8.3-v0 · R7: T-6.1→T-6.2a→T-6.2b→(T-6.3 falls nicht R3')→T-6.4→(WP-Slice nur bei E-04=Ja) · R8: T-8.1a→T-8.1b→T-8.1c→T-8.2→T-8.3-v1 · R9: T-9.1–T-9.8.

## 4. Do-not-touch-Dateien (für Copilot in allen Tickets)

- `backend/app/security/search_query_firewall.py` (nur zusätzliche Tests erlaubt)
- `backend/app/security/policy_matrix.py`, `redaction.py`, `sessions.py`, `deps.py` — Änderungen nur im dafür vorgesehenen Ticket mit Security-Review
- `finding_code`-Erzeugungsformate in `gate.py`/`checks.py` (nur ergänzen)
- Scope-Hash-Bestandteile in `review/package.py`
- Zweig-Semantik in `rules/handlers.py` («missing rät nie pass/fail»)
- Node-Reihenfolge in `runs/graph.py`
- `final_backend_contracts_v1_1/*`-Regelinhalte (nur Metadatenfelder ergänzen; Werte human)

## 5. Merge-Gates (global, ab dem jeweils genannten Milestone)

1. `scripts/verify_all.sh` grün — immer.
2. Status-Paritätstest grün — ab R1.
3. Idempotenz-Regression (Findings-Row-Count über 2 Runs) — ab R2.
4. Kein neuer `isMock("legacy")` (Lint) — ab R1.
5. No-Raw-Logging-Suite grün — ab R3 (Import) bzw. R5 (A2), vollumfänglich ab R9.
6. Injection-Suite grün — ab R5.
7. Leakage-Negativsuite grün — ab R8; rot = Merge-Stopp ohne Ausnahme.
8. Migrationen: Roundtrip-Test + menschliches Review — R2, R7.
9. Meldungs-/Disclaimer-Texte: nur aus freigegebenem Katalog — ab R2.

## 6. Rollbackstrategie (kumulativ)

- Jeder Milestone endet mit Git-Tag; R0 setzt `pre-repair-v2`.
- Feature-Flags: groupedFindings (R2), innolinkImport (R3), Verarbeitungsmodi-Fallback alt (R4), A2-Profile je Feld (R5), Statusleiter/Copy-Stufen (R6), Rubric-Heuristiken einzeln (R6/R8), Market-Planner/Panel (R8).
- Migrationen ausschliesslich additiv mit Downgrade; keine Migration und kein DB-Wechsel im selben Zeitraum (Postgres-Umzug nur in R9, nach letzter Migration).
- FE-Umstellungen: alte Props/Zweige eine Version deprecated, dann entfernt.
