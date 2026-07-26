---
title: "Finale Integrations-Baseline"
date: 2026-07-26
commit: 7f09c1f
branch: stabilize/eval3-final-01
status: clean
tags: [eval3, baseline, integration, reproducibility]
---

# Finale Integrations-Baseline

Ausgangszustand des Abschlusslaufs, erhoben **vor** allen Final-Gates.

## 1. Pflichtfelder

| Feld | Wert |
|---|---|
| Branch | `stabilize/eval3-final-01` |
| Commit vor Finalisierung | `7f09c1f` — *feat: Enhance market comparison tests and reliability view model* |
| Working Tree | **clean** (`git status --porcelain` leer; `git diff --check` sauber) |
| Markt-UI-Stand | integriert über `aedee80` (Refactor) + `7f09c1f` (Tests/Viewmodel), zusammen 15 Dateien, +1204 / −501 |
| Datum/Uhrzeit | 2026-07-26, lokal Europe/Zurich |
| Node | v24.16.0 |
| pnpm | 11.5.3 (via corepack) |
| Python | 3.13.6 (`backend/.venv`) |
| Betriebssystem | Windows 11 Pro, Build 10.0.26200 |
| Datenbankmodus | Tests: temporäre SQLite je Lauf; Gate-E2E: Wegwerf-DB `backend/var/verify_e2e.db`; `backend/app.db` unangetastet |
| Provider-Modus | deterministisch / fake (`AI_EVAL_MODE=off`, Fake-Adapter) |
| reale Provider aktiviert | **nein** |
| verwendete Testdaten | synthetisch / öffentlich (Demo-Seed `--reset --evaluation`) |
| vertrauliche Daten | **nein** |

## 2. Commits auf dem Branch (gegen `main`)

| Commit | Inhalt |
|---|---|
| `068603f` | Preiskatalog `claude-haiku-4-5-20251001`; vier Tests auf Katalog-Modell-IDs armiert |
| `cf668c9` | Halluzinationsschutz: technische Kennungen aus der Erlaubt-Basis (`_facts_only`) |
| `d548320` | `test_demo_seed`-Isolationsguard auf eigener Wegwerf-DB |
| `b1721a6` | Golden Path prüft den Status am Badge statt am Fliesstext |
| `c67b857` | Stabilisierungs-Findings und Laufartefakte |
| `aedee80` | Markt-Komponenten refaktoriert |
| `7f09c1f` | Markt-Tests und Reliability-Viewmodel |

`main` bleibt unverändert; kein Merge, nichts gepusht.

## 3. Hygiene-Prüfungen

| Prüfung | Ergebnis |
|---|---|
| `git diff --check` | sauber |
| Secretscan über den Branch-Diff (`sk-`, `fc-`, `*_API_KEY=`, Bearer) | **keine Treffer** |
| `.env`-Dateien im Commit | **keine** |
| DB-Dateien im Arbeitsbaum getrackt | **keine** (`*.db`, `app.db.bak-*` ignoriert) |
| Rohlogs / Build-Artefakte committet | keine; `.next/`, `backend/var/` ignoriert |
| unversionierte Dateien | nur beabsichtigte Evaluationsartefakte |
| gelöschte Dateien | keine offenen Löschungen |

### Altlast in der Historie — `non-sensitive repository hygiene finding`

Zwei ältere DB-Sicherungen liegen bereits auf `origin/main`:
`backend/app.db.bak-2026-07-23` (37,0 MB, `30f6ded`) und
`backend/app.db.bak-market-runid-2026-07-24` (40,8 MB, `8416914`).

**Owner-Feststellung:** keine vertraulichen oder personenbezogenen Daten, keine
Secrets, keine realen Partner-/Projekt-/NDA-Daten. Entscheidung entsprechend:

- **kein** History-Rewrite, **kein** `git filter-repo`, **kein** Force-Push,
- bestehende Commit-Hashes bleiben gültig — auch die in
  [[EVAL3_TECHNICAL_VERIFICATION]] zitierten.

Der Vollständigkeit halber die Beobachtung aus den Dateien selbst: 6 Projektzeilen
tragen das Feld `data_classification = confidential/real_project`, 1 weitere
`public/real_project`. Nach Owner-Feststellung handelt es sich dabei nicht um
reale vertrauliche Inhalte; das Feld ist ein Klassifikationsmerkmal des
Datensatzes, keine Inhaltsprüfung.

Zukünftige DB-Dateien sind über `backend/.gitignore` (`*.db`, `*.db.bak*`,
`app.db.bak-*`) ausgeschlossen — die frühere Regel griff nicht, weil die
Sicherungen auf einen Zeitstempel enden statt auf `.db`.

## 4. Geltungsbereich

- EVAL3-PRE-01 (`docs/evaluation/generated/`) und historische MVP-Abnahmen
  werden **nur gelesen**, nie verändert.
- Keine realen Provider-Aufrufe; die vier env-gated Smokes bleiben `blocked`.
- Kein neuer fachlicher Scope; die 64 Contract-Gates und die parallelen
  KI-Textvarianten bleiben bewusst unimplementiert.

Weiter: [[MARKET_UI_FINAL_VERIFICATION]] · [[F25_DASHBOARD_FLAKE_ANALYSIS]] ·
[[MVP_REQUIREMENT_BASELINE]] · [[EVAL3_FINAL_01_REPORT]]
