# Finale Definition of Done

Vier Stufen. Jede Stufe setzt die vorherige voraus. Kriterien sind messbar oder testbar — kein «wirkt stabil».

## Stufe 1 — Thesis-Demo (Pflicht für Abgabe/Verteidigung)

1. Statuswahrheit: Paritätstest grün; Dashboard/Anforderungen/Prüfung/Export zeigen identische Blocker-Zahlen; Stale-Zustände gekennzeichnet.
2. Keine doppelten Findings ohne Gruppierung; Fix Queue vorhanden und sortiert (6 Severity-Klassen).
3. Präzise Eligibility-Meldungen (entity-spezifisch); «Kein passender Partner vorhanden» existiert nicht mehr (grep-Test).
4. KI-Vorschläge für alle Stufe-A-Felder funktionieren on-demand — mit realem Provider gemäss E-02 oder mit Fake-Provider, dann in UI und Thesis explizit als solcher gekennzeichnet; jeder blockierte Zustand nennt Grund + Ausweg (kein Empty State ohne CTA).
5. Keine Auto-Übernahme von KI-Text (Regressionstest); Platzhalter-Aktionsmenü funktioniert.
6. EvidenceStatus-Leiter (7 Stufen) sichtbar; Kachelzahlen summenlogisch erklärt; Microcopy «Textstelle gefunden — fachliche Prüfung offen».
7. Copy-Readiness-Stufen in der Kopieransicht; «Trotzdem kopieren» nur mit Bestätigung bei Warnstufen.
8. D2/D3-Policy nachvollziehbar: Moduswahl im Intake, Mapping dokumentiert, NDA blockt hart mit Grund.
9. Keine Rohidee/Partnernamen/Budgetzahlen in ausgehenden Queries (Leakage-Suite grün) — gilt auch im Fake-Modus.
10. Deterministischer Budget-Rechner mit Live-Quoten und Regelquelle; kein LLM im Budgetpfad (Architektur-Test).
11. Mindestens 2 Evaluationsfälle mit Goldstandard ausgewertet (synthetisch zulässig); Bericht mit Metrikdefinitionen und Limitationen.
12. Import: entweder demonstrierbar (Upload→Review→Übernahme) oder Gate-Entscheid «streichen» mit Spike-Evidenz dokumentiert.
13. Demo-Pfad per Skript reproduzierbar; Demo-Daten klar als Demo isoliert.
14. Menschliche Freigabe bleibt zwingend für: Eligibility-Bestätigungen, Budget-Ausnahmen, IP-Aussagen, Partner-Fit, finalen Feldtext (Regressionstests, keine Auto-Approve-Pfade).

## Stufe 2 — Supervised Beta mit synthetischen/anonymisierten Daten

Zusätzlich:
15. R9-Security-Gate bestanden (jedes Item mit Testnachweis): Secrets nur via Env/Vault-Pfad dokumentiert; `cookie_secure=true` hinter TLS; Postgres-Option getestet; D2/D3-sessionStorage-Cache verifiziert deaktiviert; Rollen-Endpoint-Matrix mit 403-Tests; Tool-Allowlist-Nachweis; Audit-Redaction-Tests.
16. No-Raw-Logging über alle Pfade (Webresearch, A2-Kontext, Import, Fehlerpfade) mit Suite belegt.
17. Async-Fehlerpfade nutzerverständlich (Grund + Aktion); unterbrochene Runs gekennzeichnet.
18. Performance-Smoke bestanden (Grossfixture, dokumentierte Messwerte, keine Blocker-Ausreisser).
19. Betreuungsmodell (E-07) schriftlich; Vorfallsmeldeweg definiert.
20. Disclaimer-Katalog aktiv (keine Erfolgsprognose, keine Einreichung, Coverage ≠ Correctness, fail-open-Kopieren, Portal-Stand).
21. Testdaten-Policy (E-12) eingehalten; CI-Check auf sensible Marker grün.

## Stufe 3 — Supervised Beta mit echten D2-Daten

Zusätzlich:
22. Provider-Policy E-02 ≠ «nur Fake» ist dokumentiert mit Vertrags-/Betriebsbasis; direkte Consumer-APIs für D2 ausgeschlossen (Konfigtest).
23. D2-Gate bestanden (evaluation-and-beta-gates.md): Leakage-, Logging-, Rollen-, Injection-Suiten grün auf Produktionskonfiguration; Backup-/Löschkonzept für Projektdaten dokumentiert.
24. Nutzer-Einwilligung/Instruktion: was die App speichert, was Kopieren bedeutet (Zwischenablage-Hinweis), dass keine Einreichung erfolgt.
25. Rich-Editor-Format-Cache für D2/D3 deaktiviert (Test), Kopier-Protokollierungslücken werden dem Nutzer angezeigt.

## Stufe 4 — Post-MVP / Produktivversion (Ausblick, nicht Thesis-Scope)

26. Feldstufe C nach Contract-Verifikation; Portal-Drift-Prozess (aktive Quellenprüfung statt nur last_checked); semantische Belegprüfung (LLM-gestützt, HITL); WP-Vollstruktur, Risk Register, ICT/KI-Check, Partnerrecherche; Enterprise-Deployment gemäss E-10; Mehrmandanten-Betrieb mit vollem RBAC-Audit.

---

## «Fertig genug» — Kurzform (messbare Abschlusskriterien)

Die App gilt als fertig genug für Thesis + Beta-Stufe 2, wenn alle Punkte 1–21 grün sind und zusätzlich gilt: alle aktiven Felder sind copy-paste-ready-prüfbar (Status je Feld sichtbar, «was fehlt» beantwortet); Runtimes/Kosten/Fehlerpfade sind dokumentiert (UsageRecord-Auswertung + Fehlerpfad-Liste); keine widersprüchlichen Statuszahlen (Paritätstest ist Dauer-Gate); der Evaluationsbericht liegt vor.

---

## Must-have vs. Nice-to-have

### A. Must-have für den Bachelor-Thesis-Abschluss
- R0-Entscheide dokumentiert (auch Negativ-Entscheide zählen)
- R1 Statuswahrheit + Paritätsgate
- R2 Issue-Modell, Fix Queue, präzise Meldungen, Registry-Metadaten
- R4 Datenklassen v2 (Modi + Begründungen) — auch wenn E-02 = Fake/Local
- R5 KI-Assist Stufe A (Fake zulässig, ehrlich gelabelt) + Prompt-Regression + Injection-Suite + keine Auto-Übernahme
- R6 EvidenceStatus-Leiter + Copy-Readiness + Rubric v0
- R7a Budget-Rechner deterministisch
- Import: Gate-Entscheid dokumentiert; bei Ja: R3-MVP; bei Nein: R3'
- Evaluation: Harness + ≥2 Goldfälle + Bericht mit Limitationen
- Wirkungslogik-Kapitel: welche Ablehnungsrisiken sichtbar werden — ohne Erfolgsprognose

### B. Must-have für supervised beta mit echten Nutzern
- Alles aus A, plus DoD-Stufe 2 komplett (15–21)
- R7b Attachments-Gates + Intake ohne Doppelerfassung
- W-27-Fehlerpfade nutzerverständlich
- Bei echten D2-Daten: DoD-Stufe 3 (22–25)

### C. Nice-to-have / Post-MVP
- Feldstufe B (E-03) — wertvoll, aber nicht abschlusskritisch
- R8 Market-Slice mit echter Websearch (ohne E-05: Fake-Demo genügt für Thesis-Konzeptnachweis)
- Rubric v1 breit; ICT/KI-Check; IPR-Heuristiken
- WP-Minimalstruktur; Risk Register; Partnerrecherche
- URL-Import; Agent-Trace-Ansicht; A11y über Basis hinaus; Projektwechsel ohne Full Reload; NPV-Ansichten; Word-Export-Politur; Azure-Architektur-Doku (E-10)

---

## UX-DoD-Katalog (Zielzustand, prüfbar)

1. **Startflow:** drei Startoptionen (Antrag hochladen [falls E-01=Ja] / Projektidee / Notizen & Quellen); Intake ohne Partner-/Budgetdetails.
2. **Arbeitslogik:** Fix Queue ist der Standard-Einstieg nach jeder Analyse; jeder Eintrag beantwortet Warum/Wie/Wo/KI-möglich/Quelle-fehlt.
3. **Keine Sackgassen:** jedes «nicht verfügbar» nennt Grund + mindestens eine CTA; grep-Test auf verbotene Alt-Texte.
4. **Statussprache:** kanonischer Katalog (Statusleiter-Begriffe, Copy-Stufen, Disclaimer); Farben nie alleiniger Informationsträger.
5. **Labels:** Registry-Labels statt Technik-Namen; «Open Editor» existiert nicht mehr (grep-Test).
6. **Redundanz:** Stepper führt in der Projektbearbeitung; «Quellen importieren» / «Belege zuordnen» klar getrennt; Navigations-Audit ohne Doppelziele.
7. **Verlustschutz:** Reload-Guard bei ungespeicherten Änderungen.
