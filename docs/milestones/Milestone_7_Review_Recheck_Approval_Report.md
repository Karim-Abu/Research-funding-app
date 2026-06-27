# Milestone 7 — Review, Recheck, Approval, Version History & Section Comments

## Basis

- Branch: `feat/review-recheck-approval` (created from `a002e61`, tag
  `milestone-6-1-demo-dataset`).
- Pre-implementation gate (clean tree, full suite green) verified before any
  change: backend `pytest` 144 passed, `pnpm test` 62 passed, `tsc`/`lint` clean.
- No automatic commit was created.

## Scope & decisions

The first real review layer over the M4–M6 artifacts: deterministic
`ReviewFinding`s → a computed `ReviewPackage` → typed `HumanDecision`s (incl.
section comments) → targeted recheck → role-gated `ReviewApproval` with an
`approval_scope_hash` that goes stale on any later edit. Enforced order:
**edit → recheck → review-updated → approval**. No LLM / A3 / ModelGateway /
provider / export / cloud.

Two binding design decisions were taken with the user before implementation:

1. **Review-on-completed model** (run_state escape hatch). Runs still
   `finalize_run → completed`; `critic_review`, `aggregate_review` and
   `human_review` run as deterministic, **non-pausing** graph stages before
   finalize. Review, recheck, decisions and approval are API operations on the
   completed run. `resumeRun` stays `409 run_not_resumable`. This preserves the
   M1–M6 run lifecycle, the demo seed and every existing test (the review stages
   are additive; `finalize_run` stays last → `completed`/stage/progress
   assertions still hold).
2. **Section comments via `HumanDecision`** (no invented Comment entity). A
   comment is a `HumanDecision` targeting `portal_field_draft` carrying the
   `comment`, materialized as a `source=human` `ReviewFinding` (which has a
   status) so it shows open/resolved per section.

Four binding corrections from plan review were implemented (see the relevant
sections): (#1) recheck currency vs approvability decoupled; (#2) placeholders in
supported mandatory fields are scope-aware blockers; (#3) evidence decisions are
review-level only and never touch `verification_status`; (#4) version history is
internal-only (P1).

## Contract conformance (openapi-v1_1.yaml — no inventions)

Implemented exactly the documented operations and schemas, no new paths/fields:

| Operation | Method/Path | Request | Response |
|---|---|---|---|
| `getReview` | GET `/runs/{id}/review` | – | 200 `ReviewPackage` |
| `createHumanDecision` | POST `/runs/{id}/human-decisions` | `HumanDecisionCreate` (oneOf, discriminator `target_type`) | 201 `HumanDecision` |
| `createApproval` | POST `/runs/{id}/approvals` | `ApprovalCreate` | 201 `ReviewApproval` |
| `startTargetedRecheck` | POST `/runs/{id}/rechecks` | `RecheckCreate` | 202 `AsyncAccepted` |

All mutations require session + CSRF + Origin + `Idempotency-Key` + role
(member/lead_admin), with idempotent replay. The BFF forwards every header
unchanged. `ReviewFinding` is returned with **only** its contract fields
(`source`, `finding_code`, `target_*`, `recommended_next_action` stay internal).

## Persistence (migration `b7e3f5a91c42`, head `a6d1c7e9f024` → `b7e3f5a91c42`)

New tables (upgrade/downgrade roundtrip verified): `review_findings`
(unique `run_id, source, finding_code` for idempotent upsert), `human_decisions`,
`review_approvals`, `review_packages` (1:1 per run). Reuses the existing
`analysis_runs.{recheck_required, review_package_version, approval_scope_hash}`
columns. Terminal-run artifacts (DraftVersions, EvidenceAnchors) are never
rewritten.

## Deterministic review aggregator (`app/review/checks.py`)

Pure rule-based findings over persisted M4–M6 state, each with a stable
`finding_code` (idempotent re-run; fixes clear the finding). Sources:

- Open **blocker** OpenIssues (e.g. blocked requirements, missing eligible
  research partner) → blocker.
- `needs_input` requirement assessments → warning; stale assessments (snapshot
  drift) → warning.
- Draft **placeholders** (`[[Angabe ergänzen: …]]`) in a supported mandatory
  field → **blocker**; empty supported field → blocker; over character limit →
  blocker.
- Stale draft evidence links, evidence links to not-exact-verified anchors, and
  user-edited fields with no active evidence link while verified evidence exists
  → warning.

Never judges market fit, novelty, business quality or persuasiveness; makes no
LLM/network/provider call.

## ReviewPackage + approval scope hash (`app/review/package.py`)

`approval_scope_hash` = SHA-256 over the deterministically sorted scope: run id;
current DraftVersion ids; draft EvidenceLink `id:status`; RequirementAssessment
`id:status`; OpenIssue `id:status`; ReviewFinding `id:status`; registry versions.
`review_package_version` is derived from the hash. `approval_status` is derived
deterministically (approved / stale / blocked / changes_required / open). The
package is refreshed by `aggregate_review` and by targeted recheck; `getReview`
computes the current hash/version/counts live without mutating.

## Targeted recheck (`app/review/recheck.py`)

`startTargetedRecheck` validates the expected package version (`409
review_package_stale` on mismatch) and returns `202 AsyncAccepted`; a background
deterministic executor re-runs the aggregator, rebuilds the package and clears
`recheck_required`. **Correction #1:** a successful recheck sets
`recheck_required=false` because the review state is current again — **even if
blocker findings remain** (those keep `approval_status=blocked`); blockers never
keep `recheck_required=true`. The recheck never re-runs the graph, re-ingests
sources, re-discovers evidence, mutates historical artifacts, calls a provider,
or auto-approves.

## Approval gating + invalidation

`createApproval` (`app/review/service.py`) honours **scope** and re-derives every
gate from raw state (so a human dismissing a derived finding can never bypass a
hard gate). Allowed only if: run completed; `recheck_required=false`; expected
hash **and** version match the current state (else `409 review_package_stale`);
role member/lead_admin; `confirm_not_submission_approval=true`; and the scope is
clean:

- **scope=run** → no blocker OpenIssue, no placeholder in any supported mandatory
  field, no empty/over-limit field, no stale draft evidence link, all drafts
  current.
- **scope=field** → the same, restricted to the approved field (requirement-level
  blockers that do not target the field do not block a field approval).

Gate failure → `409 approval_blocked` with the reasons enumerated in `detail`.
**Correction #2:** placeholders in supported mandatory fields are blockers
(deferred repeated-instance fields are not M6 draft fields → never block).

**Invalidation** (`app/review/invalidation.py`): `updateField` /
`createEvidenceLink` / `deleteEvidenceLink` (which already set
`recheck_required=true` in M6) additionally mark active approvals **stale**
(`invalidated_at`) and audit it. The most recent invalidated approval surfaces as
`approval_status=stale`.

## Human decisions & section comments

`record_human_decision` validates the target is scoped to the run, then applies:
finding decisions → status (confirm→resolved, dismiss→dismissed,
override→overridden, request_changes→open); `portal_field_draft`
`request_changes` + comment → a `source=human` warning finding (the section
comment); `portal_field_draft` `confirm` → resolves the field's open comments.
**Correction #3:** `evidence_anchor` confirm/reject is review-level only — it is
recorded and audited but **never** mutates `EvidenceAnchor.verification_status`
and never creates `human_verified`; the UI labels distinguish *technisch
verifiziert* from *fachlich bestätigt*.

## Graph (`app/runs/{graph,constants}.py`) — 11 deterministic stages

`… → create_template_drafts → critic_review → aggregate_review → human_review →
finalize_run → completed`. `critic_review` records `CTRL.DATA_POLICY`
(`a3_disabled deterministic_review`) and runs the aggregator; `aggregate_review`
builds the package (`CTRL.OUTPUT_SCHEMA`); `human_review` records
`CTRL.APPROVAL_GATE` (review available, no auto-approval) without pausing. All
three check cancellation and use the existing SQLite checkpointer. `finalize_run`
stays the last stage at progress 100.

## Frontend

- **BFF**: `app/api/runs/[id]/review` (GET), `…/human-decisions`, `…/approvals`,
  `…/rechecks` (POST) via `forwardToBridge`; `"review"` added to `LIVE_RESOURCES`.
  (The stale placeholder POST handler under `…/review` was replaced by the GET.)
- **Client** `lib/review.ts`: typed `ReviewPackage`/`Finding`/`HumanDecision`/
  `Approval` DTOs + `getReview`, `createHumanDecision`, `createApproval` and
  `startRecheck` (which polls the async operation to terminal).
- **Review Center** `components/review/live-review.tsx` (rendered by
  `app/review/page.tsx` in live mode): status badge, blocker/warning counts,
  recheck-required notice, package version, findings, **Erneut prüfen** and
  **Review freigeben** (run scope) with the approve button disabled + an explicit
  disabled-reason list when the gate is not met.
- **Editor** `components/editor/live-editor.tsx`: per-field review findings,
  section comments (add via `request_changes`, resolve via finding `dismiss`),
  current-version metadata, and per-section **Abschnitt freigeben** (field-scope
  approval). M6 conflict + draft-link logic preserved; AI/redraft stay disabled.
- **Capability**: `features.review=true` (export/AI/cloud/web_research stay
  false).

## Version history — contract constraint (P1)

OpenAPI has no public draft-version-list operation and `PortalFieldDraft` has no
versions array; inventing an endpoint/field is disallowed. **Correction #4:**
M7 keeps version history **internal-only** (immutable `DraftVersion`s already
persist since M6 and are audited). The editor surfaces only the **current**
version's metadata (created_by / timestamp / character count / evidence-link
count) via `getField`. Public previous-version display and restore are deferred
pending a contract version-list operation (acceptance criteria #11/#12 are
contract-limited). All other acceptance criteria are met.

## Tests & verification

- **Backend** `pytest`: **171 passed** (144 baseline + 27 new across
  `test_review_findings.py`, `test_review_recheck.py`, `test_review_approval.py`,
  `test_review_decisions.py`). Covers finding generation (blockers/placeholders/
  partner/idempotency/no-semantic), recheck (clears `recheck_required` with
  blockers remaining, staleness 409, no historical mutation, CSRF/session),
  approval (run vs field scope, scope-hash mismatch 409, stale-on-edit, `const
  true` enforcement, guards, workspace isolation), decisions/comments (create +
  resolve, evidence verification untouched, idempotent replay, isolation), and
  the 11-stage graph (A3-disabled control, stage order). `compileall` clean.
- **Migration**: `upgrade head → downgrade -1 → upgrade head` clean.
- **Frontend** `pnpm test`: **73 passed** (62 baseline + 11 new across
  `review.test.ts`, `live-review.test.tsx`, editor review/comment/approval).
  `tsc --noEmit` 0 errors, `pnpm lint` 0 errors, `pnpm build` success.
- **Playwright** (live servers, deterministic): **7 passed + 1 seeded demo
  passed**. `review-recheck-approval.spec.ts` drives the full contract flow —
  Project A: run-scope approval blocked → edit field → recheck clears
  `recheck_required` (still blocked by other placeholders) → field-scope approval
  succeeds → re-edit → approval stale; Project B: blocked by the missing
  research-partner blocker finding — plus a live Review-Center UI smoke. All
  existing M4–M6 specs and the M6.1 demo-dataset spec still pass.

## Demo compatibility

The demo seed is unchanged: both demo runs complete through the added review
stages (additive). Project A (edited, `recheck_required=true`) demonstrates the
recheck → approval path; Project B (missing eligible research partner → blocker
OpenIssue → blocker finding) cannot be approved. The seed reset leaves the dev DB
clean.

## P0/P1 findings

- **P0**: none.
- **P1**: public draft-version history display + restore are deferred pending a
  contract version-list operation (documented above). Requirement/assessment
  `override` human decisions are recorded + audited but do not mutate the
  deterministic assessment in M7 (kept review-level by design to avoid faking a
  status).

## Readiness

The deterministic review, targeted recheck, scope-aware approval gating with a
stale-on-edit scope hash, section comments and the 11-stage review graph are
implemented contract-faithfully and fully covered by automated backend, frontend
and live end-to-end tests, without breaking any prior milestone or the demo seed.
Ready for **Milestone 8 (Export)**, which can consume `ReviewApproval` /
`ReviewPackage` as the gate for producing draft vs approved artifacts.
