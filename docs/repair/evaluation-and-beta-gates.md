# Evaluation & Beta-Gates

## 1. Evaluations-Harness (ab R0, Dauerbetrieb)

**Zweck:** Jede Roadmap-Änderung wird messbar; die Thesis erhält Vorher/Nachher-Belege statt Behauptungen.

**Aufbau (R0):** `backend/app/evaluation/` (Runner, Metrik-Implementierungen), `docs/evaluation/` (Fälle, Goldstandards, Berichte), CI-Smoke im Fake-Provider-Modus. Fälle gemäss Testdaten-Policy E-12 — Rohdaten nie im Repo.

**Fälle:**
- F1 (R0): synthetischer, realistischer Innosuisse-Fall mit Gold-Feldmapping und Gold-Findings.
- F2 (bis R6): absichtlich schwacher Fall (fehlende Baselines, unbelegte Marktclaims, Budget ausserhalb Quoten) — testet, ob die App die richtigen Risiken meldet.
- F3 (R9, abhängig von E-08): echter anonymisierter Innolink-Antrag. Ohne F3 bleibt der Wirkungsclaim Hypothese (Limitation).

**Baseline-Messung (R0/R1, einmalig):** Ist-Zustand auf F1 dokumentieren (Rohfinding-Zahl, fehlende Gruppierung, Statusdivergenz, manuelle Schritte bis exportfähiger Feldsatz). Das ist der Vergleichspunkt für alles Weitere.

## 2. Metriken (operationalisiert)

| Metrik | Definition | Quelle | Ziel/Verwendung |
|---|---|---|---|
| Finding Precision | korrekte Findings / alle gemeldeten Findings (gegen Gold, je Fall) | Harness-Vergleich | Rubric-/Regel-Qualität; keine feste Zielzahl vorab erfinden — Baseline dokumentieren, Verbesserung zeigen |
| Finding Recall | gefundene Gold-Findings / alle Gold-Findings | Harness | Ablehnungsrisiken-Sichtbarkeit (Kern-Wirkungsclaim) |
| Evidence-Sufficiency-Agreement | Übereinstimmung Sufficiency-Status vs. Expertenurteil auf Claim-Stichprobe | human-annotierte Stichprobe (F1/F3) | Ehrlichkeit von «stützt/teilweise/nicht» |
| Import Field Mapping Accuracy | korrekt gemappte Felder / 8 (sicher vs. uncertain getrennt ausweisen) | Fixtures + Gate-PDF | E-01-Gate (≥ ~60 % [Doc: Spike]) und R3-Regression |
| Copy-Paste-Readiness-Rate | Felder mit Status «kopierbereit» nach definiertem Bearbeitungsskript / aktive Felder | E2E-Skript je Fall | Fortschritt des Kernnutzens |
| Manual Effort (Proxy) | Zeit + Interaktionsschritte bis: (a) Fix Queue leer von Blockern, (b) exportfähiger Feldsatz; identisches Skript vor/nach Milestones | stoppuhr-/schrittbasiertes Protokoll | Aufwandsreduktions-Beleg (B-Frage der Schlussprüfung) |
| Rework Count | Anzahl Nutzerkorrekturen an übernommenen KI-Vorschlägen/Import-Feldern bis Freigabe | Draft-Versionshistorie [Code: DraftVersion] | Qualität statt nur Menge |
| Cost/Latency | Aufrufe, Tokens, Dauer je Run/Vorschlag | UsageRecord/AgentInvocation [Code] | Betriebs-Doku (Stufe-2-DoD 21/«Runtimes dokumentiert») |
| Finding-Dedupe-Wirkung | Gruppenzahl vs. Rohfindings auf F1 | Harness | R2-Nachweis |
| Leakage-Rate | sensible Marker in ausgehenden Queries/Logs (muss 0 sein) | Negativsuiten | hartes Gate, keine Metrik zum «Verbessern» |

Regeln: Metrikdefinitionen liegen VOR den Ergebnissen fest (dieses Dokument); keine Zielwerte erfinden, wo keine Basis existiert — Baseline + Delta berichten; Fake-Provider-Ergebnisse immer als solche kennzeichnen; «70–80 % Automatisierung» wird nicht als KPI verwendet.

## 3. Evaluation-Leakage-Schutz

- Goldstandards und Fälle enthalten keine echten vertraulichen Daten (E-12); F3 nur nach dokumentierter Anonymisierung + Review.
- Prompts/Heuristiken werden nicht auf die Goldfälle hin optimiert und dann an denselben Fällen «bewiesen»: F2 bleibt bis R6 unter Verschluss der Entwicklung (Holdout), F3 wird erst in R9 erstmalig ausgewertet.
- CI-Check auf bekannte sensible Marker der Beispielprojekte in Fixtures.

## 4. Milestone-Messpunkte

| Milestone | Pflichtmessung |
|---|---|
| R0/R1 | Baseline auf F1 (inkl. Statusdivergenz-Nachweis vor Fix) |
| R2 | Dedupe-Wirkung; Finding Precision/Recall F1 |
| R3 | Mapping Accuracy (Fixtures + Gate-PDF); Manual-Effort-Delta Einstieg |
| R5 | Rework Count + Annahmequote KI-Vorschläge F1 (Provider gemäss E-02, gelabelt); Injection-Suite |
| R6 | Sufficiency-Agreement-Stichprobe; Readiness-Rate F1 |
| R7 | Budget-Goldwerte; Readiness-Rate inkl. Attachments |
| R8 | Leakage 0; Quellen-Trefferqualität am F1-Marktteil (deskriptiv) |
| R9 | Vollauswertung F1+F2(+F3); Cost/Latency; Abschlussbericht |

## 5. Beta-Gates

### Gate B1 — Beta mit synthetischen/anonymisierten Daten (nach R9)
Bestanden, wenn: DoD-Stufe 2 (Punkte 15–21) vollständig mit Testnachweisen; Vollauswertung F1+F2 liegt vor; alle Dauer-Merge-Gates grün auf dem Release-Stand; E-07-Betreuungsmodell unterschrieben; Owner-Freigabe (E-13) dokumentiert.

### Gate B2 — Beta mit echten D2-Daten
Zusätzlich: E-02 dokumentiert (kein Consumer-API-Pfad für D2, Konfigtest); No-Raw-Logging-, Leakage-, Injection-, Rollen-Suiten grün auf Produktionskonfiguration; D2/D3-Browser-Cache deaktiviert (Test); Lösch-/Backup-Konzept dokumentiert; Nutzerinstruktion (Speicherung, Zwischenablage, keine Einreichung) liegt vor; F3 ausgewertet oder Verzicht mit Begründung dokumentiert.

### Gate-Disziplin
Ein rotes Gate-Item = keine Freigabe. Ausnahmen existieren nicht als stilles Weiterarbeiten, sondern nur als dokumentierter Owner-Entscheid mit Risikoabschätzung im Gate-Report.
