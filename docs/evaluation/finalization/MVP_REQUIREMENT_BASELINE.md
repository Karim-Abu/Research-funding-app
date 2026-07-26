---
title: "MVP-Requirement-Baseline (eingefroren)"
date: 2026-07-26
commit: 7f09c1f
branch: stabilize/eval3-final-01
status: frozen
tags: [eval3, requirements, baseline, mvp, scope]
---

# MVP-Requirement-Baseline (eingefroren)

Priorisierte Baseline des MVP-Umfangs, eingefroren mit dem Tag
`EVAL3-FINAL-01`. Grundlage: `final_backend_contracts_v1_1/requirements.yaml`
(Schema 1.0.0), maschinell ausgewertet über
`scripts/evaluation/requirement_coverage.py`; Rohdaten in
`docs/evaluation/generated/requirement_coverage.json`.

> **Kein Requirement wurde wegen roter Tests aus dem Scope entfernt.**
> Die Priorisierung beschreibt, was der MVP *auswertet*, nicht was als
> Anforderung gilt. Alle 76 Requirements bleiben `status: active`.

## 1. Gesamtbild

| Kennzahl | Wert |
|---|---|
| Requirements gesamt | **76** (alle `active`) |
| Severity | 52 `blocker` · 18 `warning` · 6 `info` |
| Typ | 42 `hard` · 20 `semantic` · 14 `hybrid` |
| Vom Regelwerk ausgewertet | **12** (`REQ.INNO.*`, verknüpft mit `official_core_rules`) |
| Nur im Contract | **64** (`REQ.PORTAL.*` → `QG.*`, nicht implementiert) |
| Portalfelder | 165 |
| Cross-Field-Rules | 17 (`XF.*`, ebenfalls nicht implementiert) |

## 2. Priorisierung

### P0 — MVP-Kern: ausgewertet und getestet (8)

Regel wird geladen, über `condition.type` in
`app/rules/handlers.py::HANDLERS` dispatcht (`app/rules/engine.py:90`) und von
mindestens einem Test namentlich abgedeckt.

| Requirement | Severity |
|---|---|
| `REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH` | blocker |
| `REQ.INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE` | blocker |
| `REQ.INNO.PARTNER.INDEPENDENCE.FINANCIAL_20` | blocker |
| `REQ.INNO.BUDGET.IMPLEMENTATION_SHARE_40_60` | blocker |
| `REQ.INNO.BUDGET.CASH_MIN5` | blocker |
| `REQ.INNO.BUDGET.NO_FINANCIAL_CAP` | info |
| `REQ.INNO.DURATION.TYPICAL_6_36` | info |
| `REQ.INNO.DURATION.MAX18_WITHOUT_IMPLEMENTATION_PARTNER` | warning |

### P1 — MVP-Kern: ausgewertet, ohne eigene Testreferenz (4)

Implementiert und lauffähig, aber kein Test nennt die Requirement- oder
Regel-ID wörtlich. **Bekannte Lücke, nicht aus dem Scope entfernt.**

| Requirement | Severity |
|---|---|
| `REQ.INNO.PARTNER.INDEPENDENCE.PERSONNEL` | blocker |
| `REQ.INNO.DURATION.NO_FORMAL_MAX_WITH_IMPLEMENTATION_PARTNER` | info |
| `REQ.INNO.APPLICATION.COMPLETE_AND_TRACEABLE` | blocker |
| `REQ.INNO.SCIENTIFIC_INTEGRITY.REVIEW` | blocker |

### P2 — Contract-only, ausserhalb des MVP-Umfangs (64)

Alle `REQ.PORTAL.<SECTION>.<GATE>` verweisen auf die 64 `QG.*`-Portal-Quality-
Gates. `app/registry/loader.py:222` liest ausschliesslich `official_core_rules`;
`QG.` und `XF.` kommen im Code nicht vor.

Verteilung nach Portalsektion: `PS` 22 · `ORG` 13 · `INTRO` 8 · `SOL` 8 ·
`SUM` 7 · `VC` 5 · sowie 1 weiteres.

**Bewusst nicht implementiert** — das war und bleibt eine Scope-Entscheidung
(`scope-gap`, siehe [[FINAL_STABILIZATION_FINDINGS]] F-22). Die vollständige
Liste steht in [[EVAL3_REQUIREMENT_COVERAGE]] Abschnitt B.

## 3. Coverage-Kennzahlen

Beide Nenner werden ausgewiesen; keine Prozentzahl ohne Bezugsgrösse.

| Kennzahl | gegen alle 76 | gegen die 12 auswertbaren |
|---|---|---|
| Implementation Coverage | **12/76 = 15,8 %** | **12/12 = 100,0 %** |
| Test Coverage | **8/76 = 10,5 %** | **8/12 = 66,7 %** |

Der niedrige Wert gegen 76 ist **keine Aussage über die Implementierungsqualität**,
sondern die Folge davon, dass 64 Requirements auf eine nie gebaute Gate-Ebene
verweisen. Wer nur die erste Spalte zitiert, stellt den MVP falsch dar; wer nur
die zweite zitiert, verschweigt den Contract-Überhang.

**«Test Coverage» heisst hier:** mindestens eine Testdatei nennt die
Requirement- oder Regel-ID wörtlich. Das belegt Vorhandensein, nicht fachliche
Vollständigkeit der Prüfung.

## 4. Was diese Baseline einfriert

- die 76 Requirements mit Severity, Typ und `assessment_basis`,
- die Zuordnung P0 / P1 / P2,
- die beiden Coverage-Kennzahlen mit ihren Nennern,
- den Stand `7f09c1f` auf `stabilize/eval3-final-01`, Tag `EVAL3-FINAL-01`.

Änderungen daran gehören in eine neue Baseline, nicht in diese Datei.

Siehe [[EVAL3_FINAL_01_REPORT]] · [[EVAL2_FINAL_RECONCILIATION]] ·
[[FINAL_INTEGRATION_BASELINE]]
