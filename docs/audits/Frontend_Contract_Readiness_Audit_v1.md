# Frontend Contract & Integration-Readiness Audit — v1

**Project:** Evidenzbasierte Proposal-Unterstützung für Innosuisse-Innovationsprojekte
**Audit date:** 2026-06-21
**Audit type:** Strict, read-only frontend contract & integration-readiness audit
**Auditor scope:** No application source modified. Only `docs/audits/*` and gitignored build
artifacts (`node_modules/`, `.next/`) were written.

---

## Repository state (STEP 1)

| Item | Value |
|---|---|
| Repo root | `App/Reasearch-funding-app` (inner git repo; outer `App/` is not a repo) |
| Git branch | `backend-integration` (up to date with `origin/backend-integration`) |
| Commit | `01d0fef` — "chore: remove accidentally embedded duplicate repo" |
| Git status | clean tracked tree; **only `final_backend_contracts_v1_1/` is untracked** |
| Package manager | **pnpm** (`pnpm-lock.yaml`, `pnpm-workspace.yaml`); pnpm not on PATH → run via `corepack pnpm` (v11.5.3) |
| Node | v24.16.0 |
| Next.js / React / TypeScript | **16.2.6** (Turbopack) / 19.2.4 / **5.7.3** |
| Scripts ([package.json](../../package.json)) | `dev`, `build` (`next build`), `start`, `lint` (`eslint .`) — **no `test`, no `typecheck`, no E2E** |
| Test/lint infra | **no eslint dependency**, no eslint config, no vitest/jest, no playwright |
| Expected pre-evaluation branch? | **Yes** — `backend-integration` is the integration-prep branch |

### Contract files (present; recorded SHA256 — Rule 5)

All five required contracts are present (the audit proceeds). The contract directory
`final_backend_contracts_v1_1/` is **currently untracked in git** and was neither modified nor
committed by this audit.

| File | SHA256 |
|---|---|
| `openapi-v1_1.yaml` | `c635cd7468b123e40b45c160b564a0011cb8cf0f8c4c988cce98190941cf2740` |
| `Domain_Model_v4.md` | `9445992d8b9b400f433740627118beabacc7bc399e76bf45c4a0a3d7010d6326` |
| `ADR-001_Gesamtarchitektur_v4.md` | `aae2d1ba9d59b8eb06b84ca9cc06d935bbd5228185346486cc886b0a980bc1b7` |
| `Backend_Implementation_Plan_v1_1.md` | `1e8d03cecf91ce79778c9df8e34b4df9d52b55e9daa8c2afa8afee1b4a8f9964` |
| `Final_Consistency_Audit_v1_1.md` | `2d042dbc9833b5e56b96c988a919290d3477e4bf5dd80b12a41332f134abc390` |
| `Frontend_API_Mapping_v1_1.md` | `459bd4c0637027a743fc70827907aa6f1cb56cbf85e26de6a47b03ea893b6e51` |

Contract under audit: **Innosuisse Proposal Assistant API v1.1.0** (OpenAPI 3.1.0, server base
`http://localhost:8000`, all paths under `/api/v1/`), **72 operations**.

---

## A. Executive verdicts

> Two verdicts are reported side by side (per the agreed scope). Each is **derived from the evidence
> below**, not pre-decided.

### A1 — Beta-slice readiness: **READY_WITH_P0_FIXES**

The end-to-end beta path (session → projects → sources → run/polling → requirements/evidence →
drafts → review/approval → export) rests on a **sound integration architecture**: a single typed
API seam (`lib/api.ts`), an explicit `USE_MOCKS` switch, a server-only BFF proxy
(`app/api/* → lib/bridge.ts`), 1-second run polling with correct unmount cleanup, and a German error
envelope. The production build passes and TypeScript is clean.

It is **not** ready to point at the live v1.1 backend today because a **bounded, enumerable set of P0
defects** must land first — most importantly: `USE_MOCKS` is hardcoded `true`; the BFF and DTO layer
were built against an **earlier `research-funding-mvp` backend shape, not the finalized v1.1
contract** (wrong paths/verbs, collapsed review, run-level redraft, GET-binary export); the
`DataClassification` and `RunStatus` models diverge from the contract (the latter silently breaks the
polling state machine); and there is **no real session/auth layer**. These are integration tasks on a
ready foundation — hence READY_WITH_P0_FIXES rather than NOT_READY, with the caveat that the P0 set is
medium-to-large in total effort.

### A2 — Full v1.1 UI coverage: **NOT_READY**

Beyond every A1 P0, the structured-application half of the contract has **zero UI** (confirmed by a
zero-match search across the whole frontend): `ProjectDates`, `WorkPackages`, `Milestones`,
`PlannedHours`, `BudgetPlan`, `RiskRegister`, `ApplicationStructure`, structured `Partner` CRUD, plus
admin surfaces (audit events, controls, service tests, limits, final-quality-review). ~17 contract
operations have no consumer. Full coverage requires net-new screens and is post-beta work.

---

## B. Technical test results (STEP 2)

`git status --porcelain` was captured before and after the build commands; it was **identical**
(`?? final_backend_contracts_v1_1/` only) — no tracked source/config/lockfile changed.
`node_modules`, `.next`, and `*.tsbuildinfo` are gitignored.

| # | Command | Result | Detail | Blocks integration? |
|---|---|---|---|---|
| 1 | `pnpm install --frozen-lockfile` | ⚠️ Pass w/ caveat | "Lockfile is up to date" but pnpm aborts on existing modules dir without a TTY: `ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY`. Succeeds with `CI=true` / `confirmModulesPurge=false` (391 packages, 30.6s). | No (CI-config gap) |
| 2 | `pnpm build` (`next build`) | ✅ **Pass** (exit 0) | Compiled in 6.1s; TypeScript checked; 20 static pages + 15 dynamic API routes generated. | No |
| 3 | `pnpm exec tsc --noEmit` | ✅ **Pass** (exit 0) | No type errors (`strict: true`). | No |
| 4 | `pnpm lint` (`eslint .`) | ❌ **Fail** (exit 1) | `eslint` not found — eslint is not a dependency and there is no eslint config. | No (quality/reproducibility gap — Rule 7) |
| 5 | Unit tests | ⚠️ **Absent** | No test runner/config present (not a pass). | No (quality gap) |
| 6 | Playwright / E2E | ⚠️ **Absent** | No Playwright config present. | No (quality gap) |

**Summary:** the application compiles and type-checks cleanly. There is **no functioning lint and no
automated test layer** — a quality and reproducibility gap, not a runtime blocker.

---

## C. Confirmed strengths

1. **Single typed API seam** — all data access funnels through [lib/api.ts](../../lib/api.ts); a
   single `USE_MOCKS` flag ([lib/api.ts:54](../../lib/api.ts#L54)) toggles mock vs `fetch`.
2. **Stable DTO contract layer** — [lib/backend-contract.ts](../../lib/backend-contract.ts) isolates
   wire shapes from UI types; integration changes have one obvious home.
3. **Server-only BFF (no secret leakage)** — `FASTAPI_BRIDGE_URL` is read only server-side
   ([lib/bridge.ts:36](../../lib/bridge.ts#L36)); the client speaks only relative `/api/*`. No
   `NEXT_PUBLIC_*` provider keys anywhere.
4. **Correct run-polling lifecycle** — 1s interval with `clearInterval` on unmount and on terminal
   states ([app/quellen/page.tsx:260](../../app/quellen/page.tsx#L260),
   [:267-296](../../app/quellen/page.tsx#L267-L296)).
5. **German error envelope** — `{ error: { code, message } }` normalized in `request()` with a
   bridge-unreachable fallback ([lib/api.ts:60-96](../../lib/api.ts#L60-L96)).
6. **Honest derived gating** — approval/export blocking is derived from live blocker issues
   (`countOpenBlockers`, `deriveGatesFromIssues`); gates fall back from issues rather than inventing
   results ([lib/api.ts:461-534](../../lib/api.ts#L461-L534)).
7. **Upload validation UX** — client restricts to `.txt/.md` with a rejection message
   ([components/quellen/source-table.tsx:32-37](../../components/quellen/source-table.tsx#L32-L37),
   [:248-253](../../components/quellen/source-table.tsx#L248-L253)).
8. **Mock-data models real Innosuisse rules** — seeded issues reflect real beta-profile criteria
   (char limit, 5% cash contribution, 40–60% partner quota), so the mock does not teach a false model.
9. **Debug scaffolding is gated off** — `SHOW_DEBUG_CONTROLS`/`showDebugControls` constants are
   `false` ([app/quellen/page.tsx:187](../../app/quellen/page.tsx#L187),
   [app/review/page.tsx:33](../../app/review/page.tsx#L33)).

---

## D. Findings (grouped)

**P0 — blocks backend integration (beta slice):** FE-P0-01 … FE-P0-09
**P1 — required before evaluation:** FE-P1-01 … FE-P1-08
**P2 — useful but deferrable:** FE-P2-01 … FE-P2-05
**Post-Beta:** FE-PB-01 … FE-PB-04

The single most important theme: **the integration layer targets an older `research-funding-mvp`
backend, not the finalized v1.1 contract** (see FE-P0-02..05, FE-P0-09). Repath/reshape is required
across the BFF and the typed client.

---

## E. Detailed findings

> Fields per finding: severity · file · line/component · current · expected (contract) · user impact ·
> recommended fix · effort.

### P0 — blocks backend integration

#### FE-P0-01 · `USE_MOCKS` hardcoded `true`
- **File/line:** [lib/api.ts:54](../../lib/api.ts#L54)
- **Current:** `export const USE_MOCKS = true` short-circuits every API function to in-memory mock data; the `fetch`/BFF branch is dead at runtime.
- **Expected:** A live path must be reachable (build- or env-driven) so the UI talks to the BFF → v1.1 backend.
- **User impact:** No screen is connected to real data; the app is a closed demo.
- **Fix:** Replace the constant with a build/runtime toggle (kept server-trusted; no secrets client-side); default live for integration builds.
- **Effort:** Small (switch) — but it gates all other P0s.

#### FE-P0-02 · Run start: wrong path + synchronous instead of `202` async
- **File/line:** [lib/api.ts:186-207](../../lib/api.ts#L186-L207); [app/api/runs/route.ts:6](../../app/api/runs/route.ts#L6)
- **Current:** `POST /api/runs` → BFF proxies to `/runs`; client expects synchronous `{ runId }`.
- **Expected:** `createRun` = `POST /api/v1/projects/{project_id}/runs` returning **`202 AsyncAccepted`** (`operation_id` + `poll_url`), with `409` (existing active run), `429` (cost/rate), `503` (provider) ([openapi-v1_1.yaml:937-956](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L937-L956)); requires `Idempotency-Key`.
- **User impact:** Run cannot be started against the real backend; no handling for an already-running run or cost/provider limits.
- **Fix:** Repath under the active project; consume `202` + poll the operation; send idempotency key; handle 409/429/503.
- **Effort:** Medium.

#### FE-P0-03 · Review collapsed into one call vs contract split
- **File/line:** [lib/api.ts:546-606](../../lib/api.ts#L546-L606); [app/api/runs/[id]/review/route.ts:10](../../app/api/runs/%5Bid%5D/review/route.ts#L10)
- **Current:** A single `submitReview` (`POST /api/runs/{id}/review`) applies field edits + issue decisions and re-checks in one mock call.
- **Expected:** The contract splits this into `getReview` (GET `/runs/{id}/review`), `createHumanDecision` (`/human-decisions`), `startTargetedRecheck` (`/rechecks`, **202 async**), and `createApproval` (`/approvals`, valid only for the current recheck scope) ([openapi-v1_1.yaml:1372-1475](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L1372-L1475), [:2318](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L2318)). `POST /runs/{id}/review` does **not** exist.
- **User impact:** Human decisions, targeted recheck, and approval cannot be performed against the real backend; stale-approval semantics are unrepresentable.
- **Fix:** Split the flow into the four operations; model recheck as async; gate approval on current recheck scope.
- **Effort:** Large.

#### FE-P0-04 · Draft save: wrong path, no `base_version_id`, no `409` handling
- **File/line:** [lib/api.ts:646-659](../../lib/api.ts#L646-L659); [app/api/sections/[fieldId]/route.ts](../../app/api/sections/%5BfieldId%5D/route.ts)
- **Current:** `patchSection(fieldId, text)` → `PATCH /api/sections/{fieldId}` sends only `{ text }`; no run scope, no version, no conflict path.
- **Expected:** `updateField` = `PATCH /api/v1/runs/{run_id}/fields/{field_id}` with a `DraftPatch` body carrying `base_version_id`, returning a new `draft_version_id` and **`409`** on conflict ([openapi-v1_1.yaml:1212-1251](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L1212-L1251)).
- **User impact:** Concurrent edits overwrite silently; no optimistic-concurrency safety; `recheck_required` not surfaced.
- **Fix:** Repath under run+field; send/track `base_version_id`/`draft_version_id`; handle 409 with a reload-and-merge UX.
- **Effort:** Medium.

#### FE-P0-05 · Export: GET-binary vs `POST` async draft model
- **File/line:** [lib/api.ts:673-678](../../lib/api.ts#L673-L678); [app/api/runs/[id]/export/route.ts](../../app/api/runs/%5Bid%5D/export/route.ts)
- **Current:** `exportDownloadUrl` builds `GET /api/runs/{id}/export?kind=` and downloads the binary directly; "no POST, no generating status" by design.
- **Expected:** `createExport` (`POST /runs/{id}/exports`) → `getExport` → `downloadExport` (`/exports/{export_id}/download`); export is a tracked artifact and is a **DRAFT without a valid approval** ([openapi-v1_1.yaml:1473-1539](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L1473-L1539)).
- **User impact:** Cannot create/track exports per contract; the draft-vs-final distinction (approval-gated) is lost.
- **Fix:** Move to create→poll→download; surface DRAFT watermark state when approval is absent/stale.
- **Effort:** Medium.

#### FE-P0-06 · `DataClassification` model mismatch (flat enum vs 5-field object)
- **File/line:** [lib/types.ts:45-94](../../lib/types.ts#L45-L94)
- **Current:** `DataClass = public_synthetic | public_external | internal | confidential | nda` — a single flat restrictiveness ladder driving `isCloudAllowed`/`isWebAllowed`/`mostRestrictiveDataClass`.
- **Expected:** `DataClassification` is a 5-field object — `sensitivity` (public|internal|confidential), `origin` (public_source|synthetic|anonymized|real_project), `processing_mode` (deterministic_only|cloud_assisted|local_only), `web_research_mode` (off|validated_public), `nda_applies` (bool) ([openapi-v1_1.yaml:2571-2605](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L2571-L2605)).
- **User impact:** Intake cannot capture and the run cannot transmit a contract-valid classification; client policy gating is not expressible in contract terms.
- **Fix:** Replace the flat enum with the structured object end-to-end (intake, badge, dialog, run payload); derive cloud/web gating from `processing_mode`/`web_research_mode`. Treat server `effective` classification as authoritative.
- **Effort:** Large.

#### FE-P0-07 · `RunStatus` enum mismatch breaks the polling state machine
- **File/line:** [lib/backend-contract.ts:46-53](../../lib/backend-contract.ts#L46-L53); consumed at [app/quellen/page.tsx:278-287](../../app/quellen/page.tsx#L278-L287)
- **Current:** `RunStatus = queued | running | needs_review | stopped | completed | failed`. The poll loop transitions on `completed`/`needs_review` and `stopped`/`failed`.
- **Expected:** Contract run status = `created | running | paused_for_review | completed | stopped | failed | cancelled` ([openapi-v1_1.yaml:3344-3353](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L3344-L3353)).
- **User impact:** Live `paused_for_review` is not recognized (banner never advances to review), `cancelled` is unhandled (poll loop keeps running), `created` ≠ `queued`. The progress UI desyncs from reality.
- **Fix:** Adopt the contract enum as the single source of truth; map `paused_for_review`→review CTA and `cancelled`→stopped UX; remove `queued`/`needs_review`.
- **Effort:** Medium.

#### FE-P0-08 · No session/authentication contract
- **File/line:** [app/login/page.tsx:12-33](../../app/login/page.tsx#L12-L33); [components/shell/user-menu.tsx:50-53](../../components/shell/user-menu.tsx#L50-L53)
- **Current:** Login is an explicit mock ("no real authentication, no session, no auth guard"); a `setTimeout(800)` then `router.push("/")`. "Abmelden" (logout) is a `DropdownMenuItem` with **no `onClick`** (no-op). No CSRF, no cookie, no 401 handling.
- **Expected:** `createSession` (`POST /session`, HTTP-only cookie + CSRF), `getSession`/`getCurrentUser`, `deleteSession`; mutating calls carry `X-CSRF-Token` ([openapi-v1_1.yaml:2426](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L2426)); `401` everywhere.
- **User impact:** No authentication; `/` reachable without login; logout does nothing; no session-expiry UX.
- **Fix:** Real session layer (create/get/delete), CSRF header on writes, route guard, 401 → re-login UX.
- **Effort:** Large.

#### FE-P0-09 · Integration mappers target `research-funding-mvp`, not v1.1
- **File/line:** [lib/run-steps.ts:32-56](../../lib/run-steps.ts#L32-L56), [:157-199](../../lib/run-steps.ts#L157-L199)
- **Current:** `NODE_TO_STEP_INDEX` keys on MVP node names (`intake`, `requirement_loader`, `evidence_anchor`, `hitl_review_gate`, `export`, …); `mapBackendRequirements` reads `requirement_matrix.eligibility_criteria/budget_rules` + `evidence_anchors` (MVP Pydantic shapes).
- **Expected:** v1.1 `current_stage` enum = `initialize | validate_source_snapshot | extract_facts_and_map_evidence | verify_evidence | evaluate_requirements_and_rules | draft_fields | create_template_drafts | critic_review | aggregate_review | human_review | targeted_recheck | finalize_run` ([openapi-v1_1.yaml:3356-3368](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L3356-L3368)); requirements come from `listRequirements` (`GET /runs/{id}/requirements`).
- **User impact:** Backend stages render as "Technischer Schritt: …" fallbacks; requirements mapping silently mismatches against live data.
- **Fix:** Rekey the node/stage map to `current_stage`; rewrite the requirements mapper against the `listRequirements` schema.
- **Effort:** Medium.

### P1 — required before evaluation

#### FE-P1-01 · No `202` / `operation_id` / `poll_url` async-operation handling
- **File/line:** [lib/api.ts:186-247](../../lib/api.ts#L186-L247); search: no `operation_id`/`poll_url` anywhere in frontend.
- **Current:** The mock run engine polls `getRun` directly; no concept of an `AsyncOperation`.
- **Expected:** `createRun`, `createRedraft`, recheck, export return `202 AsyncAccepted` (`operation_id`+`poll_url`) and are polled via `getOperation` (`/operations/{id}`, status `queued|running|succeeded|failed|cancelled`) ([openapi-v1_1.yaml:3425-3457](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L3425-L3457)).
- **User impact:** Async backend work cannot be tracked/cancelled correctly.
- **Fix:** Add a generic operation-poller; route async ops through it.
- **Effort:** Medium.

#### FE-P1-02 · No `EvidenceLink` / `verification_status` model
- **File/line:** [lib/backend-contract.ts:74-79](../../lib/backend-contract.ts#L74-L79); [lib/quellen-mock-data.ts:91-104](../../lib/quellen-mock-data.ts#L91-L104)
- **Current:** Only `EvidenceAnchor { anchorId, sourceTitle, location, verified }` + a UI `EvidenceCard` with `machineStatus`/`confidencePercent`.
- **Expected:** `EvidenceAnchor` **and** `EvidenceLink` (link lifecycle `active | stale | removed`) with `verification_status`; create/delete via `createEvidenceLink`/`deleteEvidenceLink` ([openapi-v1_1.yaml:1296-1341](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L1296-L1341)).
- **User impact:** Cannot link/unlink evidence to field drafts or reflect stale/removed links.
- **Fix:** Add the `EvidenceLink` DTO + link/unlink actions; render link status.
- **Effort:** Medium.

#### FE-P1-03 · No CSRF token / idempotency key on writes
- **File/line:** [lib/api.ts:76-96](../../lib/api.ts#L76-L96) (`request()` sets only `Content-Type`).
- **Current:** No `X-CSRF-Token`, no `Idempotency-Key`.
- **Expected:** Contract defines both header params ([openapi-v1_1.yaml:2426](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L2426), [:2433](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L2433)); create/mutate ops are `x-audit-required` and idempotent.
- **User impact:** Writes will be rejected (CSRF) or duplicated on retry (no idempotency).
- **Fix:** Inject CSRF from the session and a generated idempotency key on all mutating requests.
- **Effort:** Small–medium.

#### FE-P1-04 · Source lifecycle incomplete (status, delete, fake processing)
- **File/line:** [lib/quellen-mock-data.ts:9](../../lib/quellen-mock-data.ts#L9); [components/quellen/source-table.tsx:215-246](../../components/quellen/source-table.tsx#L215-L246)
- **Current:** `SourceStatus = processed | processing | error`; removal mutates local state only (no `deleteSource`); upload fakes completion via `setTimeout(1500)`.
- **Expected:** Contract source status includes **`needs_manual_input`** ([openapi-v1_1.yaml:2819](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L2819)); sources are listed/polled (`listSources`/`getSource`) and deleted (`deleteSource`).
- **User impact:** Manual-input-required sources are invisible; deletes don't persist; processing state is cosmetic.
- **Fix:** Adopt contract source status; wire list/poll/delete; replace fake completion with real status polling.
- **Effort:** Medium.

#### FE-P1-05 · Capabilities/role/service-availability not server-driven
- **File/line:** [lib/mock-data.ts:4-14](../../lib/mock-data.ts#L4-L14); [app/quellen/page.tsx:578-581](../../app/quellen/page.tsx#L578-L581)
- **Current:** `currentUser.role` is hardcoded; service availability is passed from local scenario flags.
- **Expected:** `getCapabilities` / `getServiceAvailability` provide `effective_role` and KI/web availability; UI gating follows the server ([openapi-v1_1.yaml:2538](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L2538), [:2507](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L2507)).
- **User impact:** UI role gating can disagree with the server (lead_admin-only actions shown to members, etc.).
- **Fix:** Fetch capabilities post-login; drive role/service gating from them. (UI gating is convenience; server remains authoritative.)
- **Effort:** Medium.

#### FE-P1-06 · Failure/edge states not handled
- **File/line:** poll loop [app/quellen/page.tsx:288-294](../../app/quellen/page.tsx#L288-L294) (generic catch only).
- **Current:** Errors collapse to one German message; no specific handling for 409 existing-active-run, 429 cost limit, 503 provider unavailable, policy-blocked, parsing failure, stale approval, recheck-in-progress.
- **Expected:** Contract distinguishes `409/429/503` and policy errors per operation (e.g. createRun [openapi-v1_1.yaml:949-956](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L949-L956)).
- **User impact:** Users can't tell "try later" from "cost limit" from "blocked by policy".
- **Fix:** Map contract error codes/status to distinct UI states and copy.
- **Effort:** Medium.

#### FE-P1-07 · Text/URL sources unsupported in UI
- **File/line:** [components/quellen/source-table.tsx:31](../../components/quellen/source-table.tsx#L31) (file upload only, `.txt/.md`).
- **Current:** Only file upload; no text-paste or URL-import entry points.
- **Expected:** `createTextSource` (`/sources/text`) and `importUrlSource` (`/sources/url`) with research-task confirmation UX.
- **User impact:** Two contract source types are unusable from the UI.
- **Fix:** Add text/URL source entry + URL confirmation step. (May be a deliberate beta cut — confirm scope.)
- **Effort:** Medium.

#### FE-P1-08 · No functioning lint, no automated tests (quality/reproducibility)
- **File/line:** [package.json:9](../../package.json#L9) (`lint: eslint .`, eslint absent); no test/E2E config.
- **Current:** `pnpm lint` fails (eslint not installed); zero unit/E2E tests; frozen install needs non-TTY consent.
- **Expected:** A green lint + a minimal test layer for contract-critical mapping (enums, status, version conflict).
- **User impact:** Regressions in the integration layer go uncaught; CI is not reproducible.
- **Fix (post-approval, separate change):** Add eslint (config + dep) and a small unit suite for `lib/api.ts`/mappers; set `confirmModulesPurge=false` or `CI` in CI. **Rule 7: quality gap, not a runtime blocker.**
- **Effort:** Medium.

### P2 — useful but deferrable

#### FE-P2-01 · Multiple competing status vocabularies
- **File/line:** `RunStatus` [lib/backend-contract.ts:46](../../lib/backend-contract.ts#L46); `MachineStatus`/`StepStatus` [lib/types.ts:19](../../lib/types.ts#L19),[:35](../../lib/types.ts#L35); `SourceStatus`/`ProgressStepState` [lib/quellen-mock-data.ts:9](../../lib/quellen-mock-data.ts#L9),[:63](../../lib/quellen-mock-data.ts#L63).
- **Current/Expected:** Several frontend-local status enums risk becoming a second source of truth alongside the contract.
- **Impact:** Drift between UI states and contract states.
- **Fix:** Derive UI states from contract enums via a single mapping module; keep presentational enums clearly separate.
- **Effort:** Medium.

#### FE-P2-02 · Hardcoded single project `"p1"`
- **File/line:** [lib/mock-data.ts:19-23](../../lib/mock-data.ts#L19-L23)
- **Current:** `projects = [{ id: "p1", … }]`, `activeProjectId = "p1"`.
- **Expected:** `listProjects`/`getProject`; active project from real context.
- **Impact:** Single hardcoded project; needed for createRun path (`/projects/{project_id}/runs`).
- **Fix:** Load projects; resolve active project id from session/context.
- **Effort:** Medium.

#### FE-P2-03 · Fake cost values
- **File/line:** [lib/api.ts:124-125](../../lib/api.ts#L124-L125),[:152-178](../../lib/api.ts#L152-L178)
- **Current:** `MOCK_COST_PER_STEP = 0.15`; cost computed by the mock run engine.
- **Expected:** `getUsage` / `estimated_cost_chf` from the contract ([openapi-v1_1.yaml:3392](../../final_backend_contracts_v1_1/openapi-v1_1.yaml#L3392)).
- **Impact:** Cost banner is cosmetic until wired.
- **Fix:** Source cost from run status/usage endpoints.
- **Effort:** Small.

#### FE-P2-04 · Frozen install needs non-TTY purge consent
- **Current:** `ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY` on `--frozen-lockfile`.
- **Fix:** Set `CI=true` / `confirmModulesPurge=false` in CI; document in README.
- **Effort:** Small.

#### FE-P2-05 · Demo scaffolding to remove before evaluation
- **File/line:** `DIALOG_SCENARIOS` [app/quellen/page.tsx:65-165](../../app/quellen/page.tsx#L65-L165); `PAGE_SCENARIOS` (review-mock-data); debug blocks behind `false` flags.
- **Fix:** Strip demo scenario switchers once data is live.
- **Effort:** Small.

### Post-Beta

- **FE-PB-01 · Structured project-data workspace** — no UI for `ProjectDates`, `WorkPackages`,
  `Milestones`, `PlannedHours`, `BudgetPlan`, `RiskRegister`, `ApplicationStructure` (zero matches in
  the frontend). **Recommend a separate "Projektdaten & Planung" workspace** (see STEP 6), not Intake
  overload. Effort: Large.
- **FE-PB-02 · Admin surfaces** — `listAuditEvents`, `listControlResults`, `testServiceConnection`,
  `getProjectLimits`/`update`, `startFinalQualityReview` (lead_admin). Effort: Medium.
- **FE-PB-03 · Multi-project context** — beyond the single `p1`. Effort: Medium.
- **FE-PB-04 · Structured Partner CRUD** — partners are free-text in Intake; contract has
  `list/create/update/deletePartner`. Effort: Medium.

---

## F. UI → operationId matrix (summary)

The complete 72-operation matrix (with Rule-4 categories and gap flags) is in
[Frontend_API_Coverage_Matrix_v1.md](./Frontend_API_Coverage_Matrix_v1.md). Headline:

- **Wired (client fn + BFF), but to MVP shape not v1.1:** createRun, getRun, cancel(stop), resume,
  listFields, updateField(section), createRedraft, review(collapsed), uploadSource, export, feedback,
  project-state — **~12 operations, all needing repath/reshape**.
- **Contract operations with a real UI consumer but no wiring:** session×4, capabilities, listProjects,
  partners, source text/url/list/delete, processing-confirmation, research×4, requirements, evidence
  links, getReview/human-decisions/approvals/rechecks (as distinct ops), usage, services.
- **No expected beta UI consumer (infrastructure/system):** getOperation, getHealth,
  getApplicationStructure, getServiceAvailability (drives toggles).
- **Planned post-beta (no beta consumer):** project-dates, work-packages, milestones, planned-hours,
  budget-plan, risk-register, audit, controls, limits, final-quality-review.

---

## G. Mock-to-live replacement plan (order)

Full sequencing, dependencies, files, and effort are in
[Frontend_Implementation_Plan_v1.md](./Frontend_Implementation_Plan_v1.md). Order:

1. **Session** (createSession/get/delete, CSRF, guard, 401) → unblocks authenticated calls.
2. **Projects** (listProjects/getProject; real active project id) → unblocks project-scoped paths.
3. **Capabilities** (getCapabilities/serviceAvailability) → server-driven gating.
4. **Sources** (file/text/url, list/poll/delete, `needs_manual_input`).
5. **Runs/polling** (createRun→202+poll, getRun with contract `RunStatus`, cancel, resume).
6. **Requirements/evidence** (listRequirements, listEvidence, EvidenceLink create/delete).
7. **Drafts** (updateField with `base_version_id`/`draft_version_id` + 409; createRedraft async).
8. **Rechecks/review/approval** (getReview, human-decisions, targeted recheck, approval scope/stale).
9. **Export** (createExport→getExport→download; DRAFT-without-approval).
10. **Usage/research** (getUsage real cost; research tasks/results import).

---

## H. Go/No-Go decisions

### (a) Backend skeleton implementation — **GO**
The v1.1 contract is finalized and internally consistent (`Final_Consistency_Audit_v1_1.md`), and the
frontend's needs are concrete and documented here. Nothing blocks scaffolding the FastAPI skeleton
against `openapi-v1_1.yaml`. **Precondition:** treat the contract (hashes above) as frozen for the
beta; track changes as contract revisions.

### (b) Beta-slice frontend integration — **GO, conditional on the P0 set**
Begin integration now on the existing seam, but **do not flip `USE_MOCKS` to live** until FE-P0-01..09
land (repath/reshape BFF to v1.1, session/auth, `DataClassification` + `RunStatus` models, draft
`base_version`/409, `202` async). Recommended entry point: phases 1–2 (session, projects) behind a
live flag while mocks remain default. **Precondition:** a running backend skeleton (decision a) and an
agreed value/format for `FASTAPI_BRIDGE_URL` (must include `/api/v1`).

### (c) Full v1.1 UI coverage — **NO-GO (defer to post-beta)**
Net-new structured-data and admin surfaces (FE-PB-01..04) are out of beta scope. Revisit after the
beta slice is live and after a "Projektdaten & Planung" workspace is designed (progressive
disclosure, not Intake overload).

---

## Methodological notes (clarifications applied)

- **No pre-decided verdicts** — A1/A2 are derived from STEP 2–8 evidence above.
- **BFF-first** — the `/api/*` proxy is an intentional, sound BFF; defects are at the **BFF→backend
  boundary** (paths/verbs/shapes vs v1.1) plus the undocumented `/api/v1` base assumption in
  `.env.example` (`FASTAPI_BRIDGE_URL=` empty).
- **Per-operation classification** (Rule 4) is applied in the coverage matrix; a missing UI is a gap
  only where a user/admin-facing consumer is expected.
- **Lint/test gaps** are quality/reproducibility issues (Rule 7), not runtime P0s.
- **Contract hashes** recorded; `final_backend_contracts_v1_1/` left untracked and untouched.
- **git status** captured before/after every file-creating step; only `docs/audits/` added.
