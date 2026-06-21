# Frontend Implementation Plan — Mock → Live (v1)

**Date:** 2026-06-21. Companion to
[Frontend_Contract_Readiness_Audit_v1.md](./Frontend_Contract_Readiness_Audit_v1.md) and
[Frontend_API_Coverage_Matrix_v1.md](./Frontend_API_Coverage_Matrix_v1.md).

> This is a sequencing plan for a **later, separately-approved implementation pass**. This audit does
> not change application code. Effort = small / medium / large (relative).

## Cross-cutting prerequisites (do first)

These underpin every phase and should land before flipping any slice to live:

- **P0-A · Live toggle** — replace `USE_MOCKS = true` ([lib/api.ts:54](../../lib/api.ts#L54)) with a
  build/runtime switch (server-trusted; no secrets client-side). *Small.*
- **P0-B · BFF base path** — define `FASTAPI_BRIDGE_URL` to include `/api/v1` (or prepend it in
  [lib/bridge.ts](../../lib/bridge.ts)); document in `.env.example` (currently empty). *Small.*
- **P0-C · Write-request envelope** — extend `request()`
  ([lib/api.ts:76-96](../../lib/api.ts#L76-L96)) to attach `X-CSRF-Token` (from session) and a
  generated `Idempotency-Key` on all mutating calls; map `401/403/404/409/422/429/503` to typed
  errors. *Medium.* (FE-P1-03, FE-P1-06)
- **P0-D · Contract enums as source of truth** — adopt contract `RunStatus`
  (`created|running|paused_for_review|completed|stopped|failed|cancelled`),
  `AsyncOperation` status, source status incl. `needs_manual_input`, and field-draft versioning into
  [lib/backend-contract.ts](../../lib/backend-contract.ts); add a single contract→UI status mapping
  module (addresses FE-P0-07, FE-P2-01). *Medium.*
- **P0-E · `DataClassification` model** — replace flat `DataClass`
  ([lib/types.ts:45-94](../../lib/types.ts#L45-L94)) with the 5-field object; rederive
  `isCloudAllowed`/`isWebAllowed` from `processing_mode`/`web_research_mode`. *Large.* (FE-P0-06)

---

## Phase 1 — Session  *(unblocks everything authenticated)*
- **Ops:** createSession, getSession, getCurrentUser, deleteSession.
- **Files:** `app/login/page.tsx` (real submit + error), `components/shell/user-menu.tsx` (wire
  logout), new session provider/hook + route guard, `app/api/session/*` BFF handlers.
- **Behaviour:** HTTP-only cookie + CSRF bootstrap; guard `/` and authenticated routes; 401 →
  re-login UX.
- **Depends:** P0-A/B/C. **Effort:** Large. **Done when:** login establishes a real session, guard
  redirects unauthenticated users, logout clears the session.

## Phase 2 — Projects  *(unblocks project-scoped paths)*
- **Ops:** listProjects, getProject (createProject/updateProject as needed by Intake).
- **Files:** `app/page.tsx` (dashboard from `listProjects`), `lib/mock-data.ts` project constants →
  real context, `lib/api.ts` add project fns, `app/api/projects/*`.
- **Behaviour:** real active-project id (removes hardcoded `"p1"`), feeding `createRun`'s
  `/projects/{project_id}/runs` path.
- **Depends:** Phase 1. **Effort:** Medium. **Done when:** dashboard reflects real projects; active
  project id resolved from context.

## Phase 3 — Capabilities  *(server-driven gating)*
- **Ops:** getCapabilities, getServiceAvailability.
- **Files:** session provider (store capabilities), `components/run/service-toggles.tsx`,
  `components/run/analyse-einstellungen-dialog.tsx`, role checks across shell.
- **Behaviour:** role (`effective_role`) and KI/web availability come from the server; UI gating is
  convenience only (server stays authoritative).
- **Depends:** Phase 1. **Effort:** Medium. **Done when:** lead_admin-only actions and service
  toggles derive from capabilities.

## Phase 4 — Sources
- **Ops:** uploadSourceFiles (repath), createTextSource, importUrlSource, listSources, getSource,
  deleteSource; createProcessingConfirmation, createReclassification.
- **Files:** `lib/api.ts` (`uploadSource`→`/projects/{id}/sources/files`; add text/url/list/get/delete),
  `components/quellen/source-table.tsx` (add text/URL entry, real delete, real status poll, remove
  `setTimeout` completion), `app/api/sources/*` repath.
- **Behaviour:** adopt contract source status incl. `needs_manual_input`; URL/research confirmation
  UX; internal cloud-processing confirmation.
- **Depends:** Phase 2, P0-D. **Effort:** Medium. (FE-P1-04, FE-P1-07)

## Phase 5 — Runs / polling
- **Ops:** createRun (202 + poll), getRun, cancelRun, resumeRun, listProjectRuns.
- **Files:** `lib/api.ts` (`startRun`→`/projects/{id}/runs`, consume `202`; `stopRun`→`cancel`;
  `normalizeRunStatus`), `app/quellen/page.tsx` poll loop (contract `RunStatus`; `paused_for_review`→
  review CTA, `cancelled` handling), `app/api/runs/*` repath (`/runs`→`/projects/{id}/runs`,
  `stop`→`cancel`), `lib/run-steps.ts` (`NODE_TO_STEP_INDEX`→`current_stage`).
- **Behaviour:** start→202→operation poll; 409 existing-active-run, 429 cost, 503 provider distinct
  UX; keep 1s polling + cleanup (already correct).
- **Depends:** Phases 2–4, P0-C/D, FE-P1-01. **Effort:** Large. (FE-P0-02, FE-P0-07, FE-P0-09, FE-P1-06)

## Phase 6 — Requirements / evidence
- **Ops:** listRequirements, listEvidence, createEvidenceLink, deleteEvidenceLink, getField.
- **Files:** `app/anforderungen/*` + `components/anforderungen/*` (mapper vs v1.1 schema),
  `components/quellen/evidence-*`, `lib/run-steps.ts` `mapBackendRequirements` rewrite,
  `lib/backend-contract.ts` add `EvidenceLink` + `verification_status` + link status.
- **Behaviour:** evidence link lifecycle (active/stale/removed); human-check verification.
- **Depends:** Phase 5. **Effort:** Medium. (FE-P0-09, FE-P1-02)

## Phase 7 — Drafts
- **Ops:** updateField (base_version_id/409), createRedraft (202 async).
- **Files:** `lib/api.ts` (`patchSection`→`updateField` under run+field, send `base_version_id`,
  track `draft_version_id`, handle 409; `redraftField`→field-level, async),
  `components/editor/*` + `components/review/*` (conflict reload-merge UX, `recheck_required`),
  `app/api/sections/*`→`app/api/runs/[id]/fields/[fieldId]/*`.
- **Depends:** Phases 5–6, P0-C/D. **Effort:** Medium. (FE-P0-04)

## Phase 8 — Rechecks / review / approval
- **Ops:** getReview, createHumanDecision, startTargetedRecheck (202), createApproval.
- **Files:** `components/review/review-screen.tsx`, `lib/api.ts` (split `submitReview` into
  human-decisions + recheck + approval), `app/api/runs/[id]/{human-decisions,rechecks,approvals}`.
- **Behaviour:** approval valid only for the current recheck scope; stale-approval state; targeted
  recheck before approval.
- **Depends:** Phase 7. **Effort:** Large. (FE-P0-03)

## Phase 9 — Export
- **Ops:** createExport (POST), getExport, downloadExport.
- **Files:** `components/export/export-screen.tsx`, `app/export/page.tsx`, `lib/api.ts`
  (`exportDownloadUrl`→create→poll→download), `app/api/runs/[id]/export`→exports flow.
- **Behaviour:** DRAFT export without a valid approval; approval-gated final.
- **Depends:** Phase 8. **Effort:** Medium. (FE-P0-05)

## Phase 10 — Usage / research
- **Ops:** getUsage (real cost), createResearchTask/getResearchTask/listResearchResults/importResearchResult.
- **Files:** `components/kosten/*` (replace mock cost), research-task UI (lead_admin).
- **Depends:** Phases 3–5. **Effort:** Medium. (FE-P2-03)

---

## Post-beta (separate track)
- **Projektdaten & Planung workspace** — ProjectDates, WorkPackages, Milestones, PlannedHours,
  BudgetPlan, RiskRegister, ApplicationStructure (progressive disclosure; **not** Intake). *Large.*
- **Admin surfaces** — audit events, controls, service tests, limits, final-quality-review. *Medium.*
- **Structured Partner CRUD**, multi-project context. *Medium.*

## Quality track (parallel, Rule 7 — not a runtime blocker)
- Add eslint (dependency + config) so `pnpm lint` runs; set `CI`/`confirmModulesPurge=false` for
  reproducible frozen installs.
- Minimal unit tests for the contract-critical seam: status/enum mapping, `DataClassification`
  derivation, `base_version_id`/409 handling, async-operation polling. *Medium.*

## Suggested integration entry point
Land cross-cutting P0-A..E + Phases 1–2 behind a live flag (mocks remain default) once a backend
skeleton is running and `FASTAPI_BRIDGE_URL` (incl. `/api/v1`) is agreed. Then proceed 3→10.
