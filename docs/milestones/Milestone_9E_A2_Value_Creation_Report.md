# Milestone 9E — A2 Value Creation / Business Model Draft Suggestions

**Scope:** activate **exactly one** additional A2 profile,
`A2.value_creation_market_logic`, for **exactly one** additional field,
`VC.BUSINESS_TARGETS_MODEL.EDITOR`. Advisory, evidence-aware draft suggestions reviewed
side-by-side and explicitly accepted. SOL (M9D) stays unchanged; no other A2/A3 profile
runs. No finalized contract was modified; no new endpoint/mode/route/schema/migration.

## Branch / commit basis

- Branch **`feat/a2-value-creation`**, created from **`77f1a65`**
  ("Milestone M9D.2: add cloud processing confirmation gate for A2").
- Tag **`milestone-9d-2-cloud-processing-gate`** added on `77f1a65` (STEP 0 setup).
- **STEP-0 stabilization:** one pre-existing strict-null TypeScript error in the M9D.2
  e2e scaffolding (`e2e/a2-solution-innovation.spec.ts`, the Flow A
  `current_source_version_id` narrowing) was fixed so the precondition `tsc` gate was
  green. No auto-commit for M9E itself (only the STEP-0 tag + branch).

## Changed / new files

**Backend**
- `app/agents/a2_fields.py` (new) — the single, explicit, **registry-backed**
  field→profile allow-list (`A2_FIELD_PROFILES`), per-field config resolution
  (`resolve_field_config`: profile_id, registry char limit, registry mandatory markers,
  dev/test fake text) and `validate_a2_field_registry()` (fail-closed at import).
- `app/agents/field_drafting.py` — generalized from SOL-only constants to per-call
  config: `run_a2_field_drafting(field_id=…)` (+ a thin `run_a2_solution_innovation`
  wrapper for M9D), `availability(run, field_id)`, field-aware fake resolver, and
  `_validate_candidate`/`_mandatory_structure_ok` driven by the resolved config.
- `app/agents/field_drafting_context.py` — context assembly parameterized by
  `field_id` + `profile_id` (was hardcoded SOL); char limit, mandatory questions,
  linked requirements, evidence, open issues, facts and structured snapshot are
  resolved per field. Payload minimization unchanged.
- `app/fields/redraft_service.py` — threads the draft's `field_id` through availability,
  the audit detail and the executor (`redraft_executor(…, field_id)`).
- `app/api/fields.py` — createRedraft gate uses `field_id in A2_FIELD_PROFILES` (was a
  single-field equality); passes `field_id` to the background task.
- `app/agents/prompts/a2_value_creation_market_logic_v1.md` (new) — versioned VC prompt.

**Frontend**
- `lib/redraft.ts` — `VALUE_CREATION_FIELD_ID`, `A2_FIELD_IDS`, `isA2Field()`.
- `components/editor/live-editor.tsx` — the A2 control/side-by-side gate uses
  `isA2Field(selected.field_id)` (renamed `isSolutionField` → `showA2Controls`).

**Tests**
- `backend/tests/test_a2_value_creation.py` (new), `backend/tests/a2_helpers.py`
  (field-parameterized), `backend/tests/test_a2_generation.py` +
  `backend/tests/test_processing_gate.py` (new `availability(run, field_id)` signature),
  `test/live-editor-a2.test.tsx` (VC side-by-side + accept),
  `e2e/a2-solution-innovation.spec.ts` (VC cloud flow + unsupported-field 404).

## A2 profile + prompt + supported field

- Profile `A2.value_creation_market_logic` (agents_v1_1.yaml): input
  `FieldDraftingInput@v1`, output `PortalFieldDraftBundle@v1`, model primary
  `anthropic_sonnet_46` / fallback `openai_gpt_54` (provider class `anthropic_direct`),
  controls = the standard A2 set, advisory.
- Prompt version `a2_value_creation_market_logic_v1` (`status: active_m9e`).
- Supported field **only** `VC.BUSINESS_TARGETS_MODEL.EDITOR` (plus the unchanged SOL).

## Character limit + mandatory structure (registry-authoritative)

Both are resolved from the portal-field registry, never hardcoded:
- VC character limit **15,000** (SOL 25,000) — `PortalFieldDef.character_limit`.
- VC mandatory markers **3.1 / 3.2** (SOL 4.1–4.5) — derived from
  `Registry.mandatory_questions()`. **Note:** the registry defines only
  `VC.BUSINESS_TARGETS_MODEL.MANDATORY_3_1` and `MANDATORY_3_2`; the agents.yaml
  acceptance prose says "3.1–3.3", but the **registry is authoritative for structure**
  (milestone STEP 1/5/6), so validation checks the registry's actual two questions.

## Context assembly

Reuses the M9D pipeline, now field-keyed: current VC DraftVersion text; the registry
field profile (label, 15,000 limit, mandatory 3.1/3.2); requirement assessments + open
issues linked to the field (`affected_field_ids`); exact-verified EvidenceAnchors via
active EvidenceLinks; advisory A1 facts; structured project/partner snapshot. No full
documents, secrets, unrelated fields or other projects. Deterministic selection,
character budget, `context_hash`, selected/skipped counts; no raw context stored in
AgentInvocation.

## Validation rules

`field_id == VC.…EDITOR`; non-empty `suggested_text`; all registry mandatory markers
present; char count ≤ 15,000 (**never trimmed**); `evidence_anchor_ids` ⊆ the run's
verified anchors; `open_issue_ids` ⊆ the run's open issues; structured schema
(`PortalFieldDraftBundle@v1`) only — no status/requirement/field mutations. Invalid →
not persisted as proposed + ControlResult(OUTPUT_SCHEMA failed) + AuditEvent + safe
failure on the operation. The prompt forbids inventing market/competitor/customer/
revenue/NPV/go-to-market facts and requires explicit placeholders for missing data.

## createRedraft + accept / hide

- createRedraft (`POST /runs/{run_id}/fields/{field_id}/redrafts`): VC on an eligible
  cloud run → 202; stale base → 409; deterministic_only/local_only or provider
  unavailable → 503; unsupported field → 404; async only (suggestion in
  `operation.result`). SOL flow unchanged.
- Accept (`PATCH /runs/{run_id}/fields/{field_id}` with `source_operation_id`): backend
  verifies the operation/suggestion belongs to the same run/draft/field/base_version and
  the content hash matches → new `DraftVersion` `created_by=agent`, suggestion
  `accepted`, `recheck_required=true`, approval invalidated; old version immutable.
- Hide: client-only ("Vorschlag ausblenden"); no audited rejection. Never auto-applied.

## Side-by-side UI

The existing M9D editor side-by-side now renders for VC as well as SOL (gated by
`isA2Field`): current draft vs suggestion, rationale, evidence used, unresolved open
issues, character count, placeholder + unconfirmed-facts warnings, "Übernehmen" /
"Vorschlag ausblenden". AI controls appear **only** on SOL and VC; absent on all other
fields. Empty/unavailable states unchanged. No provider/model/confidence/raw-prompt.

## Data Policy + CostGuard

VC runs only on a `cloud_assisted` run created through the M9D.2 confirmation gate
(public/synthetic, NDA false, confirmation used, provider available or fake, route
active). `availability(run, VC)` reuses the M9D.2 data-policy + provider check.
Deterministic-only runs stay deterministic and show unavailable. CostGuard
(`max_per_run`) + Data Policy gate every call through the gateway, unchanged. No cloud
for internal/confidential/NDA; no silent mode conversion.

## Tests / verification (fake provider only)

- **Backend** `pytest`: full suite green (the M9D.2 baseline plus the new
  `test_a2_value_creation.py` — registry config, valid VC suggestion, over-limit,
  missing 3.1/3.2 structure, invented anchor, unknown open issue, blocked policy →
  no provider call, only-VC-profile-invoked, createRedraft VC 202 / SOL 202 /
  unsupported 404 / deterministic 503 / stale 409, accept → agent DraftVersion +
  recheck + approval invalidation).
- **Frontend** `vitest`: **114 passed** (incl. the new VC side-by-side + accept test and
  the unsupported-field-absent assertion). `eslint` clean; `tsc --noEmit` clean;
  `next build` succeeds.
- **Playwright** (`--workers=1`, backend `AGENT_FAKE_PROVIDER=true`): all 13 specs green,
  including the new **M9E Value Creation** flow (cloud run via the confirmation gate →
  createRedraft VC 202 → accept → agent DraftVersion + `recheck_required` → unsupported
  field 404) and the SOL/Flow-A/deterministic-unavailable cases; the seeded demo spec
  passes with `DEMO_DATA_ENABLED=true`.
- **Optional real-provider smoke:** not run — no provider key configured; the fake
  provider drives all mandatory tests, as required.

## Security controls

Generation records AgentInvocation / ControlResult / AuditEvent via the gateway and
mutates no RequirementAssessment, EvidenceAnchor, ReviewApproval or ExportArtifact.
Verified: no API key/secret strings in the live backend log; the user-facing suggestion
view (`operation.result`) carries no provider/model identifier (model_route/model_id
persist only on the internal DraftSuggestion row, as in M9D); no raw source/prompt in
logs or DB; `features.ai` stays absent/false; the field→profile allow-list is
fail-closed and validated against both registries at import.

## Known limitations

- A2 is available only for public/synthetic cloud runs; internal/confidential/NDA stay
  blocked. VC suggestions never invent market/competitor/revenue/NPV facts — missing
  data becomes explicit placeholders/open issues (no external research is performed).
- Two A2 fields only (SOL, VC); enabling another requires an explicit, registry-backed
  entry in `A2_FIELD_PROFILES` plus tests.
- Mandatory-structure validation follows the registry (3.1/3.2), which differs from the
  agents.yaml "3.1–3.3" prose (documented above).

## Readiness for M9G (A3 Evidence Consistency)

The A2 surface is now a clean, registry-driven, multi-field generalization with strict
validation, frozen cloud provenance, and auditable advisory suggestions that never
mutate evidence/requirement/approval state. A3 can read these advisory DraftVersions and
their evidence links without re-opening the data-policy boundary or the A2 contract.
M9E introduces no A3 behaviour and leaves the consistency-checking surface untouched —
**ready for M9G**.
