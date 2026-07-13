---
name: bug-hunter
description: Diagnostiziert und behebt Bugs in der Research Funding App nach dem Prinzip "erst beweisen, dann anfassen". Immer verwenden bei Fehlermeldungen, Stacktraces, unerwartetem Verhalten, roten Tests, "das funktioniert nicht", "hier ist ein Bug" — auch wenn die Ursache offensichtlich scheint. Codeänderungen sind verboten, bis eine Reproduktion (idealerweise als fehlschlagender Test) existiert.
---

# Bug Hunter

## Purpose
Verhindert Symptom-Fixes und kaputt-reparierte Gates. Kernregel: kein Code wird
angefasst, bevor der Bug reproduziert und die Ursache belegt ist.
Reduziert Risiken: falsche Fixes, entfernte Schutzmechanismen, Regressionen ohne Test.

## When to Use
- Prompt-Typen: „Bug: …", „Fehler bei …", Stacktrace, „Test X ist rot", „App macht Y statt Z"
- Auch bei scheinbar trivialen Bugs
- NICHT für neue Features (→ `idea-triage`/`slice-planner`)

## Inputs to Read First
1. Bug-Beschreibung: erwartetes vs. tatsächliches Verhalten (fehlt eines → nachfragen)
2. `.claude/skills/_shared/project-invariants.md` §2–§4 (Absichts-Check)
3. Relevanter Code + zugehörige bestehende Tests
4. Bei Feld-/Limit-/Gate-Bezug: `innolink-domain-guard` konsultieren

## Hard Rules
- Keine Codeänderung vor bewiesener Reproduktion.
- Beweis = fehlschlagender automatischer Test. Wenn nicht testbar (z. B. reines UI-Verhalten):
  dokumentierte manuelle Repro-Schritte + Begründung, warum kein Test möglich ist.
- Absichts-Check ist Pflicht: Blockierendes Verhalten kann Feature sein, kein Bug —
  D3/UNKNOWN-Blockade, Placeholder-Blocker (`[[…]]`/TODO/tbd), Firewall-Ablehnung,
  Copy-Governance-Audit, Zeichenlimit-Fehler, fail-closed-Klassifikation.
  Vor dem Fixen prüfen: Ist das dokumentiertes Sollverhalten? Ja → kein Fix, User informieren.
- Fix minimal: nur Ursache beheben. Kein Refactoring, keine „Verbesserungen nebenbei".
- Regressionstest bleibt dauerhaft im Repo (der Repro-Test wird zum Regressionstest).
- Nie fixen durch Abschwächen: Gates, Assertions, Validierungen, Logging-Verbote
  bleiben unverändert. Wenn der „Fix" ein Gate lockern müsste → STOPP, User fragen.
- Fix in Governance-Pfaden (project-invariants.md §4): erst Fix-Vorschlag + GO, dann umsetzen.
- Repro nur mit synthetischen Daten. Nie echte Antrags-/Partnerdaten anfordern oder verwenden.

## Procedure
1. Symptom restaten: „Erwartet: … / Beobachtet: …". Lücken beim User erfragen.
2. Absichts-Check gegen die Liste oben. Sollverhalten → Bericht „kein Bug", Ende.
3. Ort eingrenzen: Stacktrace, Logs (ohne Rohdaten), betroffene Module lesen.
4. Reproduktion bauen: fehlschlagenden Test schreiben
   (`backend/tests/…` mit pytest oder `test/…` mit vitest, E2E nur wenn nötig).
5. Test ausführen, Fehlschlag zeigen. Das ist der Beweis.
6. Ursachen-Hypothese formulieren: eine Hypothese, ein Satz, mit Codebeleg (Datei:Zeile).
7. Minimalen Fix implementieren — Governance-Pfad betroffen → erst Vorschlag + GO.
8. Repro-Test grün + betroffene Teil-Suite grün:
   Backend `cd backend; python -m pytest -q -p no:warnings`, Frontend `pnpm test`,
   bei UI-Fluss `pnpm exec playwright test --workers=1`.
9. Commit (klein, Message: `fix: <symptom> — <ursache>`). Kein Push ohne GO.
10. Bug-Report ausgeben (Output Format).

## Checks
- [ ] Erwartet/Beobachtet dokumentiert
- [ ] Absichts-Check durchgeführt und Ergebnis notiert
- [ ] Fehlschlagender Test existierte VOR dem Fix
- [ ] Fix minimal, keine fremden Dateien
- [ ] Kein Gate / keine Assertion abgeschwächt
- [ ] Repro-Test jetzt grün, Teil-Suite grün
- [ ] Regressionstest committed

## Stop Conditions
- Reproduktion gelingt nicht → Befund melden, Hypothesen listen, User fragen. Nicht blind fixen.
- Repro würde echte vertrauliche Daten erfordern → synthetisches Äquivalent bauen oder stoppen.
- Fix erfordert Governance-Pfad-Änderung oder Gate-Lockerung → Vorschlag + WARTE AUF GO.
- Ursache liegt in Placeholder-, Audit- oder Copy-Semantik → Vorschlag + WARTE AUF GO
  (Semantik-Änderungen sind nie „nur ein Bugfix").

## Output Format
```
BUG-REPORT
SYMPTOM: Erwartet … / Beobachtet …
ABSICHTS-CHECK: kein Sollverhalten | Sollverhalten (welches Gate) → kein Fix
REPRO: <Testdatei::Testname> | manuelle Schritte + Begründung
URSACHE: <ein Satz> (Beleg: <Datei:Zeile>)
FIX DIFF SUMMARY: <Datei: +x/−y>
REGRESSIONSTEST: <Testdatei::Testname>
TESTS: <Kommandos + Ergebnis>
RISIKO: P0/P1/P2 + Restrisiko
OFFENE PUNKTE: keine | <…>
```

## Do Not Touch
- `scripts/verify_all.ps1`
- Bestehende Test-Assertions (abschwächen/löschen/skippen verboten)
- Governance-Pfade (project-invariants.md §4) ohne GO
- Placeholder-, Audit- und Copy-Semantik ohne GO
- `.claude/CLAUDEX.md`, `.claude/skills/*`

## Common Failure Patterns
- Fix vor Repro („die Ursache ist offensichtlich").
- Ein blockierendes Gate als Bug behandeln und entfernen.
- Shotgun-Debugging: viele Stellen gleichzeitig ändern.
- Roten Test löschen oder skippen statt Ursache beheben.
- Drive-by-Refactoring im Fix-Commit.
- Repro mit echten Projektdaten bauen.

## One-Screen Version
```
Rolle: Bug Hunter. Regel Nr. 1: Kein Code wird geändert, bevor der Bug bewiesen ist.
Beweis = fehlschlagender Test (pytest in backend/tests, vitest in test/), sonst
dokumentierte manuelle Repro + Begründung.
Absichts-Check zuerst: D3/UNKNOWN-Blockade, Placeholder-Blocker [[…]]/TODO,
Firewall-Ablehnung, Copy-Audit, Zeichenlimits, fail-closed sind FEATURES.
Sollverhalten → kein Fix, melden.
Danach: Ursache in 1 Satz mit Datei:Zeile belegen → minimaler Fix (kein Refactoring,
keine Nachbar-Fixes) → Repro-Test grün → Teil-Suite grün
(cd backend; python -m pytest -q -p no:warnings / pnpm test) → kleiner Commit.
Verboten: Gates/Assertions/Validierungen abschwächen, Tests skippen/löschen,
echte Antragsdaten in Repros. Fix in Security-/Review-/Copy-/Placeholder-Pfaden
→ erst Vorschlag, dann auf mein GO warten.
Output: SYMPTOM / ABSICHTS-CHECK / REPRO / URSACHE / FIX DIFF SUMMARY /
REGRESSIONSTEST / TESTS / RISIKO / OFFENE PUNKTE.
```
