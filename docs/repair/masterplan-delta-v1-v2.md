# Masterplan Delta v1 → v2

Nur Änderungen. Unveränderte Teile von v1 gelten weiter.

## 1. Struktur-Änderungen

| # | Änderung | v1 | v2 | Begründung |
|---|---|---|---|---|
| D-01 | Neue Gate-Phase R0 | Entscheide «vorab» erwähnt, ohne Ort/Termin | R0: PDF-Gate, Provider-Policy, Beta-Scope, Testdaten-Policy, Eval-Harness v0, Git-Tag | Drei menschliche Entscheide blockierten sonst R3/R4/R7 mitten in der Umsetzung |
| D-02 | Evaluation vorgezogen | Evaluationsset erst R8 | Harness + 1 synthetischer Goldfall ab R0; jeder Milestone misst dagegen; finale Auswertung R9 | v1-Logikfehler: Tickets referenzierten ein Evaluationsset, das erst am Ende existierte |
| D-03 | Import vorgezogen (bedingt) | Gate + Implementierung in R7 | Gate in R0; Implementierung als R3, direkt nach Issue-Modell | Grösster Aufwandshebel; braucht nur R1/R2; deterministisch, providerfrei, HITL-gesichert |
| D-04 | Import-Fallback definiert | fehlte | R3' bei negativem Gate: «Aus Notizen/Quellen starten»-Flow + Intake-Entschlackung vorziehen | Aufwandsreduktion darf nicht am PDF-Format scheitern |
| D-05 | R6 gesplittet | Budget+Partner+Attachments+Intake+WP in einem | R7a Budget deterministisch; R7b Attachments+Partner-Fit+Intake; WP nur nach Ja-Entscheid | Zwei Migrationen + FE-Umbau + offener Scope-Entscheid = zu gross, nicht rollbackbar |
| D-06 | R8 entlastet | Market+Rubric+Evaluation | R8 = Market-Slice + Rubric v1; Rubric v0 (3 Heuristiken) schon in R6; Evaluation in R0/R9 | Provider-Risiko von Market darf Rubric/Evaluation nicht mitreissen |
| D-07 | Security-Hardening als Pflicht-Gate | W-22 «Backlog, vor realer Beta» | R9 Pre-Beta-Hardening mit hartem Gate und Checkliste | Backlog-Status hätte die Beta an einem Nebensatz scheitern lassen |
| D-08 | Feldstufenmodell | «Erweiterungsliste liegt vor» (vage) | Stufe A=8 / B=+2 belegte Felder + Attachment-Gates + Readiness-Checkliste / C=Post-MVP nach Contract-Verifikation | Nur belegte Felder priorisieren; Erwartung «fast alle Felder» ehrlich umdefinieren |
| D-09 | UX-DoD-Katalog | UX-Punkte verstreut | Kanonischer UX-Zielzustand in final-definition-of-done.md | «Fertig» war UX-seitig nicht prüfbar |
| D-10 | DoD-Stufen | eine implizite Definition | 4 Stufen: Thesis-Demo / Beta synthetisch / Beta D2 / Post-MVP | Verschiedene Freigaben brauchen verschiedene Kriterien |
| D-11 | Status-Paritätstest als Dauer-Gate | einmaliger E2E in R1 | CI-Merge-Gate ab R1 für alle Folge-Milestones | Statusdrift ist Rückfall-Risiko Nr. 1 |
| D-12 | ProviderPolicy + AIProposal-Schema | fehlten als Modelle | ProviderPolicy-Konfig (R4), AIProposal-Schema gepinnt (R5) | Modell-Lücken aus Prüfpunkt K |
| D-13 | Agent-Trace-Ansicht (optional) | fehlte | R9 optional: Run-Trace mit Agentenbeiträgen, Gates, HITL-Punkten | Macht den Multi-Agent-Anspruch demonstrier- und verteidigbar, ohne neue Agentenlogik |
| D-14 | Weakness-Register erweitert | W-01–W-26 | +W-27–W-41 (siehe weakness-register-v2.md) | Lücken: Jobs-UX, Reload-Guard, Rollen-Audit, Logging-Scope, Injection-Tests, Kosten-Sicht, Performance, Sprache, A11y, IPR, Testdaten, Prompt-Regression, Disclaimer, ICT-Check, Integrity-Gates |
| D-15 | Ticket-Audit | 24 Tickets, teils zu gross | 6 gesplittet, 4 mit menschlicher Vorarbeit, 3 mit Tests-zuerst-Pflicht, 2 human-led; Do-not-touch-Listen + Merge-Gates | Copilot-Kontrollierbarkeit |

## 2. Milestone-Mapping v1 → v2

| v1 | v2 |
|---|---|
| — | R0 Gates & Fundament (neu) |
| R1 | R1 (unverändert + Dauer-Paritätsgate) |
| R2 | R2 (unverändert; T-2.6 human-geführt) |
| R7 Import | R3 (bedingt; Fallback R3') |
| R3 Datenklassen | R4 (+ ProviderPolicy-Doku) |
| R4 KI-Assist | R5 (+ Prompt-Regressionstests, Injection-Fixtures, AIProposal-Schema) |
| R5 Statusleiter | R6 (+ Rubric v0, Copy-Readiness) |
| R6 Budget/Partner | R7a + R7b (gesplittet; WP nur nach Entscheid) |
| R8 Market+Rubric+Eval | R8 Market + Rubric v1 (schmal) |
| Backlog W-22 | R9 Pre-Beta-Hardening & Abschluss (neu, Pflicht-Gate) |

## 3. Unverändert übernommen aus v1

Kernsequenz Status → Issues → Datenklassen → KI; alle v1-Invarianten (finding_code nie umformatieren, Firewall read-only, keine Auto-Übernahme, Budget deterministisch, Coverage ≠ Correctness, kein Webresearch mit Rohidee, additive Migrationen); Weakness-Register W-01–W-26 inhaltlich (Status-Updates in weakness-register-v2.md); Wirkungslogik-Mapping auf Innosuisse-Ablehnungsrisiken; Anhang-B-Korrekturen.
