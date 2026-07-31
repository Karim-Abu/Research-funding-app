---
title: "EVAL2 + EVAL3 — Einstieg"
date: 2026-07-25
commit: 8416914
status: index
tags: [eval2, eval3, index, evaluation]
---

# EVAL2 + EVAL3 — Evidenz-, Reproduktions- und Evaluationslauf

Erzeugt am **2026-07-25** gegen Commit `8416914` (Working Tree **dirty**,
Status `non-frozen-working-tree`).

Alle Dateien in diesem Ordner sind für den Import nach Obsidian ausgelegt:
YAML-Frontmatter, `[[Wikilinks]]` untereinander, keine externen Abhängigkeiten.

## Dokumente

| Dokument | Inhalt |
|---|---|
| [[EVALUATION_BASELINE]] | Reproduzierbarer Ausgangszustand: Commit, Toolchain, Provider-Modus, dirty-Tree-Dateiliste, Kostenschutz |
| [[TECHNICAL_EVIDENCE_INVENTORY]] | Alle Tests, Skripte, Berichte und Artefakte — mit kritischer Prüfung, welche Aussage tatsächlich belegt ist |
| [[EVAL3_EXECUTION_PLAN]] | Die ausgeführten Befehle, die Erfassungsstrategie und die bewusst nicht ausgeführten Kategorien |
| [[EVAL2_IMPLEMENTATION_RECONCILIATION]] | 23 formative Designentscheidungen gegen Code und Testergebnis |
| [[EVAL3_TECHNICAL_VERIFICATION]] | Ergebnisse aller Läufe, Lückenklassifikation, Kennzahlen |
| [[EVAL3_REQUIREMENT_COVERAGE]] | Requirement→Regel→Test-Matrix über 76 Requirements, mit ausgewiesenen Nennern |

## Rohdaten

```
runs/<RUN_ID>/
  command.txt     wörtlicher Befehl
  stdout.log      vollständige Ausgabe
  stderr.log      Fehlerausgabe
  result.json     Exit Code, Start/Ende, Commit
  junit.xml       maschinenlesbare Testergebnisse (wo der Runner es unterstützt)
```

Zusätzlich: `requirement_coverage.json` (Rohdaten der Coverage-Matrix),
`runs/GATE-01/verify_all.log` (erstmals erfasstes Gate-Protokoll),
`runs/BACKEND-01/failures.md` (Fehleranalyse inkl. Flakiness-Prüfung).

## Ergebnis in Kürze

| Lauf | Ergebnis |
|---|---|
| Contract-Validator, Guards, Migration | **PASS** |
| Backend-pytest | **FAIL** — 1514 Tests, 6 Fehler, 4 skipped |
| Lint / Typecheck / Vitest / Build | **PASS** — 631 Frontend-Tests grün |
| E2E (6 gezielte Specs) | **FAIL** — 9 passed, 1 failed |
| Gesamtgate `verify_all.ps1` | **ROT** (Exit 1) |
| EvaluationRunSummary | erzeugt — weicht in 5 Kennzahlen von der Spec ab |

Die **Testsubstanz ist stark** — 1514 Backend-Fälle, 631 Frontend-Fälle,
72 E2E-Fälle, ein hermetischer Provider-Guard mit eigenem Regressionstest.

Die **Beweisführung darüber war schwach** — kein CI, kein Gate-Protokoll, keine
versionierten Maschinenartefakte, widersprüchliche Statusmarker. Dieser Lauf
schliesst die Lücke für den deterministischen Teil, ohne eine Produktzeile zu
ändern.

**Der aktuelle Arbeitsstand ist nicht grün.** Die Gründe sind in
[[EVAL3_TECHNICAL_VERIFICATION]] §2–§4 einzeln getrennt: echte Backend-Regression,
zwei reihenfolgeabhängige Tests, eine Regression aus der nicht committeten
UI-Bereinigung — plus drei Mängel der Verifikationsinfrastruktur selbst.

## Abgrenzung

- Das Repository verwendet `EVAL0/EVAL1/EVAL2` bereits für etwas anderes
  (z. B. `docs/evaluation/eval2_real_provider_smoke_report.md` =
  Real-Provider-Smoke). Die Dokumente hier sind die **Thesis**-EVAL2/EVAL3.
- Es wurde **kein** kostenpflichtiger Provider-Aufruf ausgeführt.
- Es wurde **kein** Produktionscode, **kein** Test und **keine** Konfiguration
  geändert. Fehlgeschlagene Tests sind als fehlgeschlagen berichtet.
- Keine EVAL4-Bewertung.

Neu erstellt für diesen Lauf und als solches gekennzeichnet:
`scripts/evaluation/requirement_coverage.py` (evaluation-only, ohne Zugriff auf
Runtime-Logik).
