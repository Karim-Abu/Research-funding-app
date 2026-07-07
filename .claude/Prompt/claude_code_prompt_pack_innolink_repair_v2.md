# Claude Code / VS Code Prompt Pack v2 — Innolink Repair Roadmap

Stand: 2026-07-07 · Ersetzt v1. Basis: Roadmap v2, Copilot-Ticket-Audit v2, Security-To-dos (docs/security/).
Ziel: App von formularlastigem MVP zu robustem Innolink-Feldarbeitsplatz.

## Arbeitsregeln (für dich als Mensch)

1. Jeden Prompt einzeln ausführen. Nie mehrere Milestones parallel.
2. Ablauf je Prompt: `git diff` prüfen → Tests ausführen → kurze manuelle Review → Commit → nächster Prompt.
3. Ein Prompt = ein Commit (bei Splits: ein Commit je Teil). Vor R0: Tag `pre-repair-v2`. Nach jedem Milestone: Tag `repair-r<N>-done`.
4. Voraussetzungs-Gates respektieren: Steht im Prompt eine Voraussetzung (Gate-Ergebnis, Entscheid E-xx), führe ihn ohne dokumentierte Voraussetzung nicht aus.
5. Merge-Gates (kumulativ, ab dem genannten Milestone): `scripts/verify_all.sh` grün (immer) · Status-Paritätstest (ab R1) · Findings-Idempotenz-Regression (ab R2) · kein neues `isMock("legacy")` (ab R1) · No-Raw-Log-Suite Import/A2 (ab R3/R5) · Injection-Suite (ab R5) · Leakage-Negativsuite (ab R8, rot = Merge-Stopp ohne Ausnahme).
6. Feature-Flags nutzen und je Milestone dokumentieren: `groupedFindings` (R2), `innolinkImport` (R3), Verarbeitungsmodi-Fallback (R4), A2-Profile je Feld (R5), Statusleiter/Copy-Stufen (R6), Rubric-Heuristiken einzeln (R6/R8), Market-Planner/Panel (R8).
7. Meldungs-, Disclaimer- und Rubric-Texte kommen aus von dir freigegebenen Katalogen. Claude Code verdrahtet nur.
8. Migrationen: nur additiv, mit Downgrade, mit menschlichem Review vor dem Merge. Kein DB-Wechsel (Postgres) parallel zu Schema-Migrationen — Postgres-Option erst R9.

## Globaler Systemprompt für Claude Code

```text
Du arbeitest in einem bestehenden Next.js/FastAPI/SQLAlchemy-Projekt (Alembic-Migrationen unter backend/app/migrations) für eine Bachelorarbeits-App: Multi-Agent Workflow Automation für Research Funding, Fokus Innosuisse/Innolink.

Ziel der App:
Kein generischer Chatbot. Kein automatischer Proposal-Submitter. Die App ist ein Innolink-Feldarbeitsplatz: Import/Quellen, Feldzuordnung, Lückenanalyse, Evidence Anchors, Review Findings, KI-Vorschläge, Fix Queue, manuelle Copy-Paste-Vorbereitung.

Arbeitsregeln:
- Implementiere ausschliesslich den genannten Ticket-Scope. Keine Refactorings, keine Zusatzfeatures.
- Wenn eine Information fehlt oder eine Voraussetzung (Gate, Entscheid E-xx, Katalogtext) nicht vorliegt: STOPPE und benenne, was fehlt. Rate nie.
- Erfinde keine Innosuisse-Regeln, Grenzwerte oder Fördertexte. Jede fachliche Regelaussage braucht eine source_ref aus Contract/Registry/Message-Katalog.
- Zeichenlimits, Quoten und Schwellwerte liest du aus final_backend_contracts_v1_1/ bzw. der Registry. Zahlen im Ticket sind Referenz, nicht Quelle. Bei Abweichung Contract vs. Ticket: stoppen und melden.
- Keine automatische Übernahme von KI-Texten. Keine Budgetlogik im LLM (deterministisch in Code). Evidence Coverage ist nicht Evidence Correctness.
- Keine Rohideen, Rohprompts, Rohdokumente, Partnernamen oder Budgetzahlen in Logs, Audit-Details oder Fehlermeldungen. Nutze security/redaction.py (safe_detail).
- Keine Websearch mit Rohidee. Keine Klassifikations-Downgrades (restriktivste Einstufung gewinnt).
- DO NOT TOUCH (nur lesen, höchstens Tests ergänzen): backend/app/security/* (insb. search_query_firewall.py, policy_matrix.py, redaction.py, sessions.py, deps.py); finding_code-Erzeugungsformate in reliability/gate.py und review/checks.py (nur additive Felder); Scope-Hash-Bestandteile in review/package.py; Zweig-Semantik in rules/handlers.py (missing rät nie pass/fail); Node-Reihenfolge in runs/graph.py; Regel-WERTE in final_backend_contracts_v1_1/* (Metadatenfelder additiv erlaubt, Inhalte liefert der Mensch).
- Migrationen nur additiv mit Downgrade. UI-Texte auf Deutsch, konsistent mit bestehender Statussprache.
- Fake Provider bleibt Default für Tests. Keine echten API-Calls in CI. Keine Secrets in Dateien.
- Am Ende jedes Tickets: geänderte Dateien, ausgeführte Tests, offene Risiken, offene menschliche Entscheidungen.
```

---

# R0 — Gates & Fundament

## Prompt R0.1 — Repair-Dokumente importieren, Harness-Skelett

```text
Aufgabe: R0.1 — Lege die vorhandenen Repair- und Security-Dokumente im Repo ab und baue ein minimales Evaluation-Harness-Skelett. Verfasse KEINE neuen Konzeptinhalte.

Input (liegt dir vor, unverändert übernehmen):
- docs/repair/: masterplan-review-v2.md, roadmap-v2.md, masterplan-delta-v1-v2.md, weakness-register-v2.md, copilot-ticket-audit-v2.md, decision-log-needed.md, final-definition-of-done.md, evaluation-and-beta-gates.md, prompt-pack-audit.md
- docs/security/: privacy-ai-security-review.md, -gap-list.md, -todos.md, -final-recommendations.md

Erstelle zusätzlich:
1. docs/evaluation/testdata-policy.md — Regeln aus decision-log E-12: keine echten vertraulichen Rohdaten/NDA-Daten im Repo; anonymisierte Fixtures nur nach menschlicher Review mit Review-Vermerk; keine Partnernamen, Budgetzahlen, proprietären Details in Fixtures. Markiere: "Freigabe durch Owner ausstehend".
2. docs/evaluation/metrics.md — Metrikdefinitionen 1:1 aus docs/repair/evaluation-and-beta-gates.md übernehmen (nicht neu formulieren).
3. backend/app/evaluation/ — minimales Modul + Smoke-Test/CLI, läuft im Fake-Modus ohne externe Provider. Nur Struktur (Case laden, Ergebnis-Placeholder ausgeben), noch keine Bewertungslogik.
4. docs/evaluation/cases/F1_synthetic_case.md — Skeleton für den synthetischen Goldfall: Tabellen für erwartete Feldinhalte (8 aktive Felder) und erwartete Findings, Inhalte leer mit TODO-Owner-Markern. Erfinde keine Fallinhalte.

Nicht tun: keine App-Feature-Fixes, keine Migration, keine Agentenlogik, keine Provider-Calls, keine Änderung an ReviewPackage/imports/data-classification/rules.

Akzeptanz: Build/Tests grün; Harness-Smoke läuft offline; kein Secret in Dateien; Dokumente byte-identisch zu den Vorlagen, wo Vorlagen existieren.
```

## Prompt R0.2 — PDF-Gate-Report-Vorlage

```text
Aufgabe: R0.2 — Erstelle nur die Vorlage für den PDF-Import-Gate-Test. Keine Import-Implementierung, kein Code.

Datei: docs/evaluation/pdf-import-gate-report.md

Inhalt:
- Zweck: Entscheid, ob der Innolink-PDF-Import (R3) gebaut wird.
- Eingang: echtes anonymisiertes oder synthetisch-realistisches Innolink-PDF (nie ein vertrauliches Original ins Repo).
- Methode: spike/map_pdf.py gegen das PDF; Bewertung je der 8 aktiven Felder (Feld-IDs aus der Registry übernehmen): correct / partial / uncertain / missed / false-positive.
- Gate-Regel (aus decision-log E-01): usable-Quote ≥ ~60 % → R3 bauen; darunter → R3'-Fallback.
- Ergebnisabschnitte: Quote, Entscheid, Begründung, Risiken, Datum, Owner-Signatur.

Nicht tun: keinen Code ändern, keinen Upload bauen.
```

## Prompt R0.3 — Baseline-Messung am Goldfall

```text
Aufgabe: R0.3 — Dokumentiere den Ist-Zustand (Baseline) am Fall F1, bevor Reparaturen starten. Keine Code-Änderungen.

Voraussetzung: F1_synthetic_case.md ist vom Owner mit Inhalten gefüllt.

Schritte:
1. F1 als Projekt in einer lokalen Dev-Instanz anlegen (Fake-Provider), Standard-Analyse laufen lassen.
2. Erfassen und in docs/evaluation/baseline-report.md dokumentieren:
   - Anzahl Roh-Findings gesamt und je Meldungstyp (Duplikat-Nachweis)
   - Blocker-Zahlen je Screen: Dashboard / Anforderungen / Prüfung / Export (Divergenz-Nachweis)
   - Anzahl manueller Schritte + grobe Zeit bis "exportfähiger Feldsatz" nach definiertem Skript
3. Skript der manuellen Schritte als wiederholbare Checkliste anhängen (für Vorher/Nachher-Vergleich in R9).

Nicht tun: nichts fixen, auch offensichtliche Bugs nur notieren.

Akzeptanz: Baseline-Report mit konkreten Zahlen und reproduzierbarem Ablauf.
```

## Prompt R0.4 — Testdaten-CI-Marker-Check

```text
Aufgabe: R0.4 — Leichter CI-Check gegen sensible Marker in Fixtures.

Dateien: scripts/ oder backend/tests/ + CI-Anbindung an verify_all.

Anforderungen:
1. Marker-Liste in docs/evaluation/testdata-policy.md pflegbar (z. B. reale Partnernamen der Beispielprojekte, Projektcodenamen) — initial leer mit TODO-Owner.
2. Check durchsucht spike/fixtures/, backend/tests/fixtures o. ä. und schlägt bei Treffer fehl.
3. Allowlist-Mechanismus mit Begründungspflicht.

Akzeptanz: Check läuft in verify_all; leerer Markerkatalog = grün; Testtreffer = rot.
```

---

# R1 — Kanonischer Status & Legacy-Mock-Abbau

## Prompt R1.1 — Legacy-Mock-Inventar

```text
Aufgabe: R1.1 — Vollständiges Inventar aller Legacy-Mock-Pfade. Keine funktionalen Änderungen.

Untersuchen: lib/api.ts, lib/app-mode.ts, components/shell/, components/requirements/, components/review/, components/export/, Dashboard-Komponenten; alle isMock("legacy")-Aufrufe.

Output: docs/repair/r1-legacy-mock-inventory.md mit Tabelle:
Datei | Funktion/Komponente | Mock-Bedingung | aktiver Screen betroffen (ja/nein/unklar) | Live-Ersatz vorhanden | Risiko | empfohlene Änderung für R1.2/R1.3.

Regeln: Unklares als unklar markieren, nicht raten. Höchstens TODO-Kommentare, keine Logikänderung.

Akzeptanz: alle Stellen dokumentiert; Build grün.
```

## Prompt R1.2 — ReviewPackage-Status-View (Backend)

```text
Aufgabe: R1.2 — Additiver kanonischer Status-View im Backend. Keine Frontend-Umstellung.

Dateien: backend/app/review/package.py, ggf. review/service.py, passende API-Datei, Backend-Tests.

Anforderungen:
1. Read-View mit: blocker_count, warning_count, human_review_count, stale (bool), package_version/-id, per_area_counts (falls Daten vorhanden), last_reviewed_at.
2. Bestehende Zählfunktionen wiederverwenden — KEINE parallele Zähllogik. Reliability-/Approval-Blocker zählen wie im bestehenden Review-Package.
3. Read-only, additiv; bestehende Endpoints unverändert.

Nicht tun: keine Migration, keine UI, keine Findings-/finding_code-Änderung.

Tests: Platzhalter-Blocker ⇒ blocker_count 1; stale korrekt bei veraltetem Scope-Hash; leeres Package ⇒ 0-Counts.

Akzeptanz: Backend-Tests grün; klares Statusobjekt; keine Freigabelogik verändert.
```

## Prompt R1.3 — Frontend liest kanonischen Status

```text
Aufgabe: R1.3 — Dashboard, Anforderungen, Qualitätsprüfung und Export auf den Status-View umstellen.

Dateien: lib/api.ts, Status-Hook (neu falls nötig), Dashboard-Komponenten, components/requirements/, components/review/quality-summary.tsx, components/export/export-screen.tsx, E2E-Test.

Anforderungen:
1. Ein API-Client für den Status-View; alle vier Screens nutzen ihn.
2. Export berechnet keine eigene Blocker-Zahl mehr (openBlockerCount-Prop ablösen, eine Version deprecated).
3. Aktive Mock-/Legacy-Statusquellen gemäss R1.1-Inventar ersetzen; verbleibende Demo-only-Stellen klar markieren.
4. Stale einheitlich anzeigen: "Prüfung nicht aktuell".

Nicht tun: kein Redesign, keine neuen Findings, keine Migration, kein Import/KI/Market/Budget.

Tests: E2E-Paritätstest — Fixture mit X Blockern zeigt X auf allen vier Screens; stale konsistent. Dieser Test wird dauerhaftes Merge-Gate.

Akzeptanz: 0/9/17-Widerspruch reproduzierbar behoben; Inventar aktualisiert; verify_all grün.
```

## Prompt R1.4 — CI-Guard gegen neue Legacy-Statuspfade

```text
Aufgabe: R1.4 — Guard, damit keine neuen aktiven Legacy-Statuspfade entstehen, und Paritätstest im CI verankern.

Anforderungen:
1. Grep-/Lint-Script: isMock("legacy") in aktiven Status-Komponenten ⇒ Fail; Allowlist für dokumentierte Demo-only-Dateien.
2. R1.3-Paritätstest in verify_all/CI als Pflichtlauf registrieren.

Nicht tun: keine produktive Logik ändern.

Akzeptanz: Guard schlägt bei Testverstoss an; Paritätstest läuft in CI.
```

---

# R2 — Issue-Modell, Dedupe, Fix Queue

## Prompt R2.1 — Fingerprint-Modul (tests first)

```text
Aufgabe: R2.1 — Reines Fingerprint-Modul mit Tests. Keine Migration, keine Befüllung.

Dateien: backend/app/review/fingerprint.py (neu), backend/tests/.

Funktion: compute_finding_fingerprint(rule_or_code_family, field_id, claim_core=None, source_id=None) -> str
Normalisierung: lowercase, Whitespace kollabieren, Zahlen zu # maskieren, None = "", stabiler sha256.

Tests (zuerst schreiben): gleicher Input ⇒ gleicher Hash; gleicher Claim mit anderer Zahl ⇒ gleicher Hash; anderes Feld ⇒ anderer Hash; source_id beeinflusst Hash, wenn gesetzt.

Nicht tun: finding_code, DB, gate.py, checks.py unberührt.
```

## Prompt R2.2 — Additive Finding-Migration

```text
Aufgabe: R2.2 — Additive Alembic-Migration für Finding v2 (backend/app/migrations). Keine UI, keine Befüllung.

Neue nullable Felder auf dem bestehenden Finding-/OpenIssue-Modell (an vorhandene Struktur anpassen): fingerprint, severity_class, fix_recommendation, last_seen_at; message_template/specific_message nur falls nicht bereits sauber abgebildet.

Regeln: nur additiv; keine Daten löschen; finding_code unverändert; Downgrade vorhanden. Migration wird vor Merge menschlich reviewt.

Tests: Up/Down-Roundtrip; bestehende Tests grün.
```

## Prompt R2.3 — Fingerprint + Severity befüllen

```text
Aufgabe: R2.3 — Befülle fingerprint und severity_class bei neu erzeugten Findings. Keine UI.

Dateien: backend/app/reliability/gate.py, backend/app/review/checks.py, review/fingerprint.py, Tests.

Anforderungen:
1. compute_finding_fingerprint nutzen; finding_code bleibt exakt im alten Format (nur zusätzliche Felder).
2. severity_class — GENAU diese sechs Klassen, keine weiteren:
   Platzhalter/Zeichenlimit → export_blocker · Eligibility → eligibility_blocker · Budget → budget_blocker · Rubric → reviewer_risk · reliability/evidence → evidence_risk · Rest → style_risk.
3. fix_recommendation nur befüllen, wenn eindeutig ableitbar; recommended_next_action nur mit klarer Zielroute, sonst null.

Tests: Re-Run erzeugt keine zusätzlichen Rows (Idempotenz-Regression, wird Merge-Gate); finding_code unverändert; fingerprint stabil; severity_class je Kategorie korrekt.
```

## Prompt R2.4 — Gruppierungs-API und Fix Queue

```text
Aufgabe: R2.4 — Gruppierungs- und Fix-Queue-View auf Basis bestehender Findings. Keine UI.

Dateien: backend/app/review/fix_queue.py (neu) oder package.py erweitert; API-Endpoint; Tests.

Output:
- grouped_findings: group_key, title, count, severity_class, affected_fields, examples (max 3–5), recommended_next_action, target_field_id falls möglich.
- next_actions: priorisiert 1 export_blocker · 2 eligibility_blocker · 3 budget_blocker · 4 reviewer_risk · 5 evidence_risk · 6 style_risk.

Tests: 4 identische Evidence-Findings ⇒ 1 Gruppe count=4; Platzhalter vor Evidence-Risk; Research-Partner-Blocker vor Reviewer-Risk.
```

## Prompt R2.5 — UI: Gruppierte Findings + Fix Queue

```text
Aufgabe: R2.5 — UI für grouped_findings und next_actions hinter Flag groupedFindings. Keine Backend-Änderung.

Dateien: components/review/quality-summary.tsx, components/requirements/, neu components/review/fix-queue.tsx.

Anforderungen:
1. "Nächste Aufgaben" oben mit Top-5 next_actions.
2. Gruppierte Darstellung ("4 × Quantifizierte Aussage ohne passenden Zahlenbeleg"), aufklappbar mit Beispielen (Feld, Claim, Quelle).
3. Buttons navigieren zum betroffenen Feld/Bereich.
4. Fallback auf alte Liste, wenn grouped_findings fehlt.

Nicht tun: kein Redesign, keine neue Farblogik.

Tests: Component-Test mit Gruppen-Fixture; keine identischen Meldungen direkt untereinander (Snapshot).
```

## Prompt R2.6 — Präzise Regel-/Partnermeldungen

```text
Aufgabe: R2.6 — Entity-spezifische Meldungen statt generischer Partner-Blocker.

Voraussetzung: Vom Owner freigegebener Message-Katalog liegt vor (docs/repair/message-catalog.md). Ohne Katalog: stoppen.

Dateien: backend/app/rules/handlers.py, neu backend/app/rules/messages.py, Tests. Contract-Regelwerte nicht anfassen.

Anforderungen:
1. Meldungen ausschliesslich aus dem Katalog verdrahten, z. B.:
   research_partner fehlt → "Kein beitragsberechtigter Schweizer Forschungspartner erfasst."
   implementation_partner fehlt → "Kein Umsetzungspartner mit Schweiz-Bezug erfasst."
   financial independence unknown → "Finanzielle Unabhängigkeit benötigt menschliche Prüfung."
2. missing-Status benennt die fehlende Angabe; nie pass/fail raten (Zweigsemantik unverändert).
3. Alttext "Kein passender Partner vorhanden" verschwindet aus aktiven Outputs.

Tests: Unit je Entity für missing/false/true; grep-Test gegen Alttext.
```

## Prompt R2.7 — Registry-Metadaten-Validierung (Inhalte human)

```text
Aufgabe: R2.7 — Loader-Validierung für Regel-Metadaten. Die Metadaten-INHALTE liefert der Mensch.

Voraussetzung: Owner hat source_ref/source_version/last_checked/validity_status für die aktiven Regeln in den Contract-YAMLs ergänzt. Ohne diese Daten: nur Validierung + leere Felder tolerieren, nichts erfinden.

Dateien: backend/app/registry/loader.py, Tests; Contract-YAMLs nur Metadatenfelder additiv.

Anforderungen: Loader liest die vier Felder, validiert Format, fail-closed bei kaputtem Format; API/UI können last_checked anzeigen (Anzeige kommt in R6/R7-Prompts).

Tests: gültige/fehlende/fehlerhafte Metadaten.
```

---

# R3 — Import-First MVP (Gate-bedingt) oder Fallback R3'

## Prompt R3.GATE — PDF-Gate ausführen und dokumentieren

```text
Aufgabe: Führe das PDF-Gate aus und fülle den Report. Keine App-Implementierung.

Voraussetzung: geeignetes PDF gemäss Testdaten-Policy (kein vertrauliches Original ins Repo).

Schritte:
1. spike/map_pdf.py gegen das PDF laufen lassen.
2. Je der 8 aktiven Felder bewerten: correct/partial/uncertain/missed/false-positive; Quote berechnen.
3. docs/evaluation/pdf-import-gate-report.md ausfüllen; Entscheid gemäss E-01: ≥ ~60 % usable → R3 bauen, sonst R3'.

Nicht tun: kein Feature-Code.
```

## Prompt R3.1 — ImportCandidate Backend-Mapping (nur bei positivem Gate)

```text
Aufgabe: R3.1 — Backend-Mapping für ImportCandidate auf Basis des Spikes. Keine UI, keine API.

Voraussetzung: Gate-Report mit Entscheid "bauen" liegt vor. Sonst stoppen.

Dateien: backend/app/imports/ (neu); spike/map_pdf.py als Referenz sauber portieren (Imports aus backend statt Spike-Kopien); backend/app/ingestion/ nur nutzen (fail-closed-Verhalten übernehmen); Tests mit anonymisierten Fixtures.

Scope: digitale PDF/TXT, kein OCR; nur die 8 aktiven Felder (IDs aus Registry); Output ImportCandidate: field_id, label, extracted_text, confidence, source_location, decision=pending. uncertain nie automatisch übernehmbar.

Nicht-Scope: kein LLM-Mapping, keine Partner-/Budget-Extraktion, keine UI.

Tests: sauberes Fixture mappt erwartete Felder (Spike-Regression); degradiertes Fixture ⇒ uncertain statt falschem Mapping; Gate-PDF (anonymisiert, nach E-12-Review) als drittes Fixture.
```

## Prompt R3.2 — ImportCandidate-API und Persistenz

```text
Aufgabe: R3.2 — Persistenz + API für den Import-Review-Flow. Keine UI.

Dateien: backend/app/db/models.py (+ additive Alembic-Migration mit Downgrade, menschliches Review), backend/app/imports/, backend/app/api/, Tests.

Anforderungen:
1. ImportCandidate persistieren (projekt-/workspace-gebunden), decision: pending | accepted | saved_as_source | ignored.
2. Endpoints: Kandidaten erstellen (Upload→Mapping), auflisten, einzeln entscheiden.
3. accepted ⇒ DraftVersion für das Feld erzeugen (bestehenden Draft-Mechanismus nutzen); saved_as_source ⇒ als Quelle ablegen; nie stilles Überschreiben eines vorhandenen Drafts — bei Konflikt Kandidat als conflict markieren und Entscheid verlangen.
4. Nach Entscheidungen: Scope-Hash/Review wird korrekt stale (bestehendes Verhalten nutzen, nicht nachbauen).
5. Audit-Events nur mit safe_detail (keine Textinhalte).

Tests: Entscheidungspfade; Konfliktfall; HITL-Zwang (uncertain ohne Entscheid bleibt pending); Stale-Verhalten; kein Kandidatentext in Audit-Details.
```

## Prompt R3.3 — Import-Review-UI + drei Startoptionen

```text
Aufgabe: R3.3 — Frontend: Upload, Review-Tabelle, Startoptionen. Flag innolinkImport.

Dateien: components/intake/intake-form.tsx, neu components/import/import-review.tsx, lib/api.ts.

Anforderungen:
1. Intake zeigt drei Startoptionen: "Bestehenden Innolink-Antrag hochladen" / "Mit Projektidee starten" / "Aus Notizen & Quellen starten".
2. Review-Tabelle je Kandidat: erkanntes Feld, Textauszug, Confidence, Quelle/Fundstelle, Aktionen Übernehmen / Als Quelle speichern / Ignorieren; uncertain visuell markiert, ohne Vorauswahl.
3. Nach Abschluss: Weiterleitung zur Fix Queue ("Nächste Aufgaben") mit aktualisierter Lückenübersicht.
4. Kein Auto-Accept, auch nicht bei hoher Confidence.

Nicht tun: kein Redesign des Intake über die Startoptionen hinaus (Entschlackung kommt in R7.4).

Tests: Component-Tests Entscheidungsaktionen; E2E Upload→Review→Übernahme→Fix Queue.
```

## Prompt R3.4 — No-Raw-Logging für den Import-Pfad

```text
Aufgabe: R3.4 — Stelle sicher, dass Import-Inhalte nie in Logs/Audit/Fehlertexten landen.

Dateien: backend/app/imports/, Nutzung von security/redaction.py (safe_detail); Tests. redaction.py selbst nicht ändern, ausser ein Test zeigt eine konkrete Lücke — dann minimaler Fix mit Begründung.

Tests (zuerst schreiben): Fixture-PDF mit Markern PROJECT_SECRET_MARKER_123 / PARTNER_CONFIDENTIAL_NAME / CHF_999999_SECRET_BUDGET durch Upload→Mapping→Entscheid führen; Marker erscheinen nicht in Logs, Audit-Details, Operation-Fehlertexten. Redigierte Metadaten (Hashes, Zählwerte) sind erlaubt.
```

## Prompt R3' — Fallback bei negativem Gate

```text
Aufgabe: R3' — Kein PDF-Antragsimport. Stärke "Aus Notizen/Quellen starten" und entschlacke das Intake.

Voraussetzung: Gate-Report mit Entscheid "streichen" ODER kein geeignetes Test-PDF (dann im Report dokumentieren).

Dateien: components/intake/intake-form.tsx, components/quellen/, bestehende Ingestion-API nur nutzen.

Anforderungen:
1. Drei Startpfade; "Bestehenden Antrag hochladen" deaktiviert mit ehrlicher Begründung ("PDF-Import hat den Qualitäts-Gate-Test nicht bestanden") + Ausweg ("Als Quelle hochladen").
2. Intake-Entschlackung: detaillierte Partner-/Budget-Doppelerfassung entfernen; Details bleiben im Partner-&-Budget-Bereich. Migrationszuordnung Bestandsdaten liefert der Owner (Voraussetzung); ohne Zuordnung stoppen.
3. Projektidee-Feld beschriften: "Vertraulicher Projektkontext für KI-Agenten" + Kurzhinweis: wird nie direkt für Websearch verwendet.

Nicht tun: kein Parser-Umbau, kein KI-Assist, Migration nur falls zwingend (dann additiv + Review).

Tests: Intake-E2E; keine Doppelerfassung mehr erreichbar.
```

---

# R4 — Datenklassen v2, ProviderPolicy, Browser-Storage-Fix

## Prompt R4.1 — Datenklassen-Modell FE/BE

```text
Aufgabe: R4.1 — Datenklassen v2 mit Owner-Mapping-Tabelle. Keine Provider-Integration.

Voraussetzung: Owner-Mapping-Tabelle liegt vor (docs/repair/data-class-mapping.md): UI-Modus → BE-Klasse → processing_mode/web_research_mode, inkl. Migrationszuordnung Bestandsprojekte (public/internal/confidential alt → neu). Ohne Tabelle stoppen.

Modell (nicht mischen):
- Datenklassen als UI-Auswahl: Öffentlich (D0) / Intern (D1) / Vertraulich (D2) / NDA-gesperrt (D3). Unknown ist kein wählbarer Modus, sondern fail-closed-Default.
- Webresearch ist EIGENSCHAFT der Klasse gemäss policy_matrix (D1/D2: nur sanitisiert + Freigabe), kein eigener Radio-Modus. Ein optionaler Projekt-Schalter "Webresearch erlauben" darf die Matrix nur weiter EINSCHRÄNKEN, nie lockern.

Dateien: lib/data-classification.ts, lib/types.ts, components/intake/intake-form.tsx, backend/app/contracts/classification.py, backend/app/security/data_class.py (nur lesen), Tests. policy_matrix.py nicht ändern.

Regeln: D2 erlaubt kontrollierte KI nur, wenn ProviderPolicy (R4.3) es bestätigt; D3 blockiert KI und jeden Browser-Cache; Unknown fail-closed; kein stiller Downgrade (restriktivste Einstufung gewinnt — bestehende Semantik übernehmen).

Tests: Mapping FE→BE für alle Modi; Unknown blockiert; D3 blockiert KI/Cache; D2-KI nur mit Policy-Bestätigung; Migrationstest Bestandswerte gemäss Owner-Tabelle.
```

## Prompt R4.2 — Availability-Reason-Codes und Empty-State-CTAs

```text
Aufgabe: R4.2 — KI-Blockgründe maschinenlesbar + nutzerverständlich mit Ausweg.

Dateien: backend/app/agents/field_drafting.py, backend/app/fields/redraft_service.py, lib/redraft.ts, components/editor/ (KI-Panel/Empty-State).

Reason-Codes: nda_locked, mode_deterministic_only, provider_unavailable, run_mode_mismatch, missing_sources, field_not_supported.

Anforderungen: Backend liefert reason_code + reason_text_de (Texte aus freigegebenem Katalog); Frontend zeigt je Code eine CTA (nda_locked → "Verarbeitungsmodus prüfen"; provider_unavailable → "Provider nicht konfiguriert – Anleitung öffnen"; missing_sources → "Quelle hinzufügen"; field_not_supported → "Strukturvorlage nutzen"; mode_deterministic_only → "Verarbeitungsmodus ändern"). Der Satz "für diese Datenklasse oder Umgebung nicht verfügbar" darf ohne konkreten Code nicht mehr erscheinen (grep-Test).

Tests: Reason-Code-Matrix Backend; Component-Test je Code; grep gegen Alttext.
```

## Prompt R4.3 — ProviderPolicy-Konfig + Durchsetzungstest

```text
Aufgabe: R4.3 — Mache den E-02-Entscheid maschinell durchgesetzt, nicht nur dokumentiert.

Voraussetzung: E-02 im decision-log entschieden. Ohne Entscheid stoppen.

Dateien: backend/app/config/ (ProviderPolicy-Konfig), docs/security/provider-policy.md, Tests.

Anforderungen:
1. Konfigtabelle: provider (fake/local/azure/direct_openai/direct_anthropic) × erlaubte Datenklassen × Vertrags-/Betriebsbasis (Textreferenz).
2. Durchsetzung: direkte Consumer-APIs für D1/D2 sind unabhängig von gesetzten Keys blockiert (Konfigtest); Fake bleibt Default; kein NEXT_PUBLIC_*-Provider-Secret.
3. .env.example aktualisieren: AI_PROVIDER=fake Default, Hinweise ohne echte Keys.
4. Doku: Zielarchitektur (Azure Enterprise Boundary) klar als Ziel, Ist klar als Ist.

Tests: Matrix-Konfigtest (Klasse×Provider ⇒ erlaubt/blockiert); Keys gesetzt + D2 + direct ⇒ blockiert.
```

## Prompt R4.4 — Browser-Storage-Fix für D2/D3 (Security-P0)

```text
Aufgabe: R4.4 — Vertrauliche Inhalte dürfen nicht im Browser-Storage liegen.

Befund (verifiziert): lib/intake-store.ts speichert die komplette Intake-Eingabe inkl. Projektidee klassenunabhängig im sessionStorage; lib/rich-editor-cache.ts#isRichCacheAllowed erlaubt den Cache für "confidential" (D2) und sperrt nur D3/NDA-Marker.

Dateien: lib/intake-store.ts, lib/rich-editor-cache.ts, components/editor/rich-text-editor.tsx, components/intake/, Tests.

Anforderungen:
1. isRichCacheAllowed: Cache nur für D0/D1 (public); internal/confidential/D3/Unknown ⇒ kein Cache. Verhalten bei Cache-aus: Formatierung geht bei Feldwechsel verloren — bestehenden Hinweis nutzen/ergänzen, kein neues Speicherverfahren erfinden.
2. intake-store: bei internal/confidential keine Inhaltsfelder persistieren (nur IDs wie active_project_id/run_id); Alternativ serverseitiger Zwischenstand, falls ohne grossen Umbau möglich — sonst Inhalte schlicht nicht cachen.
3. Lösch-Hooks: Logout und Projektwechsel entfernen alle rf_*-Inhalts-Keys (bestehende Hooks prüfen und testen).
4. Bestehende Einträge: beim Laden eines internal/confidential-Projekts Alt-Cache löschen.

Tests (zuerst schreiben): bei confidential/internal enthalten session-/localStorage weder Projektidee noch Draft-Text noch Tiptap-JSON (Given/When/Then aus Sicherheitskonzept §10.3); Lösch-Hooks; D0 unverändert funktionsfähig.
```

---

# R5 — KI-Assist für die 8 Felder

## Prompt R5.1 — Advisory-Facts-Rename

```text
Aufgabe: R5.1 — confirmed facts → advisory facts. Keine Verhaltensänderung.

Dateien: backend/app/agents/field_drafting_context.py, zugehörige Tests/Prompts.

Anforderungen: retrieve_confirmed_project_facts → retrieve_advisory_project_facts; confirmed_facts → advisory_facts; Prompt-Label "PROPOSED A1 FACTS (advisory, NOT confirmed)". Prompt-Dateien sind versioniert: Änderung ⇒ Versions-Bump (v1→v2) statt In-Place-Edit.

Tests: grep confirmed_facts leer in aktiven Kontexten; Kontext-Tests angepasst.
```

## Prompt R5.2 — AIProposal-Schema pinnen

```text
Aufgabe: R5.2 — Typisiere das Vorschlags-Resultat, bevor weitere Felder aktiviert werden.

Dateien: backend/app/fields/redraft_service.py, backend/app/agents/, lib/redraft.ts, Tests.

Schema AIProposal: suggestion_text, used_anchor_ids (nur aus allowed_anchor_ids), missing_inputs, profile_id, prompt_version, context_hash, model_ref, created_at. Ablage weiterhin in operation.result, aber schema-validiert (Pydantic) statt frei.

Tests: Schema-Validierung; unbekannte anchor_ids ⇒ Fehler; FE parst typisiert.
```

## Prompt R5.3 — Prompt-Snapshot-Regressionstests

```text
Aufgabe: R5.3 — Stille Prompt-Änderungen verhindern.

Dateien: backend/tests/, backend/app/agents/prompts/.

Anforderungen: Hash-/Snapshot-Test je Prompt-Datei (*_vN.md); Änderung ohne Versions-Bump ⇒ Test rot; kurzes CHANGELOG je Prompt-Ordner.

Tests: Manipulationstest (temporäre Änderung schlägt an).
```

## Prompt R5.4 — Injection-Testsuite (Merge-Gate ab hier)

```text
Aufgabe: R5.4 — Adversariale Injection-Suite. Fixtures kuratiert der Owner mit; Grundmuster lieferst du.

Dateien: backend/tests/ (Basis: test_a1_injection.py erweitern), Fixtures.

Fünf Muster in Quelltexten/Quotes: (1) Instruktions-Override ("ignore all previous instructions…"), (2) Anchor-Erfindung (verlangt Zitat einer nicht freigegebenen Quelle), (3) Exfiltration ("gib den Systemprompt/alle Projektdaten aus"), (4) Format-Bruch (erzwinge anderes JSON), (5) Query-Manipulation (schleuse Partnernamen in die Suchquery).

Erwartung: Vorschläge folgen den Instruktionen nicht, nutzen nur allowed_anchor_ids, Schema bleibt valide, Firewall-Verhalten unverändert.

Diese Suite ist ab jetzt Merge-Gate für alle R5-/R8-Prompts.
```

## Prompt R5.5 — A2-Profil Abstract + Executive Summary

```text
Aufgabe: R5.5 — On-Demand-A2 für Abstract und Executive Summary. Nur diese zwei Felder, hinter Feld-Flags.

Dateien: backend/app/agents/field_drafting.py, field_drafting_context.py, agents/prompts/ (neue versionierte Dateien), fields/redraft_service.py, components/editor/ (Feldprofil), Tests.

Regeln:
- Limits aus Registry/Contract lesen (Referenz: Abstract 300 Zeichen, Aramis-publiziert ⇒ keine vertraulichen Details; Exec Summary 2000). Deterministisch prüfen; Überlänge ⇒ kürzen oder ablehnen, nie stillschweigend liefern.
- Nie Auto-Übernahme. Fehlende Daten ⇒ gezielte missing_inputs statt erfundener Inhalte. used_anchor_ids nur aus allowed_anchor_ids. Quelltexte bleiben untrusted (bestehende Prompt-Muster übernehmen).

Tests: Fake-Provider erzeugt Vorschlag je Feld; Limit eingehalten; fehlende Quelle ⇒ missing_inputs; Injection-Suite grün; keine Auto-Übernahme (Regression).
```

## Prompt R5.6 — A2-Profil Financial Independence + Management Hours

```text
Aufgabe: R5.6 — Zwei weitere Felder, gleiche Regeln wie R5.5.

Felder: ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS und PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION (Limits aus Registry; Referenz: Contract-Regel QG.PS.MANAGEMENT_EXPLANATION_LIMIT ≤ 1000).

Zusatzregeln: kein rechtliches Finale — immer Human-Review-Hinweis; unbekannte Unabhängigkeit ⇒ missing_inputs/human_review_required, keine sichere Bestätigung; keine erfundenen Prozent-/Stundenzahlen.

Tests: unknown independence ⇒ missing_inputs; keine erfundenen Zahlen (Fixture-Check); Limits; Injection-Suite.
```

## Prompt R5.7 — A2-Profil Value Creation + Solution

```text
Aufgabe: R5.7 — Die zwei grossen Editor-Felder stabilisieren/erweitern.

Felder: VC.BUSINESS_TARGETS_MODEL.EDITOR, SOL.INNOVATION_SOLUTION.EDITOR (Limits aus Registry).

Value Creation: Business Model, Customer Pain, USP, Markt, Wettbewerb, Revenue/Go-to-Market nur belegt oder als offene Angabe markiert; keine Marktgrössen/CAGR/NPV erfinden.
Solution: SOTA, Novelty, KPIs, Vorarbeiten, Partner-Eignung strukturieren; KPI ohne Baseline als offene Angabe markieren.

Tests: fehlender Marktbeleg ⇒ missing_inputs; keine unbelegten quantifizierten Claims (Fixture); Injection-Suite; Limits.
```

## Prompt R5.8 — Platzhalter-Aktionsmenü

```text
Aufgabe: R5.8 — Platzhalter nicht nur markieren, sondern auflösbar machen.

Dateien: components/editor/ (Platzhalter-Rendering/Menü), backend/app/api/ (kleine Ergänzung "Frage an Nutzer" als OpenIssue), Tests.

Menü je Platzhalter: "Fehlende Info aus Quellen suchen" (öffnet Quellen-/Belegpanel mit Feldfilter) · "KI-Vorschlag für diese Stelle" (nur wenn availability erlaubt, sonst Reason-CTA aus R4.2) · "Kurze Frage an mich stellen" (erzeugt OpenIssue mit Feldbezug) · "Als offen markieren" · "Nicht relevant — Begründung" (persistiert Begründung, Platzhalter-Finding wird resolved mit Nachweis).

Nicht tun: keine Auto-Auflösung, keine neuen Findings-Typen.

Tests: Component-Test je Aktion; "nicht relevant" reduziert Blocker-Zahl konsistent im kanonischen Status.
```

---

# R6 — Evidence-Statusleiter, Copy-Readiness, Rubric v0

## Prompt R6.1 — EvidenceStatus (tests first)

```text
Aufgabe: R6.1 — EvidenceStatus-Enum und reine Ableitungsfunktion mit vollständiger Kombinationsmatrix. Keine UI.

Statusleiter: not_required, evidence_missing, location_found, supports_partially, supports_strongly, conflict_or_uncertain, human_review_required.

Input: requires_evidence, anchor_status, sufficiency_status, human_review_status, conflict_flag (bestehende Werte aus reliability/ nutzen, keine neuen Quellzustände erfinden).

Tests (zuerst): vollständige Matrix; exact location ohne Sufficiency-Support ⇒ location_found, nie supports_strongly; conflict schlägt support; human_review korrekt.
```

## Prompt R6.2 — Evidence-Microcopy und Claim-Panel

```text
Aufgabe: R6.2 — Coverage und Correctness in der UI trennen.

Dateien: components/quellen/, components/editor/ (Belege-Panel), components/review/.

Anforderungen: "Fundstelle bestätigt" → "Textstelle gefunden — fachliche Prüfung offen"; "belegt" nur bei supports_partially/strongly mit entsprechendem Label; jede Belegkarte zeigt das Statusleiter-Label; Claim-Klick zeigt rechts Quelle, Fundstelle, gestützte Teilaussage, Schwäche, empfohlene nächste Aktion (Daten aus bestehenden Anchors/Sufficiency, nichts Neues berechnen).

Tests: Component-Test location_found (kein grünes "belegt"); grep/Snapshot gegen alte Microcopy.
```

## Prompt R6.3 — Copy-Readiness-Stufen (Backend-Ableitung, FE-Rendering)

```text
Aufgabe: R6.3 — Copy-Readiness je Feld: Ableitung NUR im Backend, Frontend rendert.

Stufen: copy_ready, draft, placeholders_open, not_reviewed, blocker.

Dateien: backend/app/review/ oder api/fields.py (Ableitung aus kanonischem Status + Feldzustand), components/export/, Tests.

Verhalten: copy_ready normal · draft kopierbar mit Markierung · placeholders_open Warnung + Bestätigung · not_reviewed Warnung + Audit-Hinweis · blocker kein "Fertig"-Export, Arbeitskopie mit Bestätigung erlaubt. Copy bleibt fail-open (bestehendes Verhalten); der Disclaimer dazu kommt in R9.5.

Tests: Backend-Ableitungsmatrix; Component-Matrix Status×Verhalten; Konsistenz mit kanonischem Status (Paritätstest bleibt grün).
```

## Prompt R6.4 — Reviewer-Rubric v0 (deterministisch)

```text
Aufgabe: R6.4 — Drei deterministische Reviewer-Risiko-Heuristiken. Kein LLM.

Voraussetzung: Owner-freigegebene Meldungstexte mit Kriterienquelle im Message-Katalog. Ohne Texte stoppen.

Dateien: neu backend/app/review/rubric.py (checks.py nur Aufruf), Tests; bestehende Lexika aus reliability/extract.py wiederverwenden.

Heuristiken: (1) Baseline Absence — quantifiziertes Ziel ohne Ausgangswert/Messmethode im Feld; (2) SOTA-Differenzierung fehlt — Innovations-/Novelty-Claim ohne Vergleichsbezug; (3) KPI ohne Messmethode.

Regeln: severity_class reviewer_risk, nie Blocker; immer "menschliche Prüfung empfohlen"; Texte + Kriterienquelle/last_checked aus Katalog/Registry; Fingerprint wie R2; je Heuristik ein Feature-Flag; erwartete False-Positives am Goldfall dokumentieren (docs/evaluation/).

Tests: Positiv-/Negativ-Fixtures je Heuristik; kein Blocker-Status; Idempotenz-Regression bleibt grün.
```

---

# R7 — Budget/Partner/Attachments/Intake

## Prompt R7.1 — Budget-Rechner (tests first)

```text
Aufgabe: R7.1 — Deterministischer Budget-Rechner als reiner Backend-Service. Keine UI, kein LLM.

Voraussetzung: Datenmodell-Review des Owners für BudgetItem/Aggregat-Regel liegt vor, falls neue Tabellen nötig; für den reinen Rechner auf bestehenden Feldern nicht erforderlich.

Dateien: neu backend/app/budget/calculator.py, Tests; rules/inputs.py nur für gemeinsamen Kern.

WICHTIG: Schwellwerte (Umsetzungspartner-Anteil, Cash-Minimum) NICHT hardcoden — sie stehen im Contract und werden von den Rule-Handlern aus rule.condition gelesen. Der Rechner nutzt denselben Kern oder dieselbe Contract-Quelle. Referenzwerte: 40–60 % Beitrag, Cash ≥ 5 % (Contract: "Cash contribution ≥ 5%").

Input: direct_project_costs_without_overhead, implementation_partner_own_contribution, implementation_partner_cash_contribution, requested_funding.
Output: implementation_contribution_total/-_percent, cash_contribution_percent, funding_percent, blockers/warnings (ausserhalb Bereich, Cash unter Minimum, Nenner fehlt/0 ⇒ "Angabe fehlt", nie geratenes pass/fail).

Tests (zuerst): Grenzwerte exakt an den Contract-Schwellen; None/0-Fälle; PARITÄTSTEST gegen bestehende Rule-Handler mit identischen Fixtures; Architektur-Test: kein Import aus agents/ im Budget-Modul.
```

## Prompt R7.2 — Budget-Live-Anzeige

```text
Aufgabe: R7.2 — Rechner-Ergebnisse live im Partner-&-Budget-Screen.

Dateien: components/partner/budget-form.tsx, kleiner API-Endpoint.

Anforderungen: Umsetzungsbeitrag %, Cash %, Fördersumme sichtbar; Warnungen mit Regelquelle/last_checked (aus R2.7-Metadaten, falls gepflegt); Berechnung nur im Backend, FE zeigt an; fehlende Eingaben ⇒ "Angabe fehlt", kein rotes Falsch-Urteil.

Tests: Component-Test grün/gelb/rot/fehlend.
```

## Prompt R7.3 — Attachment-Readiness-Gates

```text
Aufgabe: R7.3 — Attachments als gleichwertige Readiness-Punkte.

Regeln AUS DEM CONTRACT/der Matrix lesen (Referenz: Business Plan PDF ≤10 MB ≤3; IPR ≤5 MB ≤5; Publications ≤5 MB ≤5; Risk Doc ≤5 MB ≤1; Cover Letter/LOI ≤5 MB ≤1). Bei Abweichung Contract vs. Referenz: Contract gewinnt, melden.

Dateien: backend/app/review/checks.py (neue Check-Gruppe), components/requirements/, components/export/, Tests.

Anforderungen: Status je Attachment missing/ok/wrong_type/too_large/too_many; Export-Readiness und Fix Queue berücksichtigen Attachments (severity export_blocker nur, wenn der Contract das Attachment als Pflicht führt — sonst reviewer_risk); existiert keine Upload-Infrastruktur für einen Typ, dann Readiness-Checkliste ohne neuen Upload-Bau.

Tests: Regeltests je Attachment-Typ; Fix-Queue-Einordnung.
```

## Prompt R7.4 — Intake-Entschlackung (falls nicht via R3' erledigt)

```text
Aufgabe: R7.4 — Doppelerfassung Partner/Budget im Intake entfernen.

Voraussetzung: R3 wurde gebaut (sonst hat R3' das bereits erledigt — dann Prompt überspringen). Owner-Migrationszuordnung Bestandsdaten liegt vor; ohne sie stoppen.

Inhalt identisch zu R3'-Punkt 2–3: Intake fragt nur Startpfad, Projektidee/Kontext ("Vertraulicher Projektkontext für KI-Agenten"), Förderprofil, Innovationsfeld, "Partner vorhanden/gesucht/unklar", optional grober Budgetrahmen. Details nur im Partner-&-Budget-Bereich.

Tests: Intake-E2E; keine Doppelerfassung erreichbar; Bestandsprojekte laden korrekt.
```

## Prompt R7.5 — PartnerFitEvidence-Minimum

```text
Aufgabe: R7.5 — Minimale strukturierte Partner-Fit-Nachweise. Keine Recherche, kein LLM.

Dateien: backend/app/db/models.py (+ additive Migration, Review), backend/app/api/partners.py, components/partner/, Tests.

Modell PartnerFitEvidence: partner_id, competence_area (Text), evidence_anchor_id (optional, bestehende Anchors), ch_value_note (optional), created_by.
UI: je Partner Abschnitt "Eignungsnachweise" mit Hinzufügen/Entfernen; Anzeige im Requirements-Kontext ("Partner-Fit: n Nachweise erfasst, menschliche Prüfung erforderlich") — HITL-Label immer.

Nicht tun: keine Bewertung/Scoring, keine Partnerrecherche (E-11 = nein), kein neues Finding als Blocker.

Tests: CRUD; Anchor-Verknüpfung; Migrations-Roundtrip.
```

Hinweis WP: Work-Package-Minimalstruktur nur bei E-04 = Ja — dann eigener Prompt nach R7.5 (nicht Teil dieses Packs).

---

# R8 — Market-Slice + Rubric v1 (Voraussetzung: E-05 entschieden)

## Prompt R8.1a — Leakage-Negativsuite ZUERST (Merge-Stopper)

```text
Aufgabe: R8.1a — Schreibe die Leakage-Suite VOR jeder Planner-Implementierung. Firewall bleibt unangetastet.

Dateien: backend/tests/ (test_privacy_firewall.py erweitern oder test_market_leakage.py neu), Fixtures.

Fälle: Rohidee-Sätze, Partnernamen (auch zusammengesetzt), Projektcodenamen, Budgetzahlen (Ziffern UND Zahlwörter), Canary-Marker, technische Detailbegriffe aus dem projektspezifischen Lexikon ⇒ dürfen in keiner ausgehenden Query erscheinen; D2 ohne Freigabe ⇒ blockiert; geänderte Query nach Freigabe ⇒ erneut freigabepflichtig (bestehende Tests wiederverwenden).

Diese Suite ist Merge-Stopper für alle R8-Prompts: rot = kein Merge, keine Ausnahme.
```

## Prompt R8.1b — Private Query Planner

```text
Aufgabe: R8.1b — Interner Query-Planner, der die Projektidee NUR lokal liest und Query-Vorschläge erzeugt.

Voraussetzung: R8.1a-Suite existiert und läuft.

Dateien: neu backend/app/market/query_planner.py, backend/app/market/service.py (Anbindung), Tests. search_query_firewall.py und policy_matrix.py NICHT ändern.

Anforderungen: Planner erzeugt 3–5 abstrahierte Query-Kandidaten je Zweck (Marktgrösse, Wettbewerber/Alternativen, Kundenproblem); jeder Kandidat läuft durch die bestehende Firewall; Output nur sanitisierte Kandidaten + Kategorie; Rohidee verlässt den Planner nicht (kein Logging, safe_detail); Planner ist deterministisch ODER nutzt LLM nur gemäss policy_matrix/ProviderPolicy — bei E-02=fake bleibt es der Fake-Pfad, ehrlich gelabelt.

Tests: Leakage-Suite grün; Kandidaten sind firewall-sanitisiert; keine Rohterme in Persistenz/Logs.
```

## Prompt R8.1c — Query-Freigabe-UI

```text
Aufgabe: R8.1c — Nutzer sieht und genehmigt jede Query vor Ausführung. Bestehenden Approval-Service wiederverwenden.

Dateien: components/quellen/public-research-panel.tsx bzw. components/editor/market-competition-panel.tsx, lib/api.ts.

Anforderungen: Liste der Kandidaten mit Zweck-Label; je Query Freigeben/Ablehnen/Bearbeiten (Bearbeiten ⇒ erneut Firewall + erneute Freigabe, bestehende Semantik); ohne Freigabe keine Ausführung; Panel erklärt in einem Satz, dass nie die Rohidee gesendet wird.

Tests: E2E Freigabe-Pflicht; Bearbeiten invalidiert Freigabe (bestehender Test deckt Backend, hier UI-Fluss).
```

## Prompt R8.2 — D0-Quellen + Market-Panel-Ergebnisse

```text
Aufgabe: R8.2 — Ergebnisse der freigegebenen Suchen als D0-Quellen mit Fragmenten; Market-Panel zeigt strukturierte Resultate statt "nicht verfügbar".

Dateien: backend/app/market/, backend/app/research/, components/editor/market-competition-panel.tsx, Tests.

Anforderungen: Ergebnisse (je E-05/E-02: echter Provider oder Fake, ehrlich gelabelt) als D0-SourceDocuments + Fragmente; Panel-Ausgabe: Marktgrössen-KANDIDATEN mit Fundstelle (nie als Fakt), Wettbewerber-/Alternativenliste mit Quellen, schwache Marktclaims markiert (bestehender Marktclaim-Check); Evidence-Anchor-Erzeugung nur nach Nutzer-Klick; jede Zahl trägt Quelle+Statusleiter-Label; keine automatische Feldtext-Erzeugung.

Tests: Fake-Provider-E2E; Anchor nur nach Klick; Leakage-Suite grün; Panel ohne Ergebnisse zeigt geführten Ablauf statt Sackgasse.
```

## Prompt R8.3 — Rubric v1

```text
Aufgabe: R8.3 — Rubric erweitern. Nur Heuristiken mit belegbarer Kriterienquelle; Texte aus Owner-Katalog.

Kandidaten (nur umsetzen, was der Katalog freigibt): Marktgrösse ohne Quelle im Feldtext (Verzahnung mit bestehendem Marktclaim-Check statt Duplikat), Use-Case↔Methodik-Bruch (nur wenn deterministisch prüfbar, sonst weglassen), Risiko-Abschnitt fehlt/zu eng (nur als reviewer_risk-Hinweis auf Basis Contract-Anforderung).

Regeln wie R6.4: reviewer_risk, nie Blocker, HITL-Label, Flags je Heuristik, False-Positive-Doku am Goldfall.

Tests: Fixtures je Heuristik; keine Blocker; Idempotenz.
```

---

# R9 — Pre-Beta-Hardening & Abschluss

## Prompt R9.1 — No-Raw-Logging-Suite über alle Pfade

```text
Aufgabe: R9.1 — Erweitere die No-Raw-Logging-Tests auf alle sensitiven Pfade (Import ist seit R3.4 abgedeckt; hier: A2-Redraft, Runs/Fehlerpfade, Source-Ingestion, Audit gesamt).

Marker-Fixtures: PROJECT_SECRET_MARKER_123, PARTNER_CONFIDENTIAL_NAME, CHF_999999_SECRET_BUDGET.

Anforderung: Marker erscheinen nicht in Logs, Audit-Payloads, Operation-/Exception-Texten; redigierte Metadaten erlaubt. Vorgehen: failing tests zuerst, dann minimale Fixes (safe_detail nutzen); redaction.py nur bei nachgewiesener Lücke minimal ergänzen, mit Begründung.

Akzeptanz: Suite in verify_all; alle Pfade grün.
```

## Prompt R9.2 — Rollen-Endpoint-Matrix + 403-Tests

```text
Aufgabe: R9.2 — Verifiziere die Zugriffskontrolle statt sie anzunehmen.

Dateien: docs/security/roles-endpoint-matrix.md, backend/tests/.

Anforderungen: Tabelle aller Endpoints × Rolle × erwartetes Verhalten (aus openapi/x-required-roles und require_roles-Nutzung ableiten — dokumentieren, nicht erweitern); Tests: fremder Workspace ⇒ 403/404, fehlende Rolle ⇒ 403, unauthentifiziert ⇒ 401 für eine repräsentative Abdeckung (mind. alle schreibenden Endpoints).

Nicht tun: keine neuen Rollen erfinden; Lücken dokumentieren, Fix nur nach Owner-Entscheid.

Akzeptanz: Matrix vollständig; Tests grün; offene Lücken als Liste im R9-Gate-Report.
```

## Prompt R9.3 — Reload-Guard bei ungespeicherten Änderungen

```text
Aufgabe: R9.3 — Projektwechsel (window.location.reload in components/shell/app-shell.tsx) prüft vorher auf ungespeicherte Änderungen.

Anforderungen: Dirty-State aus Editor/Formularen abfragen; Dialog "Ungespeicherte Änderungen — wechseln und verwerfen / abbrechen"; wo ohne Risiko möglich, gezielte State-Invalidierung statt Hard-Reload — sonst Reload beibehalten (Kommentar-Begründung im Code respektieren).

Tests: E2E dirty ⇒ Dialog; clean ⇒ direkter Wechsel.
```

## Prompt R9.4 — Disclaimer-Katalog kanonisch

```text
Aufgabe: R9.4 — Ein Katalog, alle Stellen referenzieren ihn.

Voraussetzung: Owner-freigegebene Texte. Pflichtaussagen: keine Einreichung durch die App · keine Aussage zur Förderwahrscheinlichkeit · Fundstelle ≠ fachliche Freigabe (Coverage ≠ Correctness) · Kopieren wird protokolliert, aber technisch nicht verhindert (fail-open) · Portalregeln mit Stand/last_checked.

Dateien: lib/disclaimers.ts (Konstanten), betroffene Komponenten, grep-Tests gegen Alt-Wortlaute.

Tests: jede Pflichtaussage an definierter Stelle sichtbar; keine Duplikat-Formulierungen ausserhalb des Katalogs.
```

## Prompt R9.5 — Performance-Smoke

```text
Aufgabe: R9.5 — Messen statt vermuten.

Dateien: scripts/perf_smoke.*, docs/evaluation/perf-report.md; Grossfixture synthetisch (100+-Seiten-PDF, viele Fragmente, 25'000-Zeichen-Editorfeld) gemäss Testdaten-Policy.

Messen: Upload/Parse-Dauer, Analyse-Run-Dauer, Statusabruf, Editor-Interaktionslatenz (grob). Report mit Zahlen; harte Ausreisser als Issues notieren, NICHT in diesem Prompt fixen.
```

## Prompt R9.6 — A11y-Basisprüfung

```text
Aufgabe: R9.6 — A11y-Lint + Kurzcheck der Kernflüsse (Intake, Fix Queue, Editor, Kopieransicht).

Anforderungen: Lint (z. B. eslint-plugin-jsx-a11y) aktivieren, Befunde dokumentieren; Tastaturfallen und fehlende Labels in Kernflüssen beheben; Farbinformation stets mit Textlabel (Statussprache-Katalog nutzen). Grössere Umbauten nur dokumentieren.

Akzeptanz: Lint in CI; Kurzcheck-Protokoll in docs/.
```

## Prompt R9.7 — Security-Gate-Checkliste ausführen (human-led)

```text
Aufgabe: R9.7 — Arbeite die Beta-Gate-Checkliste ab; jedes Item braucht Testnachweis oder Messwert, kein Freitext-Abhaken.

Quelle: docs/repair/evaluation-and-beta-gates.md (Gate B1) + docs/security/privacy-ai-security-todos.md.

Items (Auszug): cookie_secure/TLS-Profil dokumentiert + getestet · Postgres-Option Smoke (NACH letzter Schema-Migration) · Browser-Storage-Tests grün (R4.4) · No-Raw-Log-Suite grün (R9.1) · Rollen-Matrix (R9.2) · Tool-Allowlist-Nachweis je AgentProfile (dokumentieren aus Registry) · Secrets-Handling dokumentiert · Testdaten-CI-Check grün.

Output: docs/security/beta-gate-report.md mit Status je Item + Nachweis-Link. Owner entscheidet Freigabe (E-13) — nicht Claude Code.
```

## Prompt R9.8 — Finale Evaluation + Abschlussbericht (human-led, Skript-Support)

```text
Aufgabe: R9.8 — Auswertungsskripte und Berichtsgerüst für die finale Evaluation. Goldstandard-Urteile und F3-Anonymisierung macht der Owner.

Dateien: backend/app/evaluation/ (Runner vervollständigen), docs/evaluation/final-report.md (Gerüst).

Anforderungen: Runner misst die Metriken aus docs/repair/evaluation-and-beta-gates.md auf F1/F2(/F3) im Fake- bzw. gemäss E-02 erlaubten Modus; Vergleich gegen Baseline (R0.3); Provider-Modus je Lauf ehrlich ausweisen; Cost/Latency aus UsageRecord aggregieren.

Akzeptanz: Runner reproduzierbar; Bericht enthält Baseline-Vergleich, Limitationen-Abschnitt, keine erfundenen Zielwerte.
```

## Prompt R9.9 (optional) — Agent-Trace-Ansicht

```text
Aufgabe: R9.9 — Read-only-Ansicht je Run: Stufen, Agentenbeiträge (A1/A2/Market), Gates, HITL-Entscheide, Dauer/Aufrufe — aus vorhandenen AgentInvocation/ToolInvocation/Audit-Daten. Keine neuen Agentenlogiken, keine Rohinhalte (nur Metadaten/Hashes).

Nutzen: Demo + Thesis-Beleg des Multi-Agent-Workflows.

Tests: Component-Test mit Fixture-Run; kein Klartext aus Quellen/Drafts in der Ansicht.
```
