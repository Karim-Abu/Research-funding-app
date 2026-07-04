# Milestone 9D — A2 Solution & Innovation Draft Suggestions with Side-by-Side Review

## Basis

- M9C baseline commit `474ecc0` (tagged `milestone-9c-a1-evidence-mapping`).
- M9D branch `feat/a2-solution-innovation`, branched from **`c3abd84`** (tagged
  `milestone-9c-1-ux-stabilization`) — `c3abd84` adds later UX-stabilization UI work
  (dashboard/sidebar/sources redesign) on top of M9C.
- Pre-implementation gate: backend `pytest` 326/3-skip, frontend `tsc`/`lint` clean,
  vitest green. **Note:** the Playwright suite was not re-run at STEP 0; the UX-stabilization
  commits had already broken 4 specs (see *Known limitations*) before any M9D change.
- No automatic commit (only the STEP-0 tags + branch).

## Scope

Activates the **first A2 (drafting) profile — `A2.solution_innovation`** — for **exactly one
field**, `SOL.INNOVATION_SOLUTION.EDITOR`, and adds the **first user-facing AI surface**: a
side-by-side suggestion review in the live Editor. The suggestion is **advisory and never
auto-applied**; the user explicitly accepts (→ new DraftVersion `created_by=agent`) or hides
it. No other A2/A3 profile, no other field, no finalized-contract change.

## Changed files

- **New backend** `app/agents/field_drafting.py` (orchestrator), `field_drafting_context.py`
  (6 read-only A2 tools), `app/fields/redraft_service.py` (createRedraft + async executor),
  `app/repositories/draft_suggestions.py`, migration `a7d2e4c8b1f6_draft_suggestions.py`,
  3 test modules + `tests/a2_helpers.py`.
- **Modified backend** `app/db/models.py` (`DraftSuggestion`), `app/agents/schemas.py`
  (A2 I/O models), `app/agents/prompts/a2_solution_innovation_v1.md` (activated),
  `app/api/fields.py` (`createRedraft` endpoint), `app/repositories/drafts.py`
  (`apply_update` agent-acceptance), `app/contracts/draft.py` (`RedraftRequest`),
  `app/config/settings.py` (`agent_fake_provider` dev flag); 2 outdated tests updated
  (`test_agent_schemas`, `test_draft_flow`).
- **New frontend** `lib/redraft.ts`, `components/editor/suggestion-review-dialog.tsx`,
  `app/api/runs/[id]/fields/[field]/redrafts/route.ts`, 3 vitest modules + the e2e spec.
- **Modified frontend** `lib/fields.ts` (`updateField` optional `source_operation_id`),
  `components/editor/live-editor.tsx` (SOL-only A2 control + dialog).

## Migration

`a7d2e4c8b1f6` (`down_revision = f3c5d7e9a1b2`, M9C head): creates the internal
`draft_suggestions` table (no OpenAPI exposure). UP/DOWN/REUP verified clean.

## A2 profile + prompt version

`A2.solution_innovation` (`agents_v1_1.yaml`): `advisory: true`, `output_authority:
draft_requires_human_review`, field `SOL.INNOVATION_SOLUTION.EDITOR` only; input
`FieldDraftingInput@v1`, output `PortalFieldDraftBundle@v1`; 6 read-only tools (authorization
pre-validated at startup); model `anthropic_sonnet_46`/`openai_gpt_54`; limits `max_per_run:1`,
`max_redrafts_per_field:1`, composite ≤ 25000 chars. Prompt **`a2_solution_innovation_v1`**
(`status: active_m9d`): structured output only, no invented facts/citations/market/novelty/IP,
`exact_verified` = quote exists (not approved), proposed A1 facts are not confirmed, preserve
4.1–4.5, never exceed the limit, never change verification/approval/requirement status.

## Public API decision — Option A (fully contract-compatible, NO new endpoint)

1. **Generate** = `createRedraft` `POST /runs/{run_id}/fields/{field_id}/redrafts`
   (`RedraftRequest{base_version_id, guidance?}` → 202; **409** stale base, **503** AI
   unavailable). Implemented (was declared-but-unimplemented).
2. **Retrieve** = existing `getOperation` — the suggestion is in `AsyncOperation.result`.
3. **Accept** = existing `updateField` with `DraftPatch.source_operation_id` → new
   DraftVersion `created_by=agent`, 409 on stale, recheck + approval-stale inherited from
   `apply_update`.
4. **Reject** = client-side dismissal ("Vorschlag ausblenden") — no public reject endpoint
   exists, so none was invented; the internal suggestion auto-expires when superseded.

## Suggestion persistence

Internal `draft_suggestions` (immutable except status/decision): suggestion/run/workspace/
draft/base_version/field/profile/operation/agent-invocation ids, prompt/model metadata,
status (proposed|accepted|rejected|expired|failed), suggested_text, rationale,
evidence_anchor_ids, open_issue_ids, placeholders, content_hash, character_count, decision
fields, accepted_draft_version_id. Only an accepted suggestion creates a DraftVersion.

## Context assembly

`field_drafting_context.assemble_a2_context`: current draft text + SOL field profile (label,
25000 limit, mandatory 4.1–4.5), requirement assessments + open issues for the field, **only
exact_verified** EvidenceAnchors + active EvidenceLinks (quotes, not full documents), and A1
ExtractedFacts as **advisory/proposed** context. Six read-only tool-services recorded as
ToolInvocations → CTRL.TOOL_AUTHORIZATION. The pinned `FieldDraftingInput@v1` carries the
structured fields; current draft + assessments are rendered into the delimited untrusted
`context_text`. Payload minimization (char budget, context_hash, metadata) as M9B/M9C; no
secrets/keys; composite `AgentInvocation.input_hash`.

## Validation rules (STEP 8)

On `draft_candidates[0]` for the SOL field: non-empty text; **char count ≤ 25000 — strict,
backend-enforced, never trimmed**; **mandatory 4.1–4.5 preserved** (semantic — the five
section numbers present, not byte-identical labels, corr #5); referenced `evidence_anchor_ids`
exist in the run; referenced `open_issue_ids` exist; verification/approval/requirement status
structurally impossible (`extra="forbid"`). Invalid/failed → no suggestion persisted, safe
failure recorded — never trimmed to fit.

## Accept / reject behaviour

`apply_update` marks `created_by=agent` **only** when `source_operation_id` passes ALL checks
(corr #3): the operation **succeeded**; same run/workspace/draft/field + base_version_id; a
still-**proposed** suggestion exists; its `content_hash` equals the accepted text. Otherwise a
normal user edit (or safe 409/422) — **never arbitrary text marked agent**. Accept inherits
409-on-stale, `recheck_required=true`, `invalidate_approvals`, link-stale, immutable old
version. Reject is a client-side dismissal (no backend mutation, not audited). **Generation
alone changes no draft/requirement/anchor/approval/export.**

## Side-by-side UI

In the live Editor, a "KI-Vorschlag erstellen" control appears **only** for
`SOL.INNOVATION_SOLUTION.EDITOR` (no AI controls on any other field; `features.ai` stays
false; no model/provider/confidence shown). States: empty
("…noch nicht erstellt"), unavailable/503 ("…nicht verfügbar"), loading, error. On success a
dedicated `SuggestionReviewDialog` shows current vs suggested text, rationale, evidence used
(quote + source + verification badge), unresolved open issues, character count vs 25000, a
placeholder warning and an unconfirmed-facts warning, with **"Übernehmen"** (→ `updateField`
with `source_operation_id`; 409 reuses the conflict dialog) and **"Vorschlag ausblenden"**
(client-side dismiss). After accept the draft reloads to the agent version and the recheck
notice appears.

## Data Policy / CostGuard

Processing-mode discipline (corr #2): `createRedraft`/`availability()` read the run's existing
processing mode and **never upgrade** deterministic_only/local_only → cloud_assisted; A2 runs
only when the run already permits cloud_assisted for the data class (else 503); `guidance` is
drafting text only (no confirmation smuggling). The gateway re-enforces Data Policy + CostGuard
(`max_per_run:1`, replay-idempotent). No key/raw prompt/source/provider payload in logs or DB.

## Fake-provider tests

All mandatory backend tests use the fake provider (26 new): generation allowed only for the
SOL field; valid suggestion persists; over-limit / missing-4.x / invented-anchor /
unknown-open-issue / empty rejected; deterministic_only skips (no provider call); confidential
blocked; malformed/timeout → safe failure; replay reuse; CostGuard; **createRedraft** 202/409/
503; **accept** → DraftVersion created_by=agent, stale→409, recheck + approval invalidated,
old version immutable, edited-text not marked agent, reject creates no version; security
(no key/raw output/full source in DB/audit, injection ignored, no requirement/anchor/draft
mutation). Frontend vitest (12 new): redraft client (202→poll, 503, 409, failure), the
review dialog, and the LiveEditor SOL flow (control only on SOL, empty/unavailable states,
generate→side-by-side→accept→recheck, dismiss).

## Optional real-provider smoke status

No A2-specific real smoke was added; the dormant adapters and the M9A/B/C env-gated smokes are
unchanged. The `agent_fake_provider` flag is a dev/test affordance (off in production).

## Security controls

No API key / raw prompt / full source / raw provider payload in logs or DB (AgentInvocation
stores hashes/metadata only). Evidence quotes are untrusted data; an injection in a verified
quote cannot mark evidence approved, change rules/tools, or leak secrets. Generation never
mutates RequirementAssessments, EvidenceAnchor verification, approvals or exports.

## Deterministic-baseline preservation

A2 is endpoint-triggered, not in the run graph — deterministic runs are unchanged. The
editor-using `template-drafts` Playwright spec, plus evidence/requirements/export/run
specs, pass — confirming the LiveEditor changes are safe.

## Test results

- **Backend** `pytest`: **353 passed, 3 skipped** (326 baseline + 27 new A2). Migration
  roundtrip clean; app starts.
- **Frontend** `tsc --noEmit` 0, `pnpm lint` 0, `pnpm build` success, `pnpm test` **108
  passed** (+12 A2 vitest).
- **Playwright**: the M9D A2 spec passes (safe-503 unavailable + field-scope + no draft
  mutation); the deterministic editor/evidence/requirements/export/run specs pass. At M9D
  end, 4 specs failed for **pre-existing UX-stabilization drift** (not M9D); these were
  resolved in **Milestone 9D.1** (the full suite is now green in serial mode — see
  `Milestone_9D_1_E2E_Acceptance_Report.md`).

## Runtime Availability in the Beta (added in M9D.1)

A2.solution_innovation is **fully implemented** and exercised by mandatory tests using the
**fake provider** and **cloud-assisted test fixtures** (backend tests construct
cloud_assisted runs directly in the DB; the dev-only `agent_fake_provider` flag drives the
fake adapter). However, in the **live beta deployment the feature returns a safe `503
ai_unavailable`** ("KI-Vorschläge sind für diese Datenklasse oder Umgebung nicht
verfügbar"), because:

- **Cloud processing is disabled by policy.** `app/runs/policy.py`
  (`validate_processing_mode`) rejects `cloud_assisted` run creation with `403
  cloud_processing_unavailable` in the evaluation beta. Every live run is therefore
  `deterministic_only`.
- **A2 requires `cloud_assisted`.** `createRedraft`/`availability()` read the run's
  **existing** processing mode and **never silently upgrade** `deterministic_only` →
  `cloud_assisted` (no mode smuggling via `RedraftRequest.guidance`). A `deterministic_only`
  run → A2 unavailable → safe 503. This honest behaviour is intentional until the cloud /
  data-policy confirmation gate is built.

**What must be implemented before real user-facing A2 can run** (out of scope here — no
data-policy change in M9D/M9D.1):

- an **explicit cloud-assisted run** (or a field-level cloud-processing confirmation) that
  the deployment policy permits;
- a **DataClassification check** restricting payloads to **public / synthetic** content in
  the beta (confidential / NDA always blocked);
- the **per-run external-processing confirmation route** (institutional approval +
  authorized-user confirmation) the A1/A2 data policy already declares;
- **CostGuard** enforcement (already wired) and **provider availability** (a configured,
  approved model route / key);
- **audit** of the cloud invocation (already wired via AgentInvocation / ControlResult /
  AuditEvent).

Until those exist, the deterministic M6 template draft remains the field's content and the
Editor shows the calm unavailable state — no misleading suggestion is produced.

## Known limitations

- **Cloud processing is gated off in this beta deployment** (`app/runs/policy.py` returns
  `403 cloud_processing_unavailable` for cloud_assisted run creation — a finalized M3 policy).
  A2 requires cloud_assisted, so in this deployment `createRedraft` always returns the safe
  **503 "nicht verfügbar"**. The full create→accept→recheck flow is therefore validated via
  the backend API tests and frontend vitest (which construct cloud_assisted runs directly),
  and the e2e validates the safe-unavailable path. When the deployment enables an approved
  cloud route, the same code path produces live suggestions (covered by `agent_fake_provider`).
- **4 pre-existing Playwright failures from the UX-stabilization commits (`c3abd84`), NOT
  M9D:** `source-ingestion` (×2) waits for the button `"Text als Quelle hinzufügen"` which the
  UX redesign removed (`git show c3abd84:components/quellen/source-table.tsx | grep` = 0);
  `review-recheck-approval` hits a strict-mode collision from a new `h2 "Qualitätsprüfungen"`;
  `portal-transfer` waits for the changed `"Innolink-Übernahme"` nav link. None of M9D's
  changed files touch the sources page, review center or Innolink navigation. **Recommendation:**
  update these specs to the redesigned UI as part of the UX-stabilization work (out of M9D
  scope); STEP 0's Playwright gate was not run, which would have surfaced this earlier.
- Reject has no audited backend path (client-side dismissal only), per corr #4.

## Readiness verdict for M9E (Value Creation)

The A2 drafting path — context assembly via 6 registered tools, ModelGateway invocation with
Data Policy + CostGuard + replay idempotency, mandatory schema + structure + char-limit +
evidence/open-issue validation, advisory DraftSuggestion persistence, the contract-compatible
createRedraft → getOperation → updateField(source_operation_id) accept flow with strict
agent-provenance verification, and the SOL-only side-by-side review UI — is implemented
contract-faithfully and covered by fake-provider backend tests + frontend vitest + an e2e,
without auto-applying drafts, changing review/approval/requirement/export state, modifying a
finalized contract, leaking secrets, or activating AI on any other field. The same field-
drafting pattern (orchestrator, context, createRedraft, accept-by-source_operation_id, the
SuggestionReviewDialog) generalizes directly to **M9E A2.value_creation_market_logic** —
which will reuse this machinery for the Value Creation field. Ready for M9E once the pre-
existing UX-stabilization Playwright specs are updated.
