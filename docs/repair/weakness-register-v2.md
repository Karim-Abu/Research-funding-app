# Weakness Register v2

Teil 1: Status-Updates W-01–W-26 (Details bleiben in Masterplan v1 gültig).
Teil 2: Neue Schwächen W-27–W-41.

## Teil 1 — W-01–W-26: Zuordnung zu Roadmap v2

| ID | Kurztitel | Prio | v2-Verortung | Änderung ggü. v1 |
|---|---|---|---|---|
| W-01 | Kein kanonischer Prüfstatus | P0 | R1 | + Dauer-Paritätsgate im CI |
| W-02 | Kein dedupliziertes Issue-Modell / Fix Queue | P0 | R2 | + Harness-Messung Gruppen vs. Rohfindings |
| W-03 | Unscharfe Partner-Blocker-Meldung | P0 | R2 | Textfreigabe human (Merge-Gate) |
| W-04 | A2 deaktiviert / KI-Assist nicht nutzbar | P0 | R5 | Provider-Entscheid nach R0 (E-02) vorgezogen |
| W-05 | Vertraulichkeitsmodell zu grob | P0 | R4 | + ProviderPolicy-Modell |
| W-06 | Nur 8 Felder | P1 | E-03 + Stufe B in R5/R7b | Feldstufenmodell A/B/C statt vager Liste |
| W-07 | Import-First fehlt | P1 | Gate R0, Bau R3, Fallback R3' | Vorgezogen; bedingt |
| W-08 | Market nicht funktional | P1 | R8 | Unverändert spät — bewusst (Provider-Risiko isolieren) |
| W-09 | Coverage ≠ Correctness unsichtbar | P1 | R6 | Unverändert |
| W-10 | Keine nächste beste Aktion | P0 | R2 | Unverändert |
| W-11 | confirmed_facts irreführend | P1 | R5 (T-4.1) | Unverändert |
| W-12 | Partner-Fit flach | P1 | R7b (Minimum) | PartnerFitEvidence-Felder definiert |
| W-13 | Budgetmodell flach | P1 | R7a | Split; Datenmodell-Review Pflicht |
| W-14 | WP/Milestones fehlen | P1 | E-04; optionaler Slice nach R7b | Unverändert: nur Minimalvariante |
| W-15 | Risk Register fehlt | P2 | Backlog | Unverändert |
| W-16 | Attachments nicht gleichwertig | P1 | R7b | Unverändert |
| W-17 | Rubric fehlt | P1 | v0 in R6, v1 in R8 | Vorgezogen (v0) |
| W-18 | Doppelerfassung Intake | P1 | R7b (oder R3' vorgezogen) | Flexibilisiert |
| W-19 | UX-Redundanzen | P2 | R9 + UX-DoD | Jetzt prüfbar über Katalog |
| W-20 | Portal-Version-Drift | P1 | R2 (Metadaten), Prozess Backlog | Datenpflege human |
| W-21 | Legacy-Mock-Pfade | P0 | R1 | Unverändert |
| W-22 | Production-Security | P1→**P0 für Beta** | R9 Pflicht-Gate | Aufgewertet: Backlog → Gate |
| W-23 | Evaluation nur Fake | P1→**P0 für Thesis-Wirkung** | R0 Harness + R9 Auswertung | Aufgewertet und vorgezogen |
| W-24 | Microcopy/Labels | P2 | R6 (Statussprache) + R9 | Unverändert |
| W-25 | URL-Import fehlt | P2 | nach R4 einschiebbar / R8 | Unverändert |
| W-26 | Copy fail-open Governance | P2 | R6 (Stufen) + R9 (Disclaimer) | Unverändert |

## Teil 2 — Neue Schwächen

### W-27 — Async-Job-Zustände für Nutzer unvollständig
- **Beschreibung:** Backend ist fail-closed mit Startup-Recovery und ohne Auto-Resume; Operationen kennen queued/running/failed/timed_out [Code: runs/executor.py; agents/cost_guard.py]. Unklar/unbelegt: nutzerseitige Retry-Wege, Fortschrittsdetail je Stufe, verständliche Fehlermeldungen statt Fehlercodes.
- **Evidenzgrad:** Backend [Code]; FE-Lücke [Inferenz — Laufzeitprüfung nötig].
- **Dateien:** `runs/executor.py`, `runs/constants.py`, FE-Run-/Operation-Anzeigen.
- **Nutzerwirkung:** Abgebrochene/fehlgeschlagene Analysen wirken wie App-Defekte; Nutzer weiss nicht, ob/wie er neu starten soll.
- **Risiko:** mittel — Beta-Support-Last, Vertrauensverlust.
- **Priorität:** P1 (Beta). **Abhängigkeiten:** R1.
- **Akzeptanzkriterien:** Jede fehlgeschlagene Operation zeigt Grund (lesbar), Zeitpunkt und eine Aktion (erneut starten / Support-Hinweis); unterbrochene Runs sind als «unterbrochen, nicht fortgesetzt» gekennzeichnet; E2E-Fehlerpfad-Test.
- **Integration:** R1 (Anzeige aus kanonischem Stand) + R9 (Fehlerpfad-Politur).

### W-28 — Projektwechsel erzwingt Full Reload ohne Unsaved-Changes-Guard
- **Beschreibung:** `window.location.reload()` beim Projektwechsel [Code: components/shell/app-shell.tsx:130]. Kein sichtbarer Guard für ungespeicherte Änderungen; Tiptap-Session-Cache mildert nur innerhalb derselben Sitzung [Doc: Milestone 10.4].
- **Evidenzgrad:** [Code].
- **Nutzerwirkung:** möglicher Textverlust-Eindruck, Irritation.
- **Risiko:** niedrig–mittel. **Priorität:** P2. **Abhängigkeiten:** keine.
- **Akzeptanzkriterien:** Vor Wechsel: Prüfung auf ungespeicherte Änderungen mit Dialog; gezielte State-Invalidierung statt Hard-Reload, wo möglich; E2E-Test.
- **Integration:** R9.

### W-29 — Rollen-/Zugriffsmodell vorhanden, Abdeckung unverifiziert
- **Beschreibung:** Session-Auth, CSRF/Origin-Guards und `require_roles` existieren [Code: security/deps.py]; welche Endpoints rollenbeschränkt sind und ob das für Beta-Mehrbenutzerbetrieb reicht, ist unverifiziert.
- **Evidenzgrad:** Mechanik [Code]; Abdeckung [Inferenz].
- **Nutzerwirkung/Risiko:** unautorisierte Sicht auf fremde vertrauliche Projekte wäre Beta-Killer.
- **Priorität:** P1 (Beta-Gate). **Abhängigkeiten:** E-06/E-07.
- **Akzeptanzkriterien:** Endpoint-Rollen-Matrix dokumentiert; Tests je geschützter Route (fremder Workspace ⇒ 403); Ergebnis im R9-Gate-Report.
- **Integration:** R9.

### W-30 — No-Raw-Logging-Scope nur für Webresearch belegt
- **Beschreibung:** `redaction.py` (M9J) verhindert Roh-Query-Logging und liefert `safe_detail` [Code]. Nicht belegt: derselbe Schutz für A2-Drafting-Kontexte, Import-Inhalte, Fehler-Stacktraces mit Dokumenttext, FE-Konsole.
- **Evidenzgrad:** teils [Code], Rest [Inferenz].
- **Risiko:** hoch bei D2-Beta (vertrauliche Ideen in Logs). **Priorität:** P1, für D2-Beta P0.
- **Akzeptanzkriterien:** Log-/Audit-Suite: kein Klartext aus Quelldokumenten/Drafts/Projektidee in Logs, Audit-Details, Operation-Fehlertexten (Fixture-basierte Suche); `safe_detail`-Nutzung in allen Agent-/Import-Pfaden; Ausnahmefälle dokumentiert.
- **Integration:** R5 (A2-Pfad), R3 (Import-Pfad), R9 (Gesamtnachweis).

### W-31 — Injection-Härtung ohne Testsuite
- **Beschreibung:** Prompts markieren Quelltexte als «untrusted data» [Code: agents/prompts/*], Kontext ist anchor-whitelisted [Code: field_drafting_context allowed_anchor_ids]. Es fehlen adversariale Tests (Anweisungen in PDFs/Webseiten/Quotes), inkl. Tool-Response-Injection bei künftigem Web-Provider.
- **Evidenzgrad:** Härtung [Code]; Testlücke [Code — keine entsprechenden Fixtures gefunden, Inferenz].
- **Priorität:** P1. **Abhängigkeiten:** R5/R8.
- **Akzeptanzkriterien:** Injection-Fixture-Suite (min. 5 Muster: Instruktions-Override, Anchor-Erfindung, Datenexfiltration, Format-Bruch, Query-Manipulation); Vorschläge/Queries bestehen alle; Suite ist Merge-Gate für R5/R8.
- **Integration:** R5, R8.

### W-32 — Kosten/Latenz erzwungen, aber unsichtbar; kein API-Rate-Limit
- **Beschreibung:** CostGuard erzwingt Call-/Retry-/Timeout-/Token-Limits je AgentProfile; CHF-Kosten werden bewusst nie erfunden [Code: agents/cost_guard.py]. Keine Betreiber-/Nutzersicht auf Verbrauch; kein endpointseitiges Rate-Limiting belegt.
- **Evidenzgrad:** Guard [Code]; Rest [Inferenz].
- **Priorität:** P2 (P1 sobald realer Provider). **Akzeptanzkriterien:** Verbrauchsübersicht je Run (Aufrufe, Tokens, Dauer) aus UsageRecord; dokumentierte Limits; einfaches Rate-Limit für teure Endpoints; Latenz-Messwerte im Evaluationsbericht.
- **Integration:** R5 (Anzeige), R9 (Doku/Messung).

### W-33 — Performance bei grossen PDFs / vielen Fragments unbelegt
- **Beschreibung:** keine Last-/Volumentests gefunden. Verhalten bei 100+-Seiten-PDF, hunderten Fragments, Editor mit 25'000 Zeichen unbekannt.
- **Evidenzgrad:** [Annahme/Inferenz].
- **Priorität:** P2. **Akzeptanzkriterien:** Performance-Smoke mit definiertem Grossfixture; Messwerte (Parse-Zeit, Run-Dauer, UI-Interaktionslatenz) dokumentiert; harte Ausreisser als Issues.
- **Integration:** R9; Fixture ab R0-Harness.

### W-34 — Sprachstrategie DE/EN nicht definiert
- **Beschreibung:** UI Deutsch, Portalfragen/Feldnamen Englisch [UI: Screenshots 9–10]; Rechtschreib-Sprachwahl existiert [UI]. Unklar: Zielsprache der Feldtexte fürs Portal, Sprache der KI-Vorschläge, Konsistenzregel.
- **Evidenzgrad:** [UI]; Portal-Sprachanforderung [Annahme — mit offiziellen Unterlagen prüfen].
- **Priorität:** P2 (fachlich aber relevant: falschsprachige Texte = Rework). **Akzeptanzkriterien:** dokumentierte Sprachregel je Feld (aus Matrix/Portal ableiten, nicht raten); KI-Vorschlagssprache folgt Feldregel; UI kennzeichnet Zielsprache am Feld.
- **Integration:** Entscheid E-09; Umsetzung R5.

### W-35 — Accessibility ohne systematische Prüfung
- **Beschreibung:** Basis vorhanden (aria-Labels/`aria-pressed` in Editor-Toolbar [Code], Statuslabels zusätzlich zu Farben [UI]); kein systematischer Check (Kontrast, Tastaturnavigation, Screenreader-Pfade).
- **Evidenzgrad:** teils [Code/UI], Rest [Inferenz].
- **Priorität:** P2. **Akzeptanzkriterien:** A11y-Lint + manueller Kurzcheck der Kernflüsse; Befunde dokumentiert; kritische (Tastaturfallen) behoben.
- **Integration:** R9.

### W-36 — IPR/FTO ohne Prüfung und ohne Feldunterstützung
- **Beschreibung:** INTRO.IP.FINDINGS (5'000, Human Review) ist im Contract/Matrix definiert [Doc], aber weder Draft-Feld noch Prüfpunkt. Keine IP-Heuristiken.
- **Evidenzgrad:** [Doc/Code].
- **Nutzerwirkung:** ein bewertungsrelevanter Bereich (IP-Strategie) bleibt unsichtbar.
- **Priorität:** P1 (fachlich), Umsetzung als Stufe-B-Feld.
- **Akzeptanzkriterien:** Bei E-03=Stufe B: Feld aktiv mit Limit + Pflichtfragen; Readiness-Punkt «IPR-Dokumente» (aus W-16-Gates); Rubric-v1-Heuristik «IP-Abschnitt ohne FTO-/Schutzrechtsaussage» nur mit belegbarer Kriterienquelle, sonst weglassen.
- **Integration:** R5/R7b (bei Stufe B), sonst Backlog.

### W-37 — Testdaten-/Evaluation-Leakage-Policy fehlt
- **Beschreibung:** Regel «keine echten vertraulichen Daten in Fixtures» existierte nur als Ticket-Hinweis (v1 T-8.4). Kein dokumentierter Anonymisierungsprozess; Risiko, dass Gate-PDF oder Goldfälle Reales enthalten.
- **Evidenzgrad:** [Doc: v1; Inferenz].
- **Priorität:** P0 vor erstem Goldfall. **Akzeptanzkriterien:** schriftliche Policy (was gilt als anonymisiert, wer prüft, wo liegen Rohdaten — nie im Repo); Review-Nachweis je Fixture; CI-Check auf bekannte sensible Marker der Beispielprojekte.
- **Integration:** R0.

### W-38 — Prompt-/Profil-Regressionstests fehlen
- **Beschreibung:** Prompts sind dateibasiert versioniert (`*_v1.md` [Code: agents/prompts/]), aber ohne Snapshot-Tests; stille Prompt-Änderungen ändern Verhalten unbemerkt.
- **Evidenzgrad:** [Code].
- **Priorität:** P1. **Akzeptanzkriterien:** Hash-/Snapshot-Test je Prompt-Datei; Änderung erfordert Versions-Bump + Changelog-Zeile; Kontext-Hash-Tests bestehen weiter.
- **Integration:** R5.

### W-39 — Governance-/Disclaimer-Sprache nicht kanonisch
- **Beschreibung:** Gute Einzel-Disclaimer existieren («keine Aussage zur Förderwahrscheinlichkeit», «wird nicht eingereicht», Zwischenablage-Hinweis [UI]). Es fehlt ein kanonischer Katalog (welcher Disclaimer wo, welcher Wortlaut), inkl. Copy-fail-open-Aussage (W-26).
- **Evidenzgrad:** [UI/Code].
- **Priorität:** P2. **Akzeptanzkriterien:** Disclaimer-Katalog als Konstante; UI-Stellen referenzieren ihn; grep-Test gegen Alt-Wortlaute; Aussagen decken: keine Einreichung, keine Erfolgsprognose, Coverage ≠ Correctness, fail-open-Kopieren, Portal-Stand (last_checked).
- **Integration:** R6 (Statussprache) + R9.

### W-40 — ICT/KI-Datenprojekt-Spezialcheck fehlt (formalisiert)
- **Beschreibung:** Checklisten-Anforderungen für ICT/KI-Projekte (Datenquellen, Trainingsdaten, FP/FN, Metriken … [Doc: Kriterien]) ohne strukturierte Prüfung; war v1-Backlog, jetzt mit Bedingungen versehen.
- **Evidenzgrad:** [Doc/Code].
- **Priorität:** P2 (Backlog). **Akzeptanzkriterien (für später):** eigener Rubric-Block, nur aktiv wenn Innovationsfeld=ICT/KI; jede Heuristik mit Kriterienquelle; HITL-Label.
- **Integration:** Backlog nach R8.

### W-41 — Submit-/Integrity-/Kontakt-Gates unvollständig als Readiness-Punkte
- **Beschreibung:** Scientific-Integrity-Gate existiert deterministisch (Sanktionsfrage, human gate [Code: handlers.h_conditional_human_gate]). Fehlend als Readiness-Punkte: Main Contacts, Innovation Mentor, Admin-/Submit-Voraussetzungen (Bereiche laut Matrix [Doc]).
- **Evidenzgrad:** [Code/Doc].
- **Priorität:** P2 (Stufe B). **Akzeptanzkriterien:** Readiness-Checkliste «Summary & Submit» mit Status je Punkt (erfasst/fehlt), rein informativ, keine Einreichungsautomatik.
- **Integration:** R7b bei E-03=Stufe B, sonst Backlog.

## Geprüft und NICHT als neue Schwäche aufgenommen

- **Vector-Store-Policy:** kein Vector Store im Code gefunden [Inferenz aus Struktursichtung] — Policy erst nötig, falls eingeführt; Hinweis in R9-Checkliste.
- **Reviewer-Scoring vs. Förderwahrscheinlichkeit:** Schutz existiert bereits in UI-Texten [UI] und Produktregeln (v1); wird über W-39-Katalog kanonisiert, keine eigene Schwäche.
- **Tool-Allowlist:** Agent-Registry mit Profilen existiert [Code: agents/registry.py]; Nachweis (welche Tools je Profil erlaubt) wird R9-Gate-Punkt, keine eigene Schwäche.
