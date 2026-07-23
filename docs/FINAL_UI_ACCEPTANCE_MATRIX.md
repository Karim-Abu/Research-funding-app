# Finale UI-Akzeptanzmatrix (RUN 4)

Stand: 23. Juli 2026
Scope: RUN 4A (Informationsarchitektur/Copy/ruhige Standardansichten) +
RUN 4B (Schreibassistent, visueller Diff, Versionen/Undo, Browser-E2E).
Konvention wie `E2E_ACCEPTANCE_MATRIX.md`: `passed` / `blocked` / `not_run` /
`pending` / `partial`.

Diese Matrix ergänzt die RUN-3-Matrix, sie ersetzt sie nicht. Die
RUN-3-Statuswahrheit bleibt unverändert (`RUN_3_TECHNICALLY_PARTIALLY_ACCEPTED`,
`COMBINED_LIVE_E2E_BLOCKED_BY_PROVIDER_TIMEOUT`; LIVE-02B/-02C/-03 `blocked`,
Browser-01 gesamthaft und HUMAN-01 `pending`).

## RUN 4A (UI-Review bestanden am 23.07.2026)

| ID | Punkt | Status | Nachweis |
|---|---|---:|---|
| UI4A-01 | Import kompakt + reversibel (RUN-2B-Aktionen) | `passed` | `docs/RUN_4A_UI_REVIEW.md` §2, `test/import-review.test.tsx`, `review-evidence/import-*.png` |
| UI4A-02 | Quellen nach Zweck gruppiert (nur kanonische Metadaten) | `passed` | `test/sources-view.test.ts`, `test/source-table.test.tsx`, `quellen-1440x900.png` |
| UI4A-03 | Anforderungs-Statussprache + offizielle Regelquelle | `passed` | `test/requirements.test.ts`, `test/live-requirements.test.tsx` |
| UI4A-04 | Evidenz-Supportleiter sichtbar + verständlich | `passed` | `test/live-evidence.test.tsx`, `test/support-status-badge.test.tsx` |
| UI4A-05 | Marktvergleich ehrlich (complete/limited/insufficient) | `passed` | `test/market-comparison-section.test.tsx` |
| UI4A-06 | Qualitätsübersicht: 4 Kennzahlen + max. 10 Aufgaben | `passed` | `test/live-review.test.tsx`, `test/fix-queue.test.tsx`, `review-1440x900.png` |
| UI4A-07 | Recherche konsolidiert, keine Roh-Enums/Scores | `passed` | `test/public-research-panel.test.tsx` |
| UI4A-08 | A11y-Grundstruktur (Fokus, Dialoge, h1, Tab-Reihenfolge) | `passed` | `docs/RUN_4A_UI_REVIEW.md` §9 |

## RUN 4B — Schreibassistent

| ID | Punkt | Status | Nachweis |
|---|---|---:|---|
| UI4B-01 | Kopf: Feldname, Portalfrage, Status, Limit, Version, EINE Primäraktion | `passed` | `test/live-editor.test.tsx` (portal-question), `draft-workspace-shell.tsx` |
| UI4B-02 | Modi «Klarer formulieren / Fehlende Innolink-Punkte ergänzen / Kürzen» | `passed` | `e2e/run4b-editor.spec.ts` (EDITOR-01), `live-editor.tsx` |
| UI4B-03 | Zwei-Spalten Desktop / gestapelt mobil, Zeichenzahl + Limitstatus beidseitig | `passed` | `suggestion-review-dialog.tsx`, `docs/assets/run4b/editor-zweispalten-*.png` (1440/768/390) |
| UI4B-04 | Diff: bestehende Logik, Ergänzungen/Kürzungen/Umformulierungen, nie nur Farbe | `passed` | `test/diff.test.ts`, `test/suggestion-review-dialog.test.tsx` |
| UI4B-05 | Screenreader-Diff-Zusammenfassung (`aria-live`) | `passed` | `summarizeDiff` + `test/suggestion-review-dialog.test.tsx` (diff-sr-summary) |
| UI4B-06 | Ehrliche Zustände inkl. «Vorschlag wird erzeugt» und 9 Stale-Klartexten | `passed` | `test/redraft.test.ts` (staleReasonLabel), `test/live-editor-a2.test.tsx` |
| UI4B-07 | «Fehlende Angaben» primär: Titel/warum/Innolink-Punkt/nächste Aktion, keine IDs | `passed` | `test/suggestion-review-dialog.test.tsx`, E2E-EDITOR-01 |
| UI4B-08 | Belege: «Dieser Vorschlag verwendet N geprüfte Belege.» + Details; Read-Pfad ehrlich | `passed` | `test/suggestion-review-dialog.test.tsx`, E2E-EDITOR-01 |
| UI4B-09 | Whole Accept → genau EINE neue DraftVersion | `passed` | E2E-EDITOR-02 (real, Fake-Provider) |
| UI4B-10 | Replay erzeugt keine zweite Version (`idempotent_replay`) | `passed` | E2E-EDITOR-02 (fester Idempotency-Key) |
| UI4B-11 | Herkunft «Aus KI-Vorschlag übernommen» (nur bei verifizierter Provenienz) | `passed` | `versionOriginLabel` + E2E-EDITOR-02 |
| UI4B-12 | Stale/failed nicht übernehmbar; benannte nächste Aktion (Regenerate) | `passed` | E2E-EDITOR-03 (real: fail-closed nicht angeboten; Fixture: Accept blockiert) |
| UI4B-13 | Versionshistorie + Wiederherstellen über bestehenden Versionspfad | `passed` | `backend/tests/test_draft_versions.py`, `test/live-editor-versions.test.tsx`, E2E-EDITOR-02, golden-path 11a |
| UI4B-14 | Provider-Fehler ehrlich, NIE Demo-Fallback | `passed` | E2E-EDITOR-04, `test/live-editor-a2.test.tsx` (Reason-Codes) |
| UI4B-15 | Markt im Editor: Status + Quellenzahl + max. 3 Findings + Link, keine 2. Analyse | `passed` | `test/live-market-comparison.test.tsx`, E2E-MARKET-01 |
| UI4B-16 | Teilübernahme: manifestgebunden strikt Vollübernahme; Legacy über Server-PATCH | `passed` | `test/suggestion-review-dialog.test.tsx` (whole_suggestion_only), Owner-Entscheid B |
| UI4B-17 | Keine technische KI-Sprache im Hauptfluss (Manifest/Provider/Prompt nur Details) | `passed` | `test/suggestion-review-dialog.test.tsx`, `test/import-review.test.tsx` |
| UI4B-18 | A11y: Fokus auf Sheet-Titel, tabpanel-Verknüpfung, aria-live Pending | `passed` | `test/live-editor-context.test.tsx`, `test/suggestion-review-dialog.test.tsx` |

## Browser-E2E (offline, Fake-Provider/Fixtures — keine externen Calls)

| ID | Fluss | Status | Nachweis |
|---|---|---:|---|
| E2E-EDITOR-01 | Feld → Modus → Vorschlag → Original/Vorschlag + Missing Inputs + Belege | `passed` | `e2e/run4b-editor.spec.ts` |
| E2E-EDITOR-02 | Whole Accept → 1 Version → Replay ohne zweite Version → Restore | `passed` | `e2e/run4b-editor.spec.ts` |
| E2E-EDITOR-03 | Stale: fail-closed nicht angeboten (real) + Accept-Block mit Klartext (Fixture) | `passed` | `e2e/run4b-editor.spec.ts` |
| E2E-EDITOR-04 | Provider unavailable → ehrlicher Fehler, kein Demo-Fallback | `passed` | `e2e/run4b-editor.spec.ts` |
| E2E-MARKET-01 | Zentrales Artefakt, limited ehrlich, 3-Findings-Cap, keine 2. Analyse | `passed` | `e2e/run4b-editor.spec.ts` |
| E2E-FLOW-01 | Import → … → Export (golden-path) + Versionshistorie-Schritt | `passed` | `e2e/golden-path.spec.ts` (Schritt 11a) |

## Gates (RUN-4B-Abschluss)

| Gate | Ergebnis |
|---|---|
| `corepack pnpm lint` | `passed` |
| `corepack pnpm exec tsc --noEmit` | `passed` |
| `corepack pnpm test` | `passed` (76 Dateien / 561 Tests) |
| `corepack pnpm build` | `passed` |
| `playwright test --workers=1` (volle Suite) | `passed` (53 passed, 5 skipped [opt-in], 0 failed) |
| `scripts/verify_all.ps1` (einmal, Abschluss) | siehe `RUN_4_RESULT.md` §6 |

## Offene Final-Acceptance-Punkte (unverändert ehrlich)

- LIVE-02B / LIVE-02C / LIVE-03: `blocked` (externer `provider_timeout`, RUN 3).
- HUMAN-01 humane Qualitätsbewertung: `pending`.
- Live-/NDA-Produktionsabnahme: nicht Teil von RUN 4; keine Live-Abnahme behauptet.
- Contract-Notizen (dokumentiert, kein Blocker): `severity` fehlt in
  `missing_inputs`; Read-Pfad liefert keine Beleg-Details für gespeicherte
  Vorschläge (UI behandelt beides ehrlich).
