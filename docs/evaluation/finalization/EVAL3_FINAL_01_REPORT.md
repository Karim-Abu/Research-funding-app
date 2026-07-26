---
title: "EVAL3-FINAL-01 — Technischer Abschlussbericht"
date: 2026-07-26
commit: 7f09c1f
branch: stabilize/eval3-final-01
tag: EVAL3-FINAL-01
gate: GRÜN
tags: [eval3, final, verification, gate]
---

# EVAL3-FINAL-01 — Technischer Abschlussbericht

Abschliessende Verifikation des stabilisierten MVP auf dem eingefrorenen Stand
des Branches `stabilize/eval3-final-01`.

> **Ergebnis: Das deterministische Gesamtgate ist GRÜN** — 14 von 14 Kategorien,
> Exit 0, Laufzeit 768 s, `readiness: ready`, Cleanup ohne verwaiste Prozesse.
> Erstmals belegt durch ein maschinenlesbares Artefakt statt durch eine Abschrift.

Ausgangszustand: [[FINAL_INTEGRATION_BASELINE]] ·
Findings: [[FINAL_STABILIZATION_FINDINGS]] ·
Requirements: [[MVP_REQUIREMENT_BASELINE]] ·
EVAL2: [[EVAL2_FINAL_RECONCILIATION]]

## 1. Gate-Ergebnis (`FINAL-GATE-05`)

| Kategorie | Status |
|---|---|
| backend tests | **pass** — 1514 Tests |
| migration (frische DB) | **pass** |
| frontend tests (vitest) | **pass** — 79 Dateien / 653 Tests |
| build / typecheck / lint | **pass** |
| Playwright (Gesamtsuite) | **pass** — 54 passed, 16 skipped, 3,1 min |
| technischer E2E (2. Lauf, golden-path) | **pass** |
| funktionaler Import | **pass** |
| review truth | **pass** |
| docx render smoke | **pass** |
| API smoke | **pass** |
| export smoke | **pass** (eigenständig) |
| no-raw-log | **pass** (eigenständig) |
| legacy status guard | **pass** |
| testdata markers | `not-applicable-no-markers` |

`overall_status: GRÜN`, `failed_tests: []`.
Rohdaten: `docs/evaluation/final/EVAL3-FINAL-01/runs/FINAL-GATE-05/`.

**`testdata markers` ist bewusst kein `pass`.** Der Markerkatalog in
`docs/evaluation/testdata-policy.md` ist leer (`TODO(Owner)`); ein Lauf mit 0
geprüften Markern prüft faktisch nichts. Früher meldete diese Zeile `pass` und
suggerierte eine Prüfung, die nie stattfand.

## 2. Der Weg dorthin — fünf Läufe, drei eigene Fehler

Vollständig berichtet, keiner ausgelassen. Es wurde **nicht** wiederholt, bis
zufällig ein grüner Lauf entstand: jeder Lauf folgte auf eine benannte,
behobene Ursache.

| Lauf | Ergebnis | Ursache | Behebung |
|---|---|---|---|
| `FINAL-GATE-01` | ROT | **Umgebung** — fremde Listener auf :3000/:8000; Server konnten nicht binden | Ports freigeräumt; Vorab-Prüfung + `port-conflict`-Zustand ergänzt |
| `FINAL-GATE-02` | ROT | **eigener Fehler** — Steuerzeichen in Logpfaden (`\v`, `\t`, `\b` als Escapes interpretiert) → `Illegales Zeichen im Pfad`, Abbruch nach dem DOCX-Smoke | Pfade auf `Join-Path` umgestellt |
| `FINAL-GATE-03` | ROT | **eigener Fehler** — Golden-Path-Locator war gefiltert («Zeile, deren Badge ‹Offen› zeigt») und löste sich beim Statuswechsel auf; exakt der Mangel, den ich am Original kritisiert hatte | Zeilenindex **vor** dem Klick binden (`nth()`) |
| `FINAL-GATE-04` | ROT | **eigener Fehler** — beim Kürzen des `SUPPORT_LADDER_HINT` wurde «**abschliessende** Bewertung» zu «**fachliche** Bewertung»; `m10-2-ux.spec.ts` prüft den Wortlaut | Wortlaut wiederhergestellt (HITL-Aussage, CLAUDEX §4) |
| **`FINAL-GATE-05`** | **GRÜN** | — | — |

**Alle drei eigenen Fehler fand erst das Gate.** Keiner wäre über die
Vitest-Suite aufgefallen — das ist zugleich der stärkste Beleg dafür, dass die
Gate-Reparatur ihren Zweck erfüllt.

Besonders unangenehm ist Lauf 04: Beim Kürzen der UI-Texte hatte ich zugesagt,
keine Aussage mit rechtlichem oder epistemischem Gehalt abzuschwächen — und
genau das getan. «Abschliessend» sagt, dass das *letzte* Urteil beim Menschen
liegt; «fachlich» sagt das nicht.

## 3. Wirksamkeitsnachweise der Gate-Reparatur

Jeder Punkt ist an einem konkreten Lauf belegt:

| Reparatur | Nachweis |
|---|---|
| `skip` färbt rot (vorher: bestand das Gate) | Lauf 02 brach nach dem DOCX-Smoke ab; 7 Kategorien blieben `skip`. Das alte Gate hätte **GRÜN** gemeldet. |
| Eigenständige Smoke-Gates | `export` und `norawlog` meldeten in **allen** Läufen `pass` — auch als das Gate rot war. Vorher kopierten sie `$R.backend` und hätten fälschlich `FAIL` gezeigt. |
| Differenzierte Readiness | Lauf 01 nannte `port-conflict` statt des früheren nichtssagenden «servers not ready»; Läufe 03–05 meldeten `ready`. |
| Server-Logs | `backend-server.log/.err`, `frontend-server.log/.err` — vorher ging Serverausgabe in ein verstecktes Fenster und war verloren. |
| PID-basiertes Cleanup | `started_pids` / `stopped_pids` je Lauf protokolliert, `remaining_listeners: []`. |
| Opt-in-Pfad korrigiert | Kategorie «Model selection» zeigt `durchgeführt` statt dauerhaft `not_run` (Pfad wies auf eine nie erzeugte Datei). |
| Marker-Guard | meldet ehrlich `not-applicable-no-markers`. |
| Explizites `exit 0` | Ein grüner Lauf endet zuverlässig mit 0 (vorher fiel der Code auf den letzten nativen Befehl zurück). |
| Frontend-/Playwright-Ausgabe erfasst | `vitest.log`, `lint.log`, `tsc.log`, `build.log`, `pw-suite.log` u. a. — vorher fing `Start-Transcript` die `iex`-Ausgaben nicht ein. |

## 4. Bekannte Grenzen — ehrlich ausgewiesen

Diese Punkte relativieren das grüne Gate und gehören in jede Zitation:

1. **Instabilität unter Last.** In einem manuellen Gesamtsuite-Lauf fielen
   `import-flow.spec.ts:153` (`read ECONNRESET`) und
   `m10-acceptance.spec.ts:78` (Timeout 60 s); gezielt liefen beide zusammen mit
   dem dritten Spec in 23,7 s durch. Im Gate-Lauf 05 waren sie grün. **Nicht als
   behoben eingestuft**, sondern als beobachtete Instabilität.
2. **F-25 Dashboard-Flake:** `not-reproduced` (10× Datei, 3× Vollsuite grün),
   Ursache nicht bewiesen. Siehe [[F25_DASHBOARD_FLAKE_ANALYSIS]].
3. **Testdaten-Marker prüfen nichts** — leerer Katalog, Owner-Entscheid offen.
4. **64 Portal-Quality-Gates sind contract-only** und bleiben es (`scope-gap`).
5. **Keine parallelen KI-Textvarianten** — nie implementiert, bewusst nicht
   nachgerüstet.
6. **`Evaluation_Dataset.md` weicht in 5 Kennzahlen** von der Messung ab
   (`specification-drift`, unverändert offen).
7. **Responsive Darstellung der neuen Markt-UI nicht geprüft** — die
   vorhandenen Screenshots stammen vom 23.07. und zeigen den Stand davor.
8. **Keine realen Provider-Läufe.** Vier env-gated Smokes bleiben `blocked`;
   die Kategorien 3–5 stützen sich auf **historische** Artefakte (15.–23.07.),
   nicht auf diesen Lauf.
9. **Kein CI.** Das Gate bleibt ein manuell gefahrener Lauf auf einer
   Entwicklermaschine.
10. **Historien-Altlast:** zwei DB-Sicherungen (37,0 + 40,8 MB) liegen weiterhin
    in der Git-Historie. Nach Owner-Feststellung ohne vertrauliche Inhalte →
    `non-sensitive repository hygiene finding`, kein Rewrite, kein Force-Push.

## 5. Was dieser Bericht nicht behauptet

- Kein Anspruch auf produktive Einsatzreife.
- Kein Nachweis fachlicher Korrektheit der KI-Vorschläge — dafür fehlt ein
  Goldstandard (`not-measurable-with-current-gold-standard`).
- «pass» heisst: der genannte Test lief in diesem Lauf und war grün. Es heisst
  nicht, dass der Bereich fachlich vollständig geprüft ist.
- Die Live-Kategorien sind **nicht** Teil des grünen Status.

## 6. Abschlussstatus

```text
EVAL3_FINAL_01_GATE_GREEN
MVP_TECHNICALLY_VERIFIED_WITH_DOCUMENTED_LIMITATIONS
NO_LIVE_PROVIDER_VERIFICATION_IN_THIS_RUN
```

Eingefroren als Tag **`EVAL3-FINAL-01`** auf `stabilize/eval3-final-01`.
`main` unverändert, kein Merge, nichts gepusht.
