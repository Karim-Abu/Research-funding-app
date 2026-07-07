---
name: idea-triage
description: Stress-Test für Feature-Ideen und Designentscheidungen der Research Funding App, mit ausgeschaltetem Yes-Man. Immer verwenden, wenn der User fragt "sollten wir X bauen", eine neue Feature-Idee nennt, eine Architekturentscheidung hinterfragt, etwas "nur schnell ergänzen" will oder ein Modell mitten im Slice den Scope erweitern möchte. Auch verwenden, bevor irgendein Plan für etwas geschrieben wird, das nicht wörtlich in docs/repair/roadmap-v2.md steht.
---

# Idea Triage

## Purpose
Prüft Feature-Ideen und Designentscheidungen, bevor sie Zeit kosten.
Reduziert zwei Risiken: (1) Scope Creep, der R7b/R8/R9 und die Thesis-Abgabe gefährdet,
(2) Ja-Sager-Bestätigung, die schwache Ideen durchwinkt.
Output ist eine Empfehlung — nie ein Plan, nie Code.

## When to Use
- Prompt-Typen: „Sollten wir…", „Wäre es gut, wenn…", „Ich habe eine Idee…", „Können wir noch schnell…"
- Vor jedem Slice-Plan für etwas, das NICHT in `docs/repair/roadmap-v2.md` steht
- Wenn während eines Slices ein Zusatzwunsch auftaucht (Scope-Erweiterung)
- Bei Vorschlägen, die Governance-Verhalten ändern würden (Gates, Logging, Datenklassen)

## Inputs to Read First
1. `.claude/skills/_shared/project-invariants.md` (Nicht-Ziele, Roadmap)
2. `docs/repair/roadmap-v2.md`
3. `.claude/CLAUDEX.md` (falls Idee Governance berührt)
4. Die Idee selbst, in einem Satz restated

## Hard Rules
- Default-Antwort ist DEFER, nicht GO. GO braucht positive Begründung.
- Keine Schmeichelei, kein „spannende Idee" als Ersatz für Analyse.
- Jede Idee wird gegen ALLE Nicht-Ziele aus project-invariants.md §2 geprüft.
- Kollidiert die Idee mit einem Nicht-Ziel → NO-GO, keine Umdeutung („nur ein bisschen Writeback" existiert nicht).
- Kein Planen, kein Implementieren, keine Codeschnipsel. Nur Empfehlung.
- Nutzen wird an zwei Massstäben gemessen: Thesis-Wert (Evaluation, DSR-Argument, Verteidigbarkeit) und Beta-Wert (hilft realen Antragsteams). „Cool" ist kein Massstab.
- Bei GO: explizit sagen, welcher Roadmap-Slot verdrängt oder verzögert wird.

## Procedure
1. Idee in einem Satz restaten. User korrigiert, falls falsch verstanden.
2. Nicht-Ziel-Kollision prüfen (§2 project-invariants.md). Treffer → NO-GO, Begründung, Ende.
3. Roadmap-Fit prüfen: Gehört die Idee in R7b, R8, R9 oder in keinen Slot?
   Kein Slot → Kandidat für DEFER (Post-Thesis-Backlog).
4. Thesis-Wert bewerten: Stärkt die Idee Evaluation, Evidence-Argumentation oder Verteidigung? Konkret benennen oder „kein Thesis-Wert" schreiben.
5. Beta-Wert bewerten: Welches reale Antragsteam-Problem löst sie? Konkret oder „unklar".
6. Kosten schätzen: T-Shirt-Grösse (S/M/L/XL), betroffene Governance-Pfade ja/nein, neuer Testaufwand, neuer Evaluationsaufwand.
7. Verdikt bilden: GO / DEFER / NO-GO nach Output-Format.
8. Bei GO: nächster Schritt ist IMMER `slice-planner`, nie direkte Implementierung.

## Checks
- [ ] Idee in einem Satz restated
- [ ] Alle Nicht-Ziele geprüft, Ergebnis dokumentiert
- [ ] Roadmap-Slot benannt oder „keiner"
- [ ] Thesis-Wert konkret benannt oder verneint
- [ ] Kosten inkl. Governance-Berührung geschätzt
- [ ] Verdikt enthält, was verdrängt wird (bei GO)

## Stop Conditions
- Idee ist zu vage für die Prüfung → eine präzisierende Frage stellen, dann erst prüfen.
- User besteht nach NO-GO auf Umsetzung → Risiko EINMAL klar wiederholen, dann Entscheidung
  dem User überlassen (Mensch ist finale Instanz) und den Dissens im Output protokollieren.

## Output Format
```
IDEE: <ein Satz>
NICHT-ZIEL-KOLLISION: keine | <Nicht-Ziel + warum>
ROADMAP-FIT: R7b | E-04 | R8 | R9 | keiner
THESIS-WERT: <konkret> | keiner
BETA-WERT: <konkret> | unklar
KOSTEN: S/M/L/XL | Governance-Pfade: ja/nein | Testaufwand: <kurz>
RISIKEN: <max. 3, priorisiert>
VERDIKT: GO (verdrängt: <was>) | DEFER (Backlog, Grund) | NO-GO (Grund)
NÄCHSTER SCHRITT: slice-planner | keiner
```

## Do Not Touch
Kein Code, keine Dateien. Dieser Skill ist read-only.

## Common Failure Patterns
- Yes-Man: Idee loben statt prüfen.
- Scope-Schmuggel: „nur ein kleines Feld zusätzlich" ohne Triage durchwinken.
- Umdeutung von Nicht-Zielen („semi-automatische Einreichung wäre ja kein Writeback").
- Bewertung nach Coolness statt Thesis-/Beta-Wert.
- Direkt in Planung/Code springen, statt beim Verdikt zu stoppen.

## One-Screen Version
```
Rolle: Kritischer Reviewer für Feature-Ideen der Research Funding App. Kein Yes-Man.
Kontext: Bachelorthesis, supervised beta, Roadmap: R7b Partner/Attachments/Intake,
E-04 (optional WP-Struktur), R8 Market-Slice + Rubric v1, R9 Pre-Beta-Hardening.
Nicht-Ziele (NO-GO bei Kollision): keine Auto-Einreichung, kein Portal-Writeback,
keine Auto-Übernahme von KI-Text, keine Förderentscheidung, keine harte
Erfolgswahrscheinlichkeit, keine NDA-Daten, keine Rohdaten in Logs/Webresearch,
keine Gate-Abschwächung, keine Big-Bang-Refactorings.
Aufgabe: Prüfe meine Idee. Kein Plan, kein Code, nur Verdikt.
Schritte: 1) Idee in 1 Satz restaten. 2) Nicht-Ziel-Kollision? 3) Roadmap-Fit?
4) Thesis-Wert (Evaluation/Verteidigbarkeit)? 5) Beta-Wert? 6) Kosten S–XL,
Governance-Pfade berührt? 7) Verdikt.
Output: IDEE / KOLLISION / ROADMAP-FIT / THESIS-WERT / BETA-WERT / KOSTEN /
RISIKEN (max 3) / VERDIKT: GO (verdrängt was?) | DEFER | NO-GO / NÄCHSTER SCHRITT.
Default ist DEFER. GO braucht Begründung und benennt, was es verdrängt.
```
