# Masterplan-Review v2

Stand: 06.07.2026 · Geprüft: Masterplan v1 (W-01–W-26, R1–R8, 24 Tickets) gegen Code-Snapshot, Screenshots, Requirement Matrix, Kriterienbasis, Datenschutzunterlagen, Spike-Report.
Evidenzgrade: [Code] [UI] [Doc] [Inferenz] [Annahme].

---

## 1. Executive Verdict

Skala 1–10 (10 = sehr gut; bei den Risikodimensionen: 10 = geringes Risiko).

| Dimension | Note | Begründung (kurz) |
|---|---|---|
| Produktnutzen für Nutzer | 7 | Richtige Probleme, richtige Reihenfolge im Kern. Nutzenspitzen (Import, Market) liegen aber am Ende. |
| Reduktion manueller Arbeit | 5 | Bis R4 reduziert der Plan fast keinen Schreib-/Eingabeaufwand. Import erst R7, KI-Assist hängt am ungeklärten Provider-Entscheid. |
| Innolink-Feldarbeitsplatz-Reife | 6 | 8 Felder sauber, aber keine definierte Feldstufe 2 und keine Readiness-Checkliste für den nicht-textuellen Rest. |
| Technische Umsetzbarkeit | 8 | Baut auf vorhandenen Mustern auf (Registry, Findings-Idempotenz, availability, Parser) [Code]. Additive Migrationen. |
| Security/Privacy-Tauglichkeit | 7 | Prinzipien stark (Firewall read-only, Leakage-Suite, HITL). Aber W-22 als Backlog ist für supervised beta zu schwach; kein Pre-Beta-Gate. |
| Testbarkeit/Evaluation | 5 | Evaluations-Harness erst in R8. Änderungen aus R1–R7 sind damit nicht messbar; Vorher/Nachher-Vergleich geht verloren. |
| Bachelorarbeits-Tauglichkeit | 8 | Verteidigbare Gates (PDF-Nachtest), ehrliche Limitationen, DSR-kompatible Wirkungslogik. |
| Supervised-Beta-Tauglichkeit | 5 | Keine DoD-Stufen (Demo vs. Beta synthetisch vs. Beta D2), kein Hardening-Milestone, Rollen-/Logging-Nachweise ungeplant. |
| Risiko Scope Overreach (10 = gering) | 6 | R6 (Budget+Partner+Attachments+Intake+WP) und R8 (Market+Rubric+Evaluation) sind überladen. |
| Risiko falsche Priorisierung (10 = gering) | 6 | Kernsequenz R1→R2→R3→R4 ist richtig. Falsch platziert: drei menschliche Entscheide mitten in der Roadmap, Evaluation am Ende, Import-Gate erst bei R7. |

**Urteil: Plan akzeptieren mit Änderungen.** Kein Neuschnitt nötig — das Fundament (Status → Issues → Datenklassen → KI) ist korrekt und bleibt.

**Drei zwingende Änderungen:**

1. **R0 vorschalten (Gate- und Entscheidungsphase).** PDF-Gate-Test, Provider-Policy D2/D3, Beta-Scope-Entscheide und Testdaten-Policy blockieren sonst mitten in der Umsetzung (R3/R4/R7). Ein 30-Minuten-Test und drei Entscheide dürfen keine späten Milestones aufhalten.
2. **Evaluations-Harness ab R0 mitführen, nicht erst R8.** Ohne frühe Goldfälle und Metriken ist keine Änderung (Dedupe, Import, KI-Assist) messbar; die Thesis verliert den Vorher/Nachher-Beleg. R8 behält nur die finale Auswertung.
3. **R6 und R8 splitten, W-22 als eigenes Pre-Beta-Gate (R9) einplanen.** Sonst scheitert die Beta-Freigabe an einem «Backlog»-Punkt, und zwei überladene Milestones gefährden den Abschluss.

Stark empfohlen (bedingt, kein Zwang): **Import-MVP direkt hinter R2 ziehen**, falls das R0-Gate besteht. Begründung in Abschnitt 2 und 3A.

---

## 2. Masterplan-Logikprüfung R1–R8

| Milestone | Bewertung | Problem | Änderungsvorschlag | Begründung | Risiko falls nicht geändert |
|---|---|---|---|---|---|
| R1 kanonischer Status | Richtig, zuerst | Keines im Schnitt. Fehlend: Paritätstest als dauerhaftes Merge-Gate | Behalten; Status-Paritätstest ab R1 als CI-Gate für alle Folge-Milestones | Jede spätere Änderung schreibt in den Status; Regression muss automatisch auffallen | Statusdrift kehrt schleichend zurück |
| R2 Issue-Modell + Fix Queue | Richtig geschnitten | Registry-Metadaten (T-2.6) sind Datenpflege, kein Copilot-Code; Rubric gehört NICHT hinein (Scope) | Behalten; T-2.6 als menschlich geführte Datenaufgabe kennzeichnen | Metadaten-Inhalte (Quelle, last_checked) darf niemand erfinden | Copilot erfindet Quellenangaben — Integritätsrisiko |
| R3 Datenklassen vor R4 | Zwingend ja | `availability()` hängt an Policy-Matrix [Code: field_drafting, policy_matrix]. Aber: Import braucht R3 nicht | R3 bleibt vor KI-Assist. Import (deterministisch, kein Provider) darf VOR die Datenklassen rücken | Import nutzt nur lokale Parser + HITL [Code: ingestion, Spike]; keine externe Verarbeitung | KI-Assist auf ungeklärter Policy = untestbare Kombinatorik |
| R4 KI-Assist 8 Felder | Genug für Thesis, zu wenig für Beta-Eindruck | Keine definierte Stufe 2 | Feldstufen definieren: A = 8 (jetzt), B = +2 belegte Limit-Felder (INTRO.PREV.SYNERGY 10'000, INTRO.IP.FINDINGS 5'000 [Doc: Matrix Kap. 3]) + Attachment-Readiness; C = nur nach Contract-Verifikation | Nur diese zwei Zusatzfelder sind mit harten Limits belegt; mehr wäre erfunden | Erwartungslücke «fast alle Felder» bleibt unbeantwortet |
| R5 Evidence-Statusleiter | Richtig positioniert | Verpasst günstige Gelegenheit: Rubric-v0-Heuristiken nutzen dieselbe Codebasis (extract/checks) [Code] | Rubric v0 (3 deterministische Heuristiken, nur `reviewer_risk`, nie Blocker) an R5 anhängen | Kein neuer Agent, gleiche Dateien, hoher fachlicher Sichtwert | Reviewer-Perspektive fehlt bis R8 komplett |
| R6 Budget/Partner/Attachments/Intake/WP | Zu gross | 5 Themen, 2 Migrationen, 1 offener Scope-Entscheid (WP) in einem Milestone | Splitten: R6a Budget-Rechner + Kostenarten + Validator; R6b Attachments + Partner-Fit-Minimum + Intake-Entschlackung; WP nur nach Ja-Entscheid als eigener Slice | Migrationen (BudgetItem) und FE-Umbauten (Intake) sind getrennt rollbackbar | Ein halb fertiger Riesen-Milestone blockiert alles danach |
| R7 Import | Implementierung ok, Gate falsch platziert | Gate-Test (30 min) erst bei R7 = Entscheid zu spät; Nutzenhebel liegt brach | Gate nach R0; Implementierung direkt nach R2 (neu R3), da nur R1/R2 als Abhängigkeit | Grösste Schwäche ist Nutzeraufwand [Doc: Schwächenliste]; Import ist deterministisch, providerfrei, HITL-gesichert [Doc: Spike] | Der wichtigste Aufwandshebel wirkt erst am Roadmap-Ende — oder nie, wenn das Gate spät scheitert |
| R8 Market + Rubric + Evaluation | Dreifach überladen | Drei unabhängige Ergebnisse mit drei Risikoprofilen in einem Milestone | Evaluation nach R0 (Harness) + R9 (finale Auswertung) verschieben; Rubric v0 nach R5; R8 = Market-Slice + Rubric v1 | Market ist der einzige Teil mit externem Provider-Risiko; er darf nicht Evaluation und Rubric mitreissen | Scheitert Market am Provider, fällt auch die Thesis-Evaluation |

**Übersehene Abhängigkeiten in v1:**
1. Provider-Entscheid blockiert R3-Wirkung, R4, R8 — in v1 nur als «Entscheid vorab» erwähnt, ohne Termin. → R0.
2. Eval-Harness ist Voraussetzung für messbare AK in R2/R4/R7 («False-Positive-Rate am Evaluationsset» stand in v1-Tickets, das Set existiert aber erst R8). Logikfehler in v1. → R0.
3. Import erzeugt DraftVersions → invalidiert Scope-Hash → braucht sauberes Stale-Verhalten aus R1. Erfüllt, aber in v1 nicht benannt.
4. Testdaten-Policy (keine echten vertraulichen Daten in Fixtures) muss vor dem ersten Goldfall stehen, nicht als Ticket-Fussnote (v1 T-8.4).

**Zu grosse/riskante Milestones:** R6 und R8 (siehe Tabelle). Zu grosse Tickets: siehe copilot-ticket-audit-v2.md.

---

## 3. Schwächen des Masterplans (A–K)

**A. Import-First kommt zu spät — bestätigt.**
Der PDF-Gate-Test gehört vor R1 (R0): 30 Minuten Aufwand, entscheidet über den grössten Aufwandshebel [Doc: Spike-Report, Abbruchkriterium <~60 %]. Die Implementierung rückt auf Position 3 (nach R1/R2), weil sie nur Statuswahrheit und Issue-Modell braucht — nicht Datenklassen-Umbau, nicht Provider. Fällt das Gate negativ aus: Ersatz-Slice «Aus Notizen/Quellen starten» (bestehende Ingestion [Code]) + Intake-Entschlackung vorziehen. So oder so sinkt der Einstiegsaufwand früh.

**B. «Finalisierte robuste App» war nicht definiert — bestätigt.**
Vier DoD-Stufen jetzt definiert in `final-definition-of-done.md`: Thesis-Demo, Beta synthetisch/anonymisiert, Beta mit echten D2-Daten, Post-MVP. v1 vermischte diese Stufen (z. B. Security «vor realer Beta» ohne Gate).

**C. 8 Felder könnten zu wenig wirken — teilweise bestätigt.**
Feldstufenmodell eingeführt: **Stufe A** = 8 aktive Felder (Thesis-Pflicht). **Stufe B** (Beta) = +INTRO.PREV.SYNERGY, +INTRO.IP.FINDINGS (beide mit belegten Limits [Doc: Matrix]) + Attachment-Readiness-Gates + Readiness-Checkliste für nicht-textuelle Portalpunkte (Kontakte, Mentor, Scientific Integrity, Submit) als Status-Punkte statt Draft-Felder. **Stufe C** (Post-MVP) = weitere Felder erst nach Verifikation gegen den Contract (161 Felder [Doc/Code]) — keine Priorisierung erfundener Felder. Priorisierungslogik: Aramis-publiziert > hartes Zeichenlimit > Eligibility-Nähe > Textumfang. Wichtig: «Fast alle Felder vorbereiten» heisst für Beta ehrlich: alle Textfelder mit Limit als Draft, alles andere als geführte Checkliste. Diese Erwartungskorrektur gehört in Thesis und UI.

**D. Rubric zu spät — bestätigt, Lösung ohne neuen Agenten.**
Rubric v0 = 3 deterministische Heuristiken an R5 (neu R6): Baseline-Absence (quantifiziertes Ziel ohne Ausgangswert im Feld), fehlende SOTA-Abgrenzung (Innovationsclaim ohne Vergleichsterm — Lexikon existiert [Code: extract.py `_LEXICONS`]), KPI ohne Messmethode. Immer `reviewer_risk`, nie Blocker, immer «menschliche Prüfung»-Label. Marktclaim-Check existiert bereits [Code: gate.py]. Rubric v1 (breiter, ggf. LLM-gestützt) bleibt R8.

**E. R6 zu gross — bestätigt.** Split R6a/R6b wie in Abschnitt 2. WP-Minimalstruktur nur nach explizitem Ja (Entscheid E-04).

**F. Security als Backlog zu schwach — bestätigt.**
W-22 wird Pflicht-Milestone R9 (Pre-Beta-Gate) mit Checkliste: Secrets/Key-Handling, `cookie_secure`, Postgres-Option, sessionStorage-Cache für D2/D3 verifizieren/deaktivieren [Code: rich-editor-cache, `isRichCacheAllowed` vorhanden — Abdeckung prüfen], No-Raw-Logging-Scope erweitern (für Webresearch umgesetzt [Code: redaction.py M9J]; Ausdehnung auf A2-Kontexte, Import-Inhalte, Fehlerpfade unbelegt), Provider-Policy dokumentiert, Audit-Redaction-Tests, Rollen-Abdeckungs-Audit (require_roles existiert [Code: deps.py]; Endpoint-Abdeckung unverifiziert), Tool-Allowlist-Nachweis über Agent-Registry [Code: agents/registry.py — prüfen]. Vector-Store-Policy: aktueller Code enthält keinen Vector Store [Inferenz aus Struktursichtung]; Policy nur nötig, falls einer eingeführt wird — dann vorher.

**G. Evaluation zu spät — bestätigt.**
Harness ab R0: Ordnerstruktur, Metrikdefinitionen, 1 synthetischer Goldfall, CI-Smoke im Fake-Modus. Jeder Milestone ab R2 misst mindestens eine Kennzahl dagegen. Details und Gates: `evaluation-and-beta-gates.md`.

**H. Copilot-Tickets teils zu gross — bestätigt.**
6 Tickets werden gesplittet, 4 brauchen menschliche Vorarbeit, 3 brauchen Tests vor Implementation, 2 sind human-led. Vollständig: `copilot-ticket-audit-v2.md`.

**I. UX-Endzustand fehlte — bestätigt.**
v1 verteilte UX-Punkte, definierte aber keinen Zielzustand. Neu: UX-DoD-Katalog in `final-definition-of-done.md` (Startflow mit 3 Optionen, Fix Queue als Startpunkt der Arbeit, kein Empty State ohne CTA, kanonischer Statussprache-Katalog, keine generischen Labels, «nicht verfügbar» immer mit Grund+Ausweg, Screen-Redundanz-Audit). Verortung: R2 (Fix Queue), R5 (Empty States, Platzhalter), R6 (Statussprache), R9 (Politur, Reload-Guard, Labels).

**J. Multi-Agent-Anspruch — teilweise bestätigt, lösbar ohne Autonomie.**
Nach v2 belegbar: A1 Fact-Extraction + Evidence-Mapping (advisory) [Code: graph.py M9B/M9C], A2 On-Demand-Drafting mit Kontext-Tools [Code: field_drafting_context], Market-Query-Planner (R8), plus deterministische Gates und HITL-Punkte. Thesis-Argument: **orchestrierte, auditierbare Agenten mit Quality Gates — nicht Autonomie.** Belegbar über AgentInvocation/ToolInvocation/UsageRecord-Trail [Code] + Evaluation. Empfohlener kleiner Zusatz (risikofrei, R9 optional): «Agent-Trace-Ansicht» pro Run — zeigt Stufen, Agentenbeiträge, Gates, menschliche Entscheide. Stärkt Demo und Verteidigung ohne neue Agentenlogik.

**K. Datenmodell-Grenzen — Statusprüfung:**

| Modell | Status v1 | Nötig vor |
|---|---|---|
| Issue/Finding v2 | definiert (Fingerprint-Formel + severity_class) | R2 |
| EvidenceStatus | definiert (7 Stufen + Ableitungstabelle gefordert) | R6 |
| ImportCandidate | definiert (v1 §2.3.8) | R3 |
| BudgetItem | definiert, aber Aggregat-Ableitung (read-only sobald Items existieren) braucht Datenmodell-Review | R7a |
| PartnerFitEvidence | **unterdefiniert** — v1 nennt «Fit-Attribute mit optionalem Anchor»; Felder festlegen: competence_area, evidence_anchor_id, wp_ref?, ch_value_note | R7b |
| AttachmentRequirement | im Contract vorhanden [Doc]; Laufzeitmodell (Status je Regel) fehlt — definieren | R7b |
| WorkPackage minimal | nur skizziert; nur nach Ja-Entscheid ausdefinieren | E-04 |
| AIProposal/RedraftSuggestion | existiert als `AsyncOperation.result` [Code]; **Schema nicht gepinnt** — pinnen (suggestion_text, used_anchor_ids, profile_id, context_hash, model_ref) | R5 |
| ProviderPolicy | **fehlt als explizites Modell** — Tabelle: provider, erlaubte Datenklassen, Vertragsbasis, Regionen; als Konfig + Doku | R4 |
| AuditEvent | existiert [Code: repositories/audit] | — |
| Source/Fragment/EvidenceAnchor | existiert [Code] | — |
| CopyReadinessStatus | definiert (v1 T-5.3, 5 Stufen) | R6 |

---

## 4. Kritische Schlussprüfung (harte Antworten)

**A. Führt Roadmap v2 zu einer robusten, klaren, funktionierenden App?**
Ja — unter zwei Bedingungen: (1) die R0-Entscheide fallen wirklich (v. a. Provider-Policy; ohne sie bleibt der KI-Kern Fake-Provider-Demo), (2) Gate-Disziplin: rote Leakage-Suite, roter Paritätstest oder rotes R9-Gate stoppen den Merge bzw. die Beta. Der Plan selbst erzwingt beides jetzt strukturell.

**B. Reduziert sie den manuellen Aufwand stark genug?**
Teilweise, und das muss ehrlich gesagt werden. Stark nur, wenn Import-Gate besteht UND KI-Assist real wird — dann sinkt der Einstieg von «alles eingeben» auf «prüfen und korrigieren» plus «Vorschlag prüfen statt schreiben». Besteht das Gate nicht und bleibt der Provider ungeklärt, reduziert v2 primär Prüf-, Interpretations- und Suchaufwand (Fix Queue, Statusleiter, Rechner) — messbar, aber nicht das volle Versprechen. Genau dafür misst der Harness ab R0 «Manual Effort» als Kennzahl statt Behauptung.

**C. Echter Mehrwert gegenüber einem ChatGPT-Workflow?**
Ja, in vier Punkten, die ein Chat nicht liefert: (1) deterministische Eligibility-/Budget-/Limit-Gates mit Quellenstand und Auditierbarkeit; (2) Evidence-Anchors mit Sufficiency-Prüfung statt unbelegter Plausibilität — inklusive der ehrlichen Unterscheidung Coverage ≠ Correctness [Code: sufficiency.py]; (3) feldgenaue Innolink-Struktur mit Limits, Platzhaltern und Copy-Readiness; (4) Privacy-Architektur (Firewall, anonymisierte Queries, No-Raw-Logging) für vertrauliche Ideen. Diese vier sind deshalb Must-haves — fallen sie weg, ist die App tatsächlich nur ein umständlicheres ChatGPT.

**D. Für eine Bachelorarbeit realistisch abschliessbar?**
Ja, wenn der Backlog Backlog bleibt (WP voll, Risk Register, ICT/KI-Check, Partnerrecherche, Felder Stufe C) und R8 schmal bleibt. Grobe Grössen [Annahme, keine belastbare Aufwandsschätzung]: R0 klein; R1, R3, R4 mittel; R2, R5, R6, R7, R9 mittel bis gross; R8 gross. Härtester Terminhebel: R0-Entscheide in Woche 1. Fallback ist definiert: ohne Import-Gate und ohne Provider-Entscheid ist die Thesis mit R0–R2, R5(Fake-belegt als Limitation), R6, R9 + Evaluation immer noch verteidigbar — mit reduziertem Wirkungsclaim.

**E. Sicher genug für supervised beta?**
Erst nach bestandenem R9-Gate. Für Beta mit echten D2-Daten zusätzlich zwingend: dokumentierte Provider-Policy, No-Raw-Logging-Nachweis über alle Pfade (nicht nur Webresearch), Rollen-Audit, deaktivierter D2/D3-Browser-Cache, Betreuungsmodell (wer superviset, wie werden Vorfälle gemeldet). Gates in `evaluation-and-beta-gates.md`.

**F. Fünf Punkte, die die App scheitern lassen, wenn ignoriert:**
1. Provider-Entscheid wird nie getroffen → KI-Kern bleibt dauerhaft Demo; das Hauptversprechen fällt.
2. Statuswahrheit wird nicht konsequent durchgezogen (ein einziger neuer Sonderzähler genügt) → Vertrauensverlust kehrt zurück.
3. Leakage-/No-Raw-Logging-Tests fehlen oder werden bei Rot gemergt → Privacy-Bruch mit vertraulichen Projektideen; Beta-Killer.
4. Evaluation ohne echten (anonymisierten) Fall → Wirkungsaussage der Thesis bleibt unbelegt; Verteidigungsrisiko.
5. Scope-Creep (WP voll, Market breit, Felder Stufe C, Partnerrecherche) → nichts wird fertig; genau das v1-Risiko, das v2 mit Gates einhegt.

**G. Fünf Punkte mit dem grössten Nutzerwert pro Aufwand:**
1. Fix Queue + Finding-Dedupe (R2) — verwandelt Rauschen in Arbeitsliste; Backend-Felder existieren grösstenteils [Code].
2. Präzise Regel-/Partnermeldungen (T-2.5) — winziger Eingriff, beseitigt den sichtbarsten Vertrauensbruch.
3. Import-MVP (R3, falls Gate ok) — grösster Hebel gegen die Hauptschwäche Nutzeraufwand.
4. Empty-State-CTAs + Platzhalter-Aktionsmenü (R5) — beendet jede «nicht verfügbar»-Sackgasse.
5. Copy-Readiness-Stufen + Evidence-Statusleiter (R6) — macht den Kern-Output («geprüft kopieren») sichtbar und ehrlich.
