---
title: "F-25 — Dashboard-Flake: Analyse"
date: 2026-07-26
commit: 7f09c1f
branch: stabilize/eval3-final-01
status: not-reproduced
tags: [eval3, flake, dashboard, test-stability]
---

# F-25 — Dashboard-Flake

| Punkt | Inhalt |
|---|---|
| **Ursprünglicher Befund** | `test/dashboard.test.tsx > projects overview > removes a card via the kebab menu and archives the project` schlug am 2026-07-26 in zwei aufeinanderfolgenden Vitest-Vollläufen fehl (`FIX-VITEST-01`: 1 Fehler; `FIX-VITEST-02`: 3 Fehler), war isoliert aber grün. Laufzeit im Fehlerfall 5171 ms — Timeout-Charakteristik. |
| **Reproduktionsrate** | **0 von 13** auf dem finalen Stand `7f09c1f`: 10 Einzelläufe der Datei (`pass=10 fail=0`) und 3 vollständige Vitest-Läufe (`pass=3 fail=0`, je 79 Dateien / 653 Tests). |
| **Ursache** | **Nicht abschliessend nachgewiesen.** Die belastbarste Erklärung ist umgebungsbedingt: Die beiden Fehlläufe fanden statt, **während am Markt-UI parallel gearbeitet wurde** — `lib/market-view.ts`, `components/editor/live-market-comparison.tsx`, `market-comparison-sheet.tsx` und drei zugehörige Testdateien wurden im selben Zeitfenster geschrieben (Zeitstempel 14:51–14:54, Vitest-Läufe 14:5x). Vitest liest Module beim Lauf ein; ein Schreibvorgang mitten im Lauf erklärt sowohl den Timeout als auch, dass beim zweiten Lauf drei statt einem Test fielen. Zusätzlich war der Baum zu diesem Zeitpunkt nicht übersetzbar (12 `tsc`-Fehler). |
| **Änderung** | **Keine.** An `test/dashboard.test.tsx` und am Dashboard-Code wurde nichts geändert. Ein Fix ohne nachgewiesene Ursache wäre Rateraten. |
| **Isolierter Nachweis** | 10× `vitest run test/dashboard.test.tsx` → 10× grün (5 Tests je Lauf). Keine Fehl-Logs erzeugt (`runs/F25/` enthält daher keine `fail_file_*.log`). |
| **Vollsuiten-Nachweis** | 3× `vitest run` → 3× grün, je 79 Dateien / 653 Tests (`runs/F25/full_1..3.log`). Die Anforderung «mindestens zwei konsistente Vollläufe» ist erfüllt. |
| **Rest-Risiko** | **Vorhanden und ausgewiesen.** Ein nicht reproduzierter Flake ist nicht dasselbe wie ein behobener Flake. Die vermutete Ursache (gleichzeitige Dateiänderungen während des Laufs) ist plausibel und deckt die Beobachtung, ist aber nicht bewiesen. Sollte der Fehler auf einem ruhigen Baum erneut auftreten, ist die Einstufung zu revidieren. |

## Klassifikation

**`not-reproduced`** — mit `environment-specific` als begründeter, aber
unbewiesener Hypothese.

Ausdrücklich **nicht** als `product-defect` oder `test-isolation-defect`
eingestuft: für beides fehlt der Nachweis, und die geforderten Prüfpunkte
(globale Stores, Module-Cache, Mock-Timer, DOM-Cleanup, Fetch-Mocks, Locale,
Timezone, Race Conditions) liessen sich mangels reproduzierbarem Fehlerfall
nicht am lebenden Objekt untersuchen. Eine Ursachenanalyse ohne auslösbaren
Fehler hätte nur Vermutungen produziert.

## Methodische Anmerkung

Die Läufe wurden **vorab festgelegt** (10 Einzel-, 3 Vollläufe) und vollständig
berichtet. Es wurde nicht wiederholt, bis ein grünes Ergebnis entstand — das
Gegenteil wäre der Fall gewesen, wenn ein roter Lauf aufgetreten und
verschwiegen worden wäre.

## Konsequenz für den Abschluss

F-25 gilt **nicht als geschlossen**, sondern als `not-reproduced` mit
dokumentiertem Rest-Risiko. Der Gate-Status wird davon nicht grün gefärbt;
die Beobachtung bleibt in [[EVAL3_FINAL_01_REPORT]] als bekannte Grenze
geführt.

Siehe auch [[FINAL_STABILIZATION_FINDINGS]] F-25.
