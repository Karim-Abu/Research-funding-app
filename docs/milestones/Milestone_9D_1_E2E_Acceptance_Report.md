# Milestone 9D.1 — E2E/UX Test Alignment, M9D Acceptance Hardening & A2 Availability Clarification

## Basis

- Branch **`fix/m9d-e2e-acceptance`**, created from **`73754c8`** ("Milestone 9D:
  Solution Innovation"), which sits on top of the UX-stabilization commits
  (`c3abd84`, `8cbde77`) and M9C (`474ecc0`). Working tree clean at start.
- **Not a feature milestone.** No A2 behaviour change, no M9E, no A3, no new contracts/
  endpoints/UI. Only Playwright spec alignment + the serial test config + documentation.

## Failing specs found (precondition record)

`pnpm exec playwright test --workers=1` (backend + live frontend running): **6 passed, 4
failed** (demo skipped). All 4 failures are **selector drift from the UX-stabilization
branch (`c3abd84`)** — verified not to be M9D regressions (M9D's changed files don't touch
the sources page, review center, Innolink nav or dashboard). A 5th spec
(`demo-dataset`, `test.skip` without `DEMO_DATA_ENABLED`) fails for the same drift class.

| Spec | Failing locator/action | Root cause |
| --- | --- | --- |
| `source-ingestion.spec.ts` (×2) | button "Text als Quelle hinzufügen" | button removed by the sources redesign |
| `review-recheck-approval.spec.ts` | heading "Qualitätsprüfung" → 2 matches | new `h2 "Qualitätsprüfungen"` |
| `portal-transfer.spec.ts` | link "Innolink-Übernahme" | Innolink is now an inline export tab |
| `demo-dataset.spec.ts` (seeded) | button "Entwurf weiterbearbeiten"; `/Verkn/`; `/Blockiert\|Angaben/` | unified "Weiterarbeiten" card action; tabbed evidence panel; bucket badges + blocker footer |

Backend/unit/build/lint/typecheck were green at the precondition (the first `pnpm build`
failed once on a stale `.next` lock — `EPERM unlink` — fixed by removing `.next`, not a
code issue). Full per-failure detail in `Milestone_9D_1_E2E_Acceptance_Audit.md`.

## Fixes made (current UX, role/name locators)

- **source-ingestion:** drive the current text-source dialog — card button **"Text
  einfügen"** → labels **"Titel der Quelle"** / **"Textinhalt"** → submit **"Als Quelle
  hinzufügen"**.
- **review:** `getByRole("heading", { name: "Qualitätsprüfung", exact: true })` (page
  title) — resolves the strict-mode collision without weakening content checks.
- **portal-transfer:** open the **"Innolink-Kopieransicht"** export tab (inline; no
  `/portal-transfer` navigation) and assert the coverage panel **"Abdeckung der
  Übernahmeansicht"**; the field-order / copy / warnings / coverage assertions are kept.
- **demo-dataset:** assert ≥2 **"Weiterarbeiten"** card actions (per-project `next_action`
  still asserted via the API); open the **"Belege"** editor tab before the `/Verkn/`
  linkage check (active links still API-verified); assert the blocker-only footer
  `/verhinder/` ("… Blocker verhindern aktuell den nächsten Schritt") for the blocked
  project.

No old UX labels were reintroduced; no arbitrary sleeps or unjustified `first()` were
added (existing `.first()` calls were retained where the original test already used them).

## Tests run and results

| Check | Result |
| --- | --- |
| `backend python -m pytest` | **353 passed, 3 skipped** |
| `pnpm test` (vitest) | **108 passed** |
| `pnpm lint` | **0 errors** |
| `pnpm exec tsc --noEmit` | **0 errors** |
| `pnpm build` | **success** (after clearing a stale `.next`) |
| `pnpm exec playwright test` (now serial) | **10 passed, 1 skipped** |
| `e2e/demo-dataset.spec.ts` (`DEMO_DATA_ENABLED=true`) | **1 passed** |

→ The full Playwright suite (10 live specs + the seeded demo = **11**) is green in the
documented reliable mode.

## Playwright serial-only due to SQLite

The live E2E specs mutate **one shared local SQLite database** (single-writer). Running
them across multiple workers causes **transient write contention** (observed: a
`source-ingestion` 201/timeout that passes serially) — a local test-infra limitation,
**not** application logic. `playwright.config.ts` now sets **`workers: 1`** (with a
documented comment) so the default `pnpm exec playwright test` is serial and deterministic.
Parallel mode can still be requested with `--workers=N`, but is **not reliable** for this
single-SQLite local setup. No application code was serialized or altered to mask a race —
only the local test runner.

## M9D runtime availability clarification

Documented in `Milestone_9D_A2_Solution_Innovation_Report.md` → **"Runtime Availability in
the Beta"**: A2.solution_innovation is implemented and covered by fake-provider +
cloud-assisted-fixture tests, but the **live beta returns a safe `503 ai_unavailable`**
because cloud processing is disabled by policy (`validate_processing_mode` → `403` for
`cloud_assisted` run creation) and A2 requires `cloud_assisted` (no silent mode upgrade).
Before real user-facing A2 can run, the deployment needs: an explicit cloud-assisted run /
field-level confirmation the policy permits; a DataClassification (public/synthetic-only)
check; the per-run external-processing confirmation route; CostGuard + an approved provider
route; and audit (CostGuard/audit are already wired). **No data-policy change was made.**

## M9D acceptance status

- M9D safe-unavailable behaviour intact (503 + calm "nicht verfügbar" UI). ✓
- A2 UI appears **only** on `SOL.INNOVATION_SOLUTION.EDITOR` (vitest + the A2 e2e
  field-scope check). ✓
- No model/provider names or AI controls on other fields. ✓
- Accepting a suggestion (cloud-assisted) is covered by `backend/tests/
  test_a2_redraft_api.py` (DB cloud fixtures). ✓
- No A3 / M9E / market-research code introduced. ✓

## Remaining limitations

- A2 is unavailable at runtime in this beta deployment by policy (the cloud/confirmation
  gate is a future milestone) — intentional and honestly surfaced.
- Parallel Playwright remains unreliable locally due to single-writer SQLite; serial is the
  supported mode. (Per-test isolated databases would be the long-term fix, out of scope.)
- The seeded-demo spec requires `DEMO_DATA_ENABLED=true` and reseeds via `app.demo.seed
  --reset` in `beforeAll` (unchanged).

## Readiness verdict for M9E (Value Creation)

The post-UX E2E suite is aligned to the current UI and green in the documented reliable
(serial) mode; backend, vitest, lint, typecheck and build are green; M9D's advisory A2
slice (createRedraft → suggestion → explicit accept → new agent DraftVersion +
recheck/approval-stale) and its safe runtime-unavailability are intact and clearly
documented. The M9D baseline is **acceptance-ready**, and the A2 field-drafting machinery
(orchestrator, context, createRedraft, accept-by-`source_operation_id`, the
SuggestionReviewDialog, the fake-provider + cloud-fixture test patterns) generalizes
directly to **M9E A2.value_creation_market_logic**. Ready for M9E.
