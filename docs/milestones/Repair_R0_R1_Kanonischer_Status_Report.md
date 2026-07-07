# Repair-Milestones R0 + R1 — Gates, Baseline & Kanonischer Status

**Scope:** Abschluss von R0 (Gates & Fundament: Gate-Report-Vorlage, Testdaten-CI-Marker-Check,
F1-Goldfall, Baseline-Messung) und vollständige Umsetzung von R1 (kanonischer Status &
Legacy-Mock-Abbau) gemäss Prompt-Pack `claude_code_prompt_pack_innolink_repair_v2.md` und
`docs/repair/roadmap-v2.md`. Ein Prompt = ein Commit. Kein neues Produkt-Feature — Ziel ist
Statuswahrheit: **eine Blocker-Zahl, überall**.

## Branch / Commit-Basis

- Branch **`repair-v2`**, abgezweigt von `f52363d` (Stand `spike-innolink-pdf`).
- Tags: **`pre-repair-v2`** auf `a10ac17` (letzter Commit vor den Repair-Dokumenten,
  retroaktiv), **`repair-r0-done`** auf `1fb2c83`, **`repair-r1-done`** auf diesem Stand.
- Lokales `main` per Fast-Forward auf `origin/main` (`71e9c6e`, PR #8) gebracht —
  Merge-Base von `repair-v2` zu `main` ist damit `a10ac17`; Slice-Diffs gegen `main`
  funktionieren wieder. **Kein Push** (wartet auf Owner-GO).

## Commits (ein Prompt = ein Commit)

| Commit | Prompt | Inhalt |
|---|---|---|
| `f52363d`/`3b8e6d9` | Preflight | `.gitignore`: `private_inputs/` (Testdaten-Policy E-12) + Evaluation-Laufzeitlogs untrackt (blockierten Branch-Wechsel) |
| `a790790` | R0.2 | PDF-Gate-Report-Vorlage (`docs/evaluation/pdf-import-gate-report.md`), Entscheid E-01 bleibt beim Owner |
| `e4a2e97` | R0.4 | Testdaten-CI-Marker-Check (`scripts/check_testdata_markers.py` + verify_all-Gate + 7 Selbsttests) |
| `499d5d3` | F1 | Goldfall QUALIMON final (Owner-geliefert, Ergänzungen A–C, Owner-approved) |
| `1fb2c83` | R0.3 | Baseline-Messung (`scripts/baseline_f1.py`, `docs/evaluation/baseline-report.md`, Rohdaten-JSON) |
| `339a3a7` | R1.1 | Legacy-Mock-Inventar (`docs/repair/r1-legacy-mock-inventory.md`, 16 Stellen, 3× toter Code) |
| `acb5c02` | R1.2 | `ReviewStatusView` Backend (additiv, read-only, wiederverwendete Zählprimitiven) |
| `04cf23d` | R1.3 | Alle vier Screens lesen den Status-View; Paritätstest (`e2e/status-parity.spec.ts`) |
| `bcb03fc` | R1.4 | CI-Guard `check_legacy_status_paths.py` + verify_all-Gate |
| `5575c5e` | R1.3-Fix | Fehlende Next.js-Proxy-Route `app/api/runs/[id]/review/status/route.ts` (Paritätstest erreichte das Backend nicht) + Milestone-Doc-Entwurf |
| `9904f3a` | Bugfix (vorbestehend) | `e2e/demo-dataset.spec.ts` an ehrliche Herkunfts-Badges angepasst (Alt-Badge war hartkodiert «Strukturvorlage», seit Owner-Commit `2b455a4` dynamisch) |
| `5622e9e` | Bugfix (vorbestehend) | Quellen-Seite löst die im Backend gespeicherte Projektklasse auf statt Dauer-Fallback «confidential» (State-Resolution, kein Policy-Downgrade) |

## Kernverhalten

### R0 — Messbarkeit vor Reparatur
- **Baseline am Goldfall F1 (QUALIMON):** Die Statuszahl-Divergenz ist reproduziert und
  dokumentiert — Dashboard **0** / Anforderungen **2** Blocker-Issues / Qualitätsprüfung
  **18** / Zuverlässigkeits-Kacheln **12** / Export **18** für denselben Projektzustand;
  72 offene Findings verteilen sich auf 20 Meldungstexte (grösste Gruppe 31× identisch).
  Details: `docs/evaluation/baseline-report.md`. Zwei unabhängige Läufe, identische Zahlen.
- **Testdaten-Gate:** Marker-Katalog + Allowlist (Begründungspflicht) in
  `docs/evaluation/testdata-policy.md`, durchgesetzt in verify_all (fail-closed bei kaputter
  Policy). Katalog initial leer (TODO Owner).

### R1 — Eine Blocker-Zahl, überall
- **Backend (R1.2):** `GET /runs/{id}/review/status` liefert den kanonischen Status
  (blocker/warning/human_review_count, stale, approval_status, package_version,
  per_area_counts, last_reviewed_at). Zahlen kommen aus exakt denselben Funktionen wie das
  ReviewPackage (`review/package.py::counts`/`approval_status`) — keine parallele Zähllogik.
  Read-only, additiv, keine Migration, bestehende Endpoints unverändert.
- **Frontend (R1.3):** Ein Status-Client (`lib/status.ts`) + `CanonicalStatusBadge`.
  Dashboard-Karten zeigen die kanonische Blocker-Zahl (statt der `run_stopped`-Heuristik,
  die inhaltliche Blocker versteckte); Anforderungen/Qualitätsprüfung/Export betten dasselbe
  Badge ein. Präzisierung statt Widerspruch: der Anforderungen-Footer sagt jetzt
  «N blockierende Anforderungen» (Teilmenge), nicht «N Blocker». Stale einheitlich:
  **«Prüfung nicht aktuell»**. `openBlockerCount`-Prop des Mock-Export-Screens ist
  deprecated (eine Version).
- **Guard (R1.4):** Neue `isMock("legacy")`-Aufrufe ausserhalb der drei dokumentierten
  Demo-only-Dateien lassen verify_all fehlschlagen; der Paritätstest ist gegen Löschen/
  Aushöhlen geschützt.

## Datenschutz-/Governance-Bezug (manueller Security-Sweep)

Der Diff berührt `backend/app/review/*` (Governance-Pfad). Geprüft:
- `backend/app/security/*`: **unverändert** (Do-not-touch eingehalten).
- `finding_code`-Formate, Zweig-Semantik `rules/handlers.py`, Node-Reihenfolge
  `runs/graph.py`, Contract-WERTE: **unverändert** (Diff-Nachweis: keine dieser Dateien im
  Slice-Diff).
- Scope-Hash-Bestandteile in `review/package.py`: **unverändert** — `read_status_view`
  liest nur (`compute_scope_hash`/`counts`/`approval_status` werden aufgerufen, nicht
  verändert).
- Neuer Endpoint: `require_session` + Workspace-Scoping (`_require_run`), read-only,
  liefert **nur Zählwerte/Statuscodes — keine Draft-Texte, keine Quelleninhalte**.
- Keine neuen Logs mit Rohinhalten; CI-Skripte lesen nur Fixture-/Quelldateien lokal.

## Tests

- **Backend neu:** `test_review_status_view.py` (6: Parität mit ReviewPackage,
  Platzhalter-Blocker zählt genau 1, stale nach Draft-Edit + Rücksetzung nach Recheck,
  leeres Package 0-Counts, per_area/human_review, Read-only-Stabilität),
  `test_testdata_marker_check.py` (7), `test_legacy_status_guard.py` (6).
- **Frontend neu:** `test/canonical-status.test.tsx` (4: Zahl, Stale-Wortlaut, 0-Fall,
  Parität zweier Einbettungen).
- **E2E neu:** `e2e/status-parity.spec.ts` — X Blocker identisch auf Dashboard,
  Anforderungen, Qualitätsprüfung, Export; nach Feld-Edit einheitlich «Prüfung nicht
  aktuell». **Dauerhaftes Merge-Gate**, vom R1.4-Guard gegen Entfernen geschützt.
- Keine Tests deaktiviert, geskippt oder abgeschwächt (Diff-Prüfung; die `s`-Marker der
  Backend-Suite sind vorbestehende Conditional-Skips der Real-Provider-Smokes).

## Verifikation (verify_all.ps1, wörtlich)

Lauf vom 2026-07-07 (nach den beiden Fix-Commits `9904f3a`/`5622e9e`), Exit-Code 0.
Backend-pytest komplett grün (die `s`-Marker sind vorbestehende Conditional-Skips
der Real-Provider-Smokes), vitest 210/210 (49 Dateien), Playwright 31/31
(inkl. neuem Paritätstest), API-Smoke 18/18. Summary-Block wörtlich:

```text
================ M10 VERIFICATION SUMMARY ================
backend tests            : pass
migration                : pass
frontend tests (vitest)  : pass
build/typecheck/lint     : pass
Playwright               : pass
API smoke                : pass
export smoke             : pass   (test_m10_smoke.py::test_export_all_types)
no-raw-log               : pass   (test_m10_smoke.py::test_no_raw_log)
testdata markers         : pass   (scripts/check_testdata_markers.py)
legacy status guard      : pass   (scripts/check_legacy_status_paths.py)
evaluation summary       : C:\Users\karim\OneDrive - FHNW\Documents\Bachelorthesis\App\Reasearch-funding-app\backend\var\evaluation\EvaluationRunSummary.json
=========================================================
ALL GREEN
```

## Offene Punkte / Follow-ups

- **E-01 (PDF-Gate):** Original-PDF liegt lokal in `private_inputs/` (nie ins Repo);
  R3.GATE-Testlauf + Owner-Entscheid stehen aus. Ohne Entscheid gilt Default R3'.
- **R0.1-Restlücke:** die vier `docs/security/privacy-ai-security-*.md`-Vorlagen und
  `docs/repair/prompt-pack-audit.md` existieren nirgends — Owner liefert nach oder
  akzeptiert die Lücke (R9.7 referenziert sie).
- **R2.6-Voraussetzung:** Message-Katalog (`docs/repair/message-catalog.md`) muss vom
  Owner freigegeben vorliegen, sonst Stopp in R2.6. R2.7 braucht Registry-Metadaten
  (source_ref/last_checked) vom Owner.
- **Marker-Katalog** (R0.4) ist initial leer — Owner trägt reale Partnernamen/Codenamen nach.
- **Toter Code** (`lib/api.ts`: `redraftField`, `patchSection`, `acceptSuggestion`) —
  Entfernung als separater Aufräum-Commit empfohlen (P2).
- Baseline-Beobachtungen 2/4/5 (Stale-Sprünge beim Recheck, technische Feldlabels in
  Meldungen, gerundete Budget-Meldungen) sind notiert, nicht gefixt — Adressierung in
  R2 (Meldungen) bzw. R6 (Statusleiter).
- **Kein Push** von `repair-v2`/`main`/Tags ohne Owner-GO.

## Einordnung (ohne Überclaims)

Dieser Slice stellt Statuswahrheit her und macht Reparaturwirkung messbar (Baseline).
Er verbessert **nicht** die inhaltliche Qualität der Findings (Dedupe/Fix-Queue folgt in
R2), erzeugt keine KI-Inhalte und trifft keine Aussagen zur Förderfähigkeit. Kopieren
bleibt fail-open und wird nur protokolliert.
