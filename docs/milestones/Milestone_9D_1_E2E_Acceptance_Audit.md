# Milestone 9D.1 — E2E Acceptance Audit

Branch `fix/m9d-e2e-acceptance` (from `73754c8`, "Milestone 9D"). Recorded with the
backend (uvicorn :8000) + frontend (live :3000) running, `pnpm exec playwright test
--workers=1`.

## Precondition results

| Check | Result |
| --- | --- |
| Backend `pytest` | **353 passed, 3 skipped** |
| Frontend `pnpm test` (vitest) | **108 passed** |
| `pnpm lint` | 0 errors |
| `pnpm exec tsc --noEmit` | 0 errors |
| `pnpm build` | success (after removing a stale `.next` dir — see note) |
| Playwright `--workers=1` | **6 passed, 4 failed** (demo skipped) |

**Build note:** the first `pnpm build` failed with `EPERM: operation not permitted,
unlink '.next\…\evidence-links\route'` — a stale `.next` directory locked by a
prior dev server / OneDrive sync, **not** a code error. Removing `.next` and rebuilding
succeeds. No code change required.

All Playwright failures are **selector drift from the UX-stabilization branch
(`c3abd84`)** — none are M9D regressions, real UI regressions, backend/API regressions,
or concurrency issues. M9D's changed files do not touch the sources page, review center,
Innolink navigation, or the dashboard.

## Failures and fixes

### 1. `e2e/source-ingestion.spec.ts` (2 tests) — selector drift
- **Failing action:** `getByRole("button", { name: "Text als Quelle hinzufügen" })`
  (60s timeout, element not found).
- **Current UX:** the sources page redesign replaced the single button with source-way
  cards. The text path is a card button **"Text einfügen"** → dialog "Text einfügen" with
  labels **"Titel der Quelle"** / **"Textinhalt"** → submit **"Als Quelle hinzufügen"**.
- **Root cause:** the old button label was removed by `c3abd84`
  (`git show c3abd84:components/quellen/source-table.tsx | grep "Text als Quelle" = 0`).
- **Fix:** updated both tests to the current dialog flow (role/label/accessible-name
  locators). The intake → `/quellen` flow and the "Verarbeitet" status are unchanged.

### 2. `e2e/review-recheck-approval.spec.ts:85` — strict-mode collision
- **Failing action:** `getByRole("heading", { name: "Qualitätsprüfung" })` resolved to
  **2** elements: `h1 "Qualitätsprüfung"` (page title) + `h2 "Qualitätsprüfungen"`
  (a new sub-section added by the redesign).
- **Root cause:** non-exact accessible-name matching substring-matches both headings.
- **Fix:** `{ name: "Qualitätsprüfung", exact: true }` on both occurrences — targets the
  page title without weakening the review-content assertions.

### 3. `e2e/portal-transfer.spec.ts:84` — moved navigation
- **Failing action:** `getByRole("link", { name: /Innolink-Übernahme/ })` (60s timeout).
- **Current UX:** the Export Center redesign turned the Innolink view into an **inline
  tab** ("Innolink-Kopieransicht"); `openInnolink()` switches the tab (no navigation to
  `/portal-transfer`). The embedded `PortalTransfer` omits its `h1` (it lives under the
  tab) and renders the section groups + a coverage panel `h2 "Abdeckung der
  Übernahmeansicht"`.
- **Root cause:** the separate `/portal-transfer` link/route nav was replaced by an
  in-page tab.
- **Fix:** click the tab `getByRole("tab", { name: "Innolink-Kopieransicht" })`, drop the
  `/portal-transfer` URL assertion, and assert the inline coverage-panel heading. The
  field-order / copy-only-content / warnings / coverage assertions are unchanged.

### 4. `e2e/demo-dataset.spec.ts` (seeded, run with `DEMO_DATA_ENABLED=true`) — dashboard + tabbed-editor + requirements drift
This spec is `test.skip` without `DEMO_DATA_ENABLED`, so it was not in the default
precondition run; it fails for the same UX-drift class:
- **Dashboard:** the project-card primary action is now a single **"Weiterarbeiten"**
  button (was per-`next_action` labels "Entwurf weiterbearbeiten" / "Analyse …"). Fix:
  assert ≥2 "Weiterarbeiten" buttons; the per-project `next_action` distinction is still
  asserted via the API.
- **Editor evidence panel:** the right panel is now **tabbed** (Markt / Belege /
  Kommentare); the default tab is not always "Belege". Fix: open the **"Belege"** tab
  before asserting the `/Verkn/` linkage section (active links remain API-verified).
- **Requirements page:** per-requirement status is now a **bucket badge** (Erfüllt /
  Teilweise / Offen / Blocker) and the blocked state shows a blocker-aware footer
  ("… Blocker verhindern aktuell den nächsten Schritt"). The labels "Blockiert" /
  "Angaben" are no longer rendered. Fix: assert the blocker-only footer text `/verhinder/`.

## Stabilization (STEP 3)

Parallel Playwright (`pnpm exec playwright test` with multiple workers) shows **transient
failures** (e.g. `source-ingestion` 201/timeout) because all live E2E specs mutate **one
shared local SQLite database** (single-writer contention) — a local test-infra
limitation, not application logic. Set **`workers: 1`** in `playwright.config.ts` so the
default run is serial and deterministic; the suite is green serially. No app code was
serialized or changed to "hide" a race — only the local test runner.

## M9D verification mapping (STEP 4)

| STEP-4 point | Covered by |
| --- | --- |
| Only Solution & Innovation has AI suggestion UI | vitest `test/live-editor-a2.test.tsx` (control only on SOL) |
| create suggestion → unavailable when cloud blocked | e2e `a2-solution-innovation.spec.ts` (503), vitest unavailable state |
| safe unavailable UI is understandable | vitest renders "…nicht verfügbar" |
| no A2 controls on other fields | vitest (no control on Abstract) |
| no model/provider names | dialog/component carry none; vitest |
| accepting covered by backend/unit tests | `backend/tests/test_a2_redraft_api.py` (DB cloud fixture) |

A robust editor-navigation UI Playwright test was **not** added: the behaviours are fully
covered by the above, and editor field-navigation against redesigned labels would risk a
flaky spec — contrary to this milestone's stabilization goal.

## Result

After the fixes, the full Playwright suite is **green in serial mode** (10 passed + the
seeded demo). No old UX labels were reintroduced; M9D safe-unavailable behaviour and the
SOL-only AI scope are intact.
