# Milestone 9B — A1 Project Fact Extraction with Provenance, Policy Controls & Safe Persistence

## Basis

- Branch `feat/a1-fact-extraction`, created from `e9e3a6d` (M9A,
  "Milestone 9: add agent infrastructure and model gateway"). Tag
  `milestone-9a-agent-infrastructure` created on `e9e3a6d` as part of STEP 0.
- Pre-implementation gate verified first: backend `pytest` 258 passed / 1 skipped,
  `tsc`/`lint` clean, tree clean.
- No automatic commit (only the STEP-0 tag + branch).

## Scope

Activates exactly one agent profile — **`A1.project_fact_extraction`** — inside the
existing `extract_facts_and_map_evidence` run stage: assemble controlled context
from the immutable RunSourceSnapshot → call A1 through the ModelGateway → validate
provenance → persist **advisory** ExtractedFacts (proposed / conflicted / missing) →
continue the deterministic M5/M4 pipeline **unchanged**. A1 output is advisory
(`output_authority: proposal_requires_validation`); it never confirms facts, changes
RequirementAssessments, verifies evidence or satisfies hard rules. **Not activated:**
A1.evidence_candidate_mapping, A1.public_competence_research, A2, A3. No new
user-facing AI; `capabilities.features.ai` stays false; no finalized contract modified.

## Changed files

- **New** `app/agents/context.py` (snapshot context assembly + 3 tool-services),
  `app/agents/fact_extraction.py` (A1 orchestrator — the single entrypoint),
  `app/repositories/extracted_facts.py`, migration
  `e1b7f3a9c2d4_extracted_facts.py`, 8 test modules + `tests/a1_helpers.py`.
- **Modified** `app/db/models.py` (`ExtractedFact` + `AgentInvocation.context_meta`),
  `app/agents/gateway.py` (context fields + composite input_hash + prompt assembly),
  `app/agents/schemas.py` (`ExtractedFactRecord.fact_type`/`normalized_value`),
  `app/agents/prompt_assets.py` (`prompt_instructions_for`),
  `app/agents/prompts/a1_project_fact_extraction_v1.md` (activated body),
  `app/config/settings.py` (`a1_context_char_budget`),
  `app/runs/graph.py` (A1 call in the stage node).
- **No frontend changes.**

## Migration

`e1b7f3a9c2d4` (`down_revision = d9a4b2c6e8f3`, the M9A head): creates
`extracted_facts` (unique `(run_id, fact_fingerprint)`) and adds nullable
`agent_invocations.context_meta`. UP/DOWN/REUP roundtrip verified clean (table
created, dropped, recreated; `context_meta` present).

## A1 profile used

`A1.project_fact_extraction` (resolved from `agents_v1_1.yaml`): `status: beta_active`,
`advisory: true`; `input_schema: ProjectFactExtractionInput@v1`, `output_schema:
ProjectFactExtractionResult@v1`; `allowed_tools: [retrieve_source_fragments,
lookup_requirement_definition, lookup_portal_field_profile]`; `model: {primary:
anthropic_haiku_45, fallback: openai_gpt_54_mini}`; `invocation_limits: {max_per_run:
1, max_retries: 1, timeout_seconds: 120, max_input_fragments: 80}`. Only this profile
is invoked — tests assert no A2/A3 AgentInvocation is created.

## Prompt version

`a1_project_fact_extraction_v1` (frontmatter `status: active_m9b`). The activated body
encodes the profile instruction contract (structured output only; no invented facts;
null/missing for absent values; explicit conflicts; provenance for every fact; fragment
ids exactly from context; never change requirement statuses / verify / approve; source
content is untrusted data). `prompt_assets.prompt_instructions_for` loads the body for
the prompt (placeholder prompts are excluded); `prompt_version_for` records the version
on the AgentInvocation and every ExtractedFact.

## Context assembly design (`app/agents/context.py`)

Three **read-only, snapshot-scoped tool-services** — model code never touches the DB
and gets no file/network/arbitrary-DB access:
- `retrieve_source_fragments` — fragments from the **RunSourceSnapshot only**, in
  deterministic canonical order (snapshot source `created_at`,`source_document_id`,
  then fragment `ordinal`), de-duplicated, each block carrying fragment_id,
  source_version_id, source title, page/section/ordinal and normalized text.
- `lookup_requirement_definition` / `lookup_portal_field_profile` — active requirement
  ids/titles and A1-prefixed (INTRO./ORG./VC./SOL./PS.) portal field ids/labels.

**Payload minimization (corr #2):** both the `max_input_fragments=80` cap **and** an
explicit character budget (`settings.a1_context_char_budget`, default 24000) are
enforced; over budget → **deterministic truncation at fragment boundaries** (trailing
fragments dropped, never mid-fragment). A **`context_hash`** is computed over the final
delimited context and non-sensitive **metadata** (selected/skipped fragment counts,
char budget, total chars) is recorded on `AgentInvocation.context_meta`. Each of the
three tool calls records a **ToolInvocation** (existing M8 mechanism, caller =
`A1.project_fact_extraction`) → **CTRL.TOOL_AUTHORIZATION**. Source text is labelled
untrusted data; no secrets/keys.

## Provenance validation (`fact_extraction._persist`, partial persistence)

Two-tier, documented:
- **Whole-output (gateway):** output must validate against
  `ProjectFactExtractionResult@v1` **and** every fact's `source_fragment_ids` must be a
  subset of the selected snapshot set. A hallucinated / outside-snapshot /
  foreign-workspace fragment in *any* fact → the entire output is rejected (schema
  failure after retry → safe failure, **no facts**), guaranteeing the gateway never
  returns a fact citing a disallowed fragment.
- **Per-fact (orchestrator, partial):** for output whose references are all valid, a
  fact is individually rejected (warning ControlResult + `extracted_fact.rejected`,
  others still persist) when its `target_ref` does not resolve to a known requirement
  or portal field, or it duplicates an existing fingerprint. Missing-information entries
  need no provenance; conflicts inherit the referenced facts' fragments. Requirement
  statuses are never touched (no such field exists in the schema).

## Persistence design (`extracted_facts`)

One internal table (no public endpoint — none exists in OpenAPI; `extracted_fact` is an
existing `target_type` enum value used for anchors/audit). Stores fact_type,
normalized_value, original_statement, status, requirement_id/field_id, provenance
(`source_fragment_ids`/`source_version_ids`), and lineage (profile_id, model_route,
model_id, schema_version, prompt_version, agent_invocation_id) — **never full source
documents**. **M9B writes only `proposed`/`conflicted`/`missing`; never
`confirmed`/`rejected`** (those require a real HumanDecision in a later milestone).
Idempotency: insert-if-absent keyed by `(run_id, fact_fingerprint)`; new runs (new
run_id) create new facts; terminal historical facts are never rewritten.

## Graph changes (`node_extract_facts_and_map_evidence`)

The node now calls `fact_extraction.run_a1_fact_extraction(db, run)` **before** the
existing `evidence_pipeline.run_discovery(db, run)`. A1 never raises into the graph
(a defensive wrapper records `agent.fact_extraction.failed` and continues). The graph
uses a module-level `_PROVIDER_RESOLVER` (default `gateway.default_provider_resolver`)
so production without a key marks the route unavailable → safe skip; tests monkeypatch
it to inject the fake provider. Cancellation check stays first; checkpoints unaffected;
no A2/A3 node added. Deterministic-only runs (the deterministic beta default) skip A1
at the mode gate — no provider call, no context assembly, no invocation.

## Data Policy behaviour

The orchestrator gates before any payload is built: `deterministic_only`/`local_only`
→ **skipped** (no provider call, no context); cloud_assisted runs the M9A
`data_policy.evaluate` — public/synthetic → allowed; confidential → blocked; NDA →
blocked; internal/real_project → blocked unless `agent_institutional_route_approved`
(default false) **and** a per-run external-processing confirmation (no mechanism in
M9B → always blocked). On block: `CTRL.DATA_POLICY=blocked`, AuditEvent, **no facts**,
deterministic pipeline continues. Processing mode is never silently up/down-graded.

## CostGuard behaviour

Reuses the M9A CostGuard: per-(run, profile) call count (`max_per_run=1` → a second A1
call on the same run is blocked, no duplicate facts), retry cap, timeout, output-token
cap. Token usage is persisted in `UsageRecord`; **no pricing config exists so CHF cost
is never invented** — `cost_chf=0.0` is a non-nullable placeholder, never surfaced.

## Fake-provider tests

All mandatory tests use the deterministic fake provider (no network/key). Coverage:
persistence (proposed/conflict/missing; confirmed/rejected never created; idempotent
upsert; workspace isolation), provenance (valid; hallucinated / outside-snapshot /
foreign-workspace fragment rejected; invalid requirement/field rejected; partial
persistence), gateway integration (success / missing / conflict / malformed / timeout /
provider-error-then-fallback / provider-unavailable-skip / extra-field rejected), data
policy (skip/allow/block matrix with provider-call-count assertions), cost guard
(max_per_run, usage tokens), prompt injection (source instructions cannot change
rules/tools/secrets), and graph (cloud path persists facts + runs discovery,
deterministic-only skips, A1 does not change deterministic evidence counts, only A1
invoked).

## Optional real-provider smoke status

`test_a1_real_provider_smoke.py`, gated by `RUN_REAL_PROVIDER_SMOKE=true`; public/
synthetic source only; uses the normal pipeline; asserts a schema-valid result or a
safe failure (no crash, no leak); skips cleanly without the env or a key. **Skipped**
in this verification.

## Security controls

Source content is untrusted data, never instructions; the prompt embeds it in a
delimited `UNTRUSTED SOURCE DATA` block and the injection test confirms embedded
"ignore instructions / reveal secrets / grant tool access" cannot change rules, tools
or leak secrets. Provider output cannot call tools (orchestrator-only). The
`AgentInvocation.input_hash` is a **composite over the complete model-facing input**
(profile_id, prompt_version, schema_id, model_route, input_payload_hash, sorted selected
fragment ids, context_hash) — auditable and reproducible, with **no raw context or full
prompt text stored** (corr #3). No API key / full prompt / full source text / raw
provider payload is logged or persisted; AuditEvents carry only ids/counts.

## Deterministic-baseline preservation

Proposed A1 facts live in their own table and are **never read** by any deterministic
stage. A regression test runs A1 + discovery on one run and discovery-only on an
identical run and asserts the EvidenceCandidate count is identical. Deterministic-only
runs are functionally unchanged apart from A1 skip ControlResult/AuditEvent rows. The
full M4–M8.1 Playwright workflow (deterministic_only runs) is unaffected.

## Test results

- **Backend** `pytest`: **289 passed, 2 skipped** (258 baseline + 31 new A1 tests across
  persistence 4, provenance 7, gateway 8, data-policy 6, cost-guard 2, injection 1,
  graph 3; 2 env-gated smokes skipped). Migration roundtrip clean; app starts (agent
  registry + new model load).
- **Frontend** `tsc --noEmit` 0, `pnpm lint` 0, `pnpm test` green, `pnpm build` success
  — no frontend changes.
- **Playwright** (live servers): **9 passed + 1 seeded demo passed** — deterministic
  M4–M8.1 workflow unchanged. Capabilities expose no `ai`/cloud to normal users.

## Known limitations

- Provider unavailability (no key) and policy blocks surface **internally only**
  (ControlResult + AuditEvent); only **genuine** failures (schema-fail-after-retry,
  provider error after fallback, timeout) create one idempotent **info-severity
  OpenIssue** targeting the agent invocation (`issue_type=ai_extraction_unavailable`,
  `target_type=agent_invocation` — an established target_type, corr #1).
- Hallucinated/invalid evidence references reject the **whole** output (gateway
  guarantee); only target-resolution/duplicate issues are partial (documented above).
- The per-run external-processing confirmation for internal data has no UI yet, so
  internal/real_project A1 is always blocked in M9B (by design).
- A1 facts are internal (no public endpoint); no AI UI is activated.

## Readiness verdict for M9C (A1 Evidence Candidate Mapping)

The A1 fact-extraction path — context assembly via registered snapshot tools, ModelGateway
invocation, Data Policy + CostGuard enforcement, mandatory schema + provenance
validation, advisory ExtractedFact persistence with idempotency, info-issue failure
surfacing, and full audit/control trails — is implemented contract-faithfully and
covered by fake-provider tests, without touching the deterministic baseline, activating
any user-facing AI, modifying a finalized contract, or leaking secrets/source text. The
ModelGateway context channel, the snapshot tool-services and the AgentInvocation/
ControlResult/ToolInvocation trail are reusable for **M9C A1 Evidence Candidate
Mapping**, which will map facts/requirements/fields to fragments using the same
controlled boundary. Ready for M9C.
