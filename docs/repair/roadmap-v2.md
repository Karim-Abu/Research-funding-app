# Roadmap v2 (R0–R9)

> **Status-Vorschlag (2026-07-07, zur Owner-Bestätigung):**
> **R0 abgeschlossen** (`repair-r0-done`) — Harness/Doku aus R0.1 lagen vor; ergänzt um
> R0.2 Gate-Report-Vorlage, R0.4 Marker-CI-Check, F1-Goldfall (Owner-approved) und
> R0.3-Baseline (`docs/evaluation/baseline-report.md`). Offen aus R0: Entscheide E-01
> (PDF-Gate-Testlauf mit lokalem PDF), E-02/E-12 formal; vier `docs/security/`-Vorlagen
> fehlen weiterhin.
> **R1 abgeschlossen** (`repair-r1-done`) — kanonischer Status-View (R1.2), alle vier
> Screens lesen ihn (R1.3), Status-Paritätstest als dauerhaftes Merge-Gate, CI-Guard
> gegen neue Legacy-Statuspfade (R1.4). Nachweis:
> `docs/milestones/Repair_R0_R1_Kanonischer_Status_Report.md`.
> **R2 abgeschlossen** (`repair-r2-done`) — Fingerprint + display_group_key (R2.1),
> additive Finding-v2-Migration (R2.2, Owner-Review vor Merge ausstehend), severity_class-
> Befüllung mit Idempotenz-Merge-Gate (R2.3), Fix-Queue-API (R2.4), UI hinter Flag
> `groupedFindings` (R2.5), Message-Katalog Owner-approved + verdrahtet (R2.6),
> Registry-Metadaten-Validierung (R2.7). Messbare Wirkung am F1-Goldfall: 72 offene
> Findings → 7 priorisierte Gruppen. Nachweis:
> `docs/milestones/Repair_R2_Issue_Modell_Dedupe_Fix_Queue_Report.md`.
> **Nächster Milestone-Kandidat:** R3 hängt an E-01 (PDF-Gate-Entscheid, Owner);
> ohne E-01 ist **R4.4 (Browser-Storage-Security-P0, keine Owner-Abhängigkeiten)**
> der empfohlene nächste Slice. R4.1–4.3 brauchen Owner-Tabelle/E-02.

Die vom Product Owner vorgeschlagene R0–R9-Struktur wird übernommen — mit drei begründeten Abweichungen:

1. **Import rückt von R7 auf R3.** Er braucht nur R1 (Statuswahrheit) und R2 (Issue-Modell), nicht Datenklassen-Umbau und keinen Provider [Code: ingestion/parsers.py, Spike deterministisch]. Er ist der grösste Hebel gegen die Hauptschwäche Nutzeraufwand. Datenklassen (neu R4) müssen nur vor KI-Assist liegen, nicht vor einem lokalen, deterministischen, HITL-gesicherten Import.
2. **Rubric v0 hängt an R6 (Statusleiter), nicht an R8.** Gleiche Codebasis (extract/checks [Code]), kein Agent, sofortiger Reviewer-Sichtwert.
3. **Evaluation ist kein Milestone-Inhalt von R8, sondern Dauerbetrieb ab R0** mit finaler Auswertung in R9.

Grössen [Annahme, keine belastbare Aufwandsschätzung]: S = Tage, M = 1–2 Wochen-Slices, L = mehrere Slices.

---

## R0 — Gates & Fundament (S)

- **Ziel:** Alle blockierenden Entscheide fallen; Messbarkeit existiert ab Tag 1.
- **Nutzerwert:** indirekt — verhindert, dass Nutzenhebel (Import, KI) später an offenen Entscheiden hängen.
- **Technische Änderung:** Git-Tag/Freeze `pre-repair-v2`; Eval-Harness-Skelett (`backend/app/evaluation/`, `docs/evaluation/`): Metrikdefinitionen, 1 synthetischer Goldfall (Feldmapping + erwartete Findings), CI-Smoke im Fake-Modus; PDF-Gate-Skriptlauf dokumentiert.
- **Dateien/Module:** `spike/map_pdf.py` (nur ausführen), `backend/app/evaluation/`, `docs/evaluation/`, `docs/repair/decision-log-needed.md` (Entscheide eintragen).
- **Nicht-Scope:** jede App-Code-Änderung ausser Harness; keine Fixes.
- **Abhängigkeiten:** echtes Innolink-PDF (beschaffen), Verfügbarkeit des Owners für Entscheide.
- **Akzeptanzkriterien:** (1) PDF-Gate-Ergebnis mit Quote dokumentiert, Entscheid bauen/streichen gefällt; (2) Provider-Policy-Entscheid schriftlich (auch «vorerst nur Fake/Local» ist ein gültiger Entscheid); (3) Beta-Scope-Entscheide E-01–E-10 beantwortet; (4) Testdaten-Policy schriftlich (keine echten vertraulichen Daten in Fixtures; Anonymisierungsregel); (5) Harness läuft in CI grün.
- **Tests:** Harness-Smoke (Fake-Provider).
- **Risiken:** Entscheide werden vertagt → gesamte Roadmap verschiebt sich. Gegenmassnahme: R1 startet parallel, aber R3–R5 starten nicht ohne die jeweiligen Entscheide.
- **Rollback:** entfällt (nur Doku + additiver Harness).
- **Definition of Done:** decision-log ausgefüllt, Harness in CI, Gate-Report abgelegt.
- **Entscheidungspunkt Mensch:** E-01 PDF-Gate, E-02 Provider, E-03 Feldstufe, E-04 WP, E-05 Websearch, E-08 Evaluationsdaten (siehe decision-log).
- **Copilot-Eignung:** Harness-Skelett ja; alles andere human-led.

## R1 — Kanonischer Status & Legacy-Mock-Abbau (M)

- **Ziel:** Eine Blocker-Zahl, überall; keine aktiven Mock-Datenquellen.
- **Nutzerwert:** Vertrauen — der sichtbarste Widerspruch (0/1/9/17 [UI]) verschwindet.
- **Technische Änderung:** ReviewPackage-Read-View als einziger Status-Endpoint; Dashboard/Anforderungen/Prüfung/Export lesen daraus; `isMock("legacy")`-Inventar + Entfernung aus aktiven Pfaden [Code: lib/api.ts, app-mode.ts]; einheitliches Stale-Verhalten.
- **Dateien:** `lib/api.ts`, `lib/app-mode.ts`, Dashboard-/Shell-Komponenten, `components/export/export-screen.tsx`, `components/review/quality-summary.tsx` (Datenquelle), `backend/app/review/package.py` (nur View), `backend/app/api/`.
- **Nicht-Scope:** neue Findings, neue Felder, UI-Redesign.
- **Abhängigkeiten:** keine.
- **Akzeptanzkriterien:** wie v1-R1; zusätzlich: Status-Paritätstest läuft als CI-Merge-Gate für alle Folge-Milestones.
- **Tests:** E2E Paritätstest (Blocker erzeugen/lösen → 4 Screens identisch); Unit View; Lint-Guard gegen neue legacy-Branches.
- **Risiken:** unentdeckte Screens am Mock; Gegenmassnahme: Inventar zuerst (T-1.1), Route-Prüfliste.
- **Rollback:** View additiv; FE-Hooks revertierbar; Deprecated-Props eine Version.
- **DoD:** 0/9/17-Widerspruch reproduzierbar behoben; Paritätstest im CI verankert.
- **Entscheidungspunkt Mensch:** keiner.
- **Copilot-Eignung:** ja (T-1.1–T-1.3), Merge nur mit grünem Paritätstest.

## R2 — Issue-Modell v2: Dedupe, Severity-Klassen, Fix Queue, präzise Meldungen (M–L)

- **Ziel:** Aus Befund-Rauschen wird eine priorisierte Arbeitsliste mit nächster Aktion.
- **Nutzerwert:** «Was tue ich als Nächstes?» wird beantwortet; Meldungsflut [UI: Screenshot 16] verschwindet; Partner-Blocker wird präzise.
- **Technische Änderung:** additive Finding-Spalten (fingerprint, severity_class, fix_recommendation, last_seen_at); Fingerprint-Modul; Gruppierungs-API + Fix Queue (Prio 1–6); UI-Gruppierung; entity-spezifische Regelmeldungen aus Message-Katalog; Registry-Pflichtmetadaten (source_ref, source_version, last_checked, validity_status) — Inhalte human-gepflegt.
- **Dateien:** `db/models.py` (+Migration), `reliability/gate.py`, `review/checks.py`, `review/package.py` bzw. `review/fix_queue.py`, `rules/handlers.py`, `rules/messages.py` (neu), `registry/loader.py`, Contract-YAMLs, `components/review/`, `components/requirements/`.
- **Nicht-Scope:** neue Prüfregeln, Rubric, LLM.
- **Abhängigkeiten:** R1 (Queue liest kanonischen Stand); R0-Harness (Messung Finding-Dedupe-Wirkung).
- **Akzeptanzkriterien:** wie v1-R2/W-02/W-03/W-20; zusätzlich: Harness misst Gruppenzahl vs. Rohfindings am Goldfall (Vorher/Nachher dokumentiert).
- **Tests:** Fingerprint-Determinismus; Idempotenz-Regression (finding_code unverändert, Row-Count stabil über 2 Runs); Gruppierungs-Snapshot; Handler-Tests je Entity/Zweig; Loader fail-closed.
- **Risiken:** Copilot «bereinigt» finding_code → Do-not-touch; Copilot erfindet Regeltexte/Quellen → Message-Katalog mit source_ref-Pflicht, menschliche Textfreigabe.
- **Rollback:** Spalten nullable; UI-Flag `groupedFindings`; Downgrade-Migration.
- **DoD:** Screenshot-16-Fall zeigt ≤ 6 Gruppen mit Aktion; «Kein passender Partner vorhanden» existiert nicht mehr (grep-Test).
- **Entscheidungspunkt Mensch:** Freigabe der Meldungstexte gegen Kriterienbasis; Registry-Metadaten-Inhalte.
- **Copilot-Eignung:** ja mit Splits (Ticket-Audit); T-2.6-Inhalte human.

## R3 — Import-First MVP (bedingt: nur bei bestandenem R0-Gate) (L)

- **Ziel:** Nutzer startet mit begonnenem Innolink-Antrag statt leeren Formularen.
- **Nutzerwert:** grösster Hebel — «prüfen und korrigieren» statt «alles neu eingeben» [Doc: Schwächenliste].
- **Technische Änderung:** Upload-Weg über bestehenden Parser (fail-closed übernehmen [Code: ingestion/parsers.py]); Mapping der 8 Stufe-A-Felder mit Zeilenverschmelzungs-Toleranz (Spike-Code portieren, diesmal mit Imports aus backend); ImportCandidate-Persistenz (field_id, extracted_text, confidence, source_span, decision); Import-Review-Tabelle (HITL; `uncertain` nie auto); Übernahme → DraftVersions, Rest → Quelle; Auto-Refresh Coverage/Fix-Queue; drei Startoptionen im Intake.
- **Dateien:** neues `backend/app/imports/`, `ingestion/`, `api/`, neue FE-Import-Review-Komponente, `components/intake/`.
- **Nicht-Scope:** LLM-Mapping; DOCX-Antragsimport (nur als Quelle); Felder > Stufe A; Partner-/Budget-Extraktion (erst nach stabilem Feld-Mapping, sonst Scope-Creep).
- **Abhängigkeiten:** R0-Gate bestanden; R1 (Stale-Verhalten), R2 (Issues/Coverage).
- **Akzeptanzkriterien:** v1-R7-AK 2–6; zusätzlich: Harness misst Import Field Mapping Accuracy am Goldfall + echtem Gate-PDF.
- **Tests:** Spike-Fixtures als Regression (sauber 8/8; degradiert kontrolliert `uncertain`); HITL-Zwang-E2E; Scope-Hash wird bei Übernahme korrekt stale.
- **Risiken:** echtes PDF-Verhalten variiert je Export; Gegenmassnahme: Gate-PDF wird Teil der Regressionsfixtures (anonymisiert gemäss Testdaten-Policy).
- **Rollback:** Feature-Flag `innolinkImport`; Intake ohne Upload-Option.
- **DoD:** Upload → Review → Übernahme → aktualisierte Lückenliste, durchgängig demonstrierbar.
- **Entscheidungspunkt Mensch:** Freigabe des anonymisierten Gate-PDFs als Fixture.
- **Copilot-Eignung:** ja, in drei Splits (BE-Mapping TDD / API / FE); Fixtures zuerst.

### R3' — Fallback bei negativem Gate (M)
«Aus Notizen/Quellen starten» stärken (bestehende Ingestion: PDF/DOCX/TXT [Code]) + Intake-Entschlackung (aus R7b vorziehen) + Startoptionen ohne Antrag-Upload. Entscheid und Begründung (Spike-Quote) in Thesis dokumentieren — sauber verteidigbar.

## R4 — Datenklassen v2 + Provider-Verdrahtung (M)

Inhaltlich = v1-R3, plus: ProviderPolicy als explizite Konfiguration + Doku (provider, erlaubte Datenklassen, Vertragsbasis/Region) gemäss R0-Entscheid E-02.
- **Nutzerwert:** reale (interne/vertrauliche) Projekte verlieren KI nicht mehr pauschal; jeder Block hat Grund + Ausweg.
- **Nicht-Scope:** echter Provider-Anschluss über den Entscheid hinaus; Market.
- **AK/Tests/Risiken/Rollback:** wie v1-R3 (Mapping-Property-Tests, Downgrade-Verbot-Regression, NDA-Gate-E2E) + ProviderPolicy-Konfigtest.
- **DoD:** Modi wählbar, Gründe lesbar, NDA blockt hart; Policy dokumentiert.
- **Entscheidungspunkt Mensch:** E-02 muss vorliegen; Migrationszuordnung Bestandsprojekte alt→neu.
- **Copilot-Eignung:** ja nach menschlicher Mapping-Tabelle (Architekturentscheid zuerst).

## R5 — KI-Assist produktiv für Stufe-A-Felder (L)

Inhaltlich = v1-R4, plus drei Ergänzungen:
1. **AIProposal-Schema pinnen** (suggestion_text, used_anchor_ids, profile_id, context_hash, model_ref) statt freies `operation.result`.
2. **Prompt-Regressionstests:** Snapshot je Prompt-Version (Dateien sind versioniert, `*_v1.md` [Code]); Änderung ⇒ bewusster Versions-Bump.
3. **Injection-Testsuite:** adversariale Fixtures (Anweisungen in Quelltexten/Quotes) → Vorschlag folgt ihnen nicht, referenziert weiter nur allowed_anchor_ids (Prompt-Härtung existiert [Code: prompts «untrusted data»]; Tests fehlen).
- **Nutzerwert:** echte, evidenzgebundene Vorschläge; Platzhalter aktiv auflösbar; keine Sackgassen-Empty-States.
- **Nicht-Scope:** Felder Stufe B (nur nach E-03), A3-Critic, Auto-Übernahme (verboten).
- **AK/Tests:** v1-R4-AK; plus Harness: Vorschlag-Annahmequote/Nachbearbeitungsaufwand am Goldfall dokumentiert (Fake- oder realer Provider je E-02, ehrlich gelabelt).
- **Risiken:** Provider-Entscheid = «nur Fake» ⇒ Nutzen bleibt Demo; dann in Thesis als Limitation, in UI als klarer Hinweis.
- **Rollback:** Profile einzeln deaktivierbar.
- **DoD:** alle 8 Felder liefern on-demand Vorschläge mit Belegbezug; jede Blockade nennt Grund + Ausweg.
- **Entscheidungspunkt Mensch:** keiner neu (E-02 aus R0).
- **Copilot-Eignung:** ja in 2-Feld-Splits; Injection-Fixtures human-kuratiert.

## R6 — Evidence-Statusleiter + Copy-Readiness + Rubric v0 (M–L)

Inhaltlich = v1-R5, plus Rubric v0 (3 deterministische Heuristiken: Baseline-Absence, fehlende SOTA-Abgrenzung, KPI ohne Messmethode; Severity `reviewer_risk`, nie Blocker, Kriterienquelle im Text, human-freigegebene Formulierungen).
- **Nutzerwert:** Coverage ≠ Correctness sichtbar; Kopieren wird geführt statt riskant; erste Reviewer-Perspektive.
- **Nicht-Scope:** semantische LLM-Belegprüfung; Rubric v1.
- **AK/Tests:** v1-R5-AK (7-Stufen-Enum, Kombinationsmatrix, Claim-Panel, Microcopy, Copy-Stufen) + Heuristik-Fixtures mit dokumentierter False-Positive-Erwartung am Goldfall.
- **Rollback:** Enum additiv; Heuristiken je Flag.
- **DoD:** jede Aussage zeigt eine Stufe; Kacheln summenlogisch erklärt; 3 Heuristiken aktiv.
- **Entscheidungspunkt Mensch:** Freigabe der Heuristik-Texte.
- **Copilot-Eignung:** ja; Ableitungstabelle als Tests zuerst.

## R7 — Budget/Partner/Attachments deterministisch (L, intern zweigeteilt)

**R7a Budget:** Kostenarten-Modell (BudgetItem) + Migration (Datenmodell-Review vor Umsetzung); Budget-Rechner-Service (eine Berechnungsquelle mit Regel-Handlern); Live-Anzeige; Kostenart-Validator mit Regelquelle + last_checked. Kein LLM im Budgetpfad (Architektur-Test).
**R7b Partner/Attachments/Intake:** Attachment-Readiness-Gruppe (Typ/Grösse/Anzahl aus Matrix [Doc]); PartnerFitEvidence-Minimum (competence_area, anchor, ch_value_note); Intake-Entschlackung (falls nicht in R3' geschehen) inkl. Migrationszuordnung; WP-Minimalstruktur **nur** bei E-04 = Ja als eigener Slice danach.
- **Nutzerwert:** Budget-Blocker sofort sichtbar statt spät; Attachments gleichwertig; ein Erfassungsort.
- **Nicht-Scope:** NPV, Partnerrecherche, Risk Register, MWST-/Abschreibungs-Vollmodell (nur Kostenart-Zulässigkeit gemäss dokumentierten Regeln [Doc: Kostenregeln]).
- **AK/Tests:** v1-R6-AK, aufgeteilt; Goldwerte inkl. Randfälle; Import-Graph-Test; Migrations-Roundtrips getrennt je Teilmilestone.
- **Risiken:** Aggregat-vs-Items-Doppelpflege; Regel: Aggregate read-only, sobald Items existieren (Review-Pflicht).
- **Rollback:** je Teilmilestone eigene Downgrade-Migration + Flags.
- **DoD:** Quoten live mit Regelquelle; fehlender Business Plan erscheint als Readiness-Punkt; keine Doppelerfassung.
- **Entscheidungspunkt Mensch:** E-04 (WP); Datenmodell-Review BudgetItem; Intake-Migrationszuordnung.
- **Copilot-Eignung:** Rechner/Validator ja (TDD); Migrationen nur mit menschlichem Review.

## R8 — Market-Slice privacy-konform + Rubric v1 (L)

Inhaltlich = v1-R8 ohne Evaluationsaufbau.
- **Nutzerwert:** geführte, freigabepflichtige Marktrecherche im wichtigsten Innosuisse-Kapitel; breitere Reviewer-Risiken.
- **Technische Änderung:** Private Query Planner (liest Rohidee nur intern) → bestehende Firewall (read-only, nur Tests ergänzen [Code]) → Query-Freigabe-UI (HITL) → Suche je E-05/E-02 (sonst Fake, ehrlich gelabelt) → D0-Quellen + Fragmente → internes Matching → strukturierter Output (Marktgrössen-Kandidaten mit Fundstelle, Wettbewerber-/Alternativenliste, schwache Claims markiert); Rubric v1 erweitert v0.
- **Nicht-Scope:** NPV-Szenarien, automatischer Feldtext, Partnerrecherche, LLM-Critic A3 (nur Schnittstelle).
- **AK/Tests:** v1-R8-AK; **Leakage-Negativsuite ist Merge-Stopper** (Rohidee/Partner/Budget erreichen nie eine ausgehende Query); Anchor-Erzeugung nur nach Klick.
- **Risiken:** Provider-/Suchqualität; Gegenmassnahme: Harness misst Quellen-Trefferqualität am Goldfall, Ergebnis ehrlich dokumentiert.
- **Rollback:** Planner-/Panel-Flags; Fallback «Quelle hinzufügen».
- **DoD:** Market-Panel zeigt statt «nicht verfügbar» einen geführten Ablauf; jede ausgehende Query wurde vom Nutzer gesehen und freigegeben.
- **Entscheidungspunkt Mensch:** jede Query (HITL by design); E-05 muss vorliegen.
- **Copilot-Eignung:** Planner nur mit Tests-zuerst (Leakage-Suite vor Implementation); Firewall do-not-touch.

## R9 — Pre-Beta-Hardening, finale Evaluation, Abschluss (M–L; hartes Gate)

- **Ziel:** Beta-Freigabe-Fähigkeit + Thesis-Abschlussartefakte.
- **Nutzerwert:** Sicherheit, Verlässlichkeit, letzte UX-Politur.
- **Technische Änderung:** Security-Checkliste abarbeiten (Secrets/Vault-Pfad, cookie_secure, Postgres-Option, D2/D3-sessionStorage verifiziert/deaktiviert, No-Raw-Logging-Scope auf A2-Kontexte/Import/Fehlerpfade ausgedehnt + Tests, Rollen-Endpoint-Audit, Tool-Allowlist-Nachweis, Audit-Redaction-Tests); Performance-Smoke (grosses PDF, viele Fragments — Messwerte dokumentieren); Reload-Guard bei ungespeicherten Änderungen [Code: app-shell.tsx:130]; A11y-Basisprüfung; Microcopy-/Label-Politur (Registry-Labels statt «Open Editor»); Disclaimer-Katalog kanonisch; finale Evaluation (3 Fälle inkl. echtem anonymisiertem, je E-08); Demo-Pfad + Doku; optional Agent-Trace-Ansicht.
- **Nicht-Scope:** neue Features, neue Felder, neue Agenten.
- **Abhängigkeiten:** alle vorherigen; E-06/E-07/E-08.
- **Akzeptanzkriterien:** Beta-Gate-Checkliste vollständig grün (evaluation-and-beta-gates.md); Evaluationsbericht mit Zahlen + Limitationen; DoD-Stufe «Beta synthetisch» erfüllt; für D2-Beta zusätzlich D2-Gate.
- **Tests:** No-Raw-Logging-Suite über alle Pfade; Rollen-Matrix-Tests; Performance-Smoke-Skript; A11y-Lint.
- **Risiken:** Checkliste wird «abgehakt» statt getestet; Gegenmassnahme: jedes Gate-Item braucht Testnachweis oder Messwert, kein Freitext.
- **Rollback:** entfällt (Härtung + Doku); Konfig-Änderungen dokumentiert reversibel.
- **DoD:** Gate-Report unterschrieben (Owner), Demo reproduzierbar per Skript, Thesis-Artefakte abgelegt.
- **Entscheidungspunkt Mensch:** E-06 Security-Level, E-07 Beta-Betreuungsmodell, Gate-Freigabe.
- **Copilot-Eignung:** einzelne Checks ja; Gate-Bewertung und Security-Review human.

---

## Reihenfolge-Begründung gegenüber dem Owner-Vorschlag

Owner-Vorschlag: R0, R1, R2, R3 Datenklassen, R4 KI, R5 Statusleiter, R6 Budget, R7 Import, R8 Market, R9 Hardening.
Übernommen bis auf einen Tausch: **Import (Owner-R7) ↔ Datenklassen/KI-Block (Owner-R3–R5).**
Gründe: (1) Import hat keine Abhängigkeit zu Datenklassen-UI oder Providern — er ist lokal, deterministisch, HITL-pflichtig [Code/Doc]; (2) er adressiert die als grösste benannte Schwäche (manueller Aufwand) und liefert damit den frühesten messbaren Nutzerwert; (3) das R0-Gate macht ihn planbar — bei negativem Gate greift R3' und die Reihenfolge entspricht wieder fast dem Owner-Vorschlag; (4) KI-Assist gewinnt durch importierte echte Feldtexte besseren Kontext (mehr Quellen, weniger Platzhalter) — die umgekehrte Reihenfolge hätte KI-Vorschläge zuerst auf leeren Templates demonstriert. Risiko des Tauschs: Import verschiebt KI-Nutzen um einen Milestone nach hinten; akzeptiert, weil der KI-Nutzen ohnehin am E-02-Entscheid hängt, nicht am Kalender.
