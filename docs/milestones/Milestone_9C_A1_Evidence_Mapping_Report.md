# Milestone 9C — A1 Evidence Candidate Mapping with Deterministic Quote Verification

## Basis

- Branch `feat/a1-evidence-mapping`, created from `57bf2c6` (M9B). Tag
  `milestone-9b-a1-fact-extraction` created on `57bf2c6` as part of STEP 0.
- Pre-implementation gate verified first: backend `pytest` 289 passed / 2 skipped,
  `tsc`/`lint` clean, tree clean.
- No automatic commit (only the STEP-0 tag + branch).

## Scope

Activates exactly one more profile — **`A1.evidence_candidate_mapping`** — inside the
existing `extract_facts_and_map_evidence` stage: assemble controlled context
(ExtractedFacts + requirements + fields + frozen fragments) → call A1 via the
ModelGateway → validate each proposed candidate against the RunSourceSnapshot → persist
**agent-origin EvidenceCandidates** → let the **unchanged deterministic M5 pipeline**
verify them (`verify_evidence_quote` → EvidenceAnchors) and link them
(→ RequirementAssessments). A1 only proposes; **only the deterministic verifier creates
`exact_verified`**, A1 never creates `human_verified`, never sets a verification status,
and never changes a RequirementAssessment. Not activated:
A1.public_competence_research, A2, A3. No finalized contract modified; no new public
endpoint; no AI UI; `capabilities.features.ai` stays false.

## Changed files

- **New** `app/agents/evidence_mapping.py` (orchestrator), `app/repositories/agent_proposals.py`
  (dedup + evaluation trail), migration `f3c5d7e9a1b2_evidence_candidate_origin.py`, 8 test
  modules + `tests/a1_mapping_helpers.py`.
- **Modified** `app/db/models.py` (EvidenceCandidate origin columns + `AgentEvidenceProposal`),
  `app/agents/schemas.py` (mapping I/O models), `app/agents/context.py`
  (`assemble_evidence_mapping_context`), `app/agents/prompts/a1_evidence_candidate_mapping_v1.md`
  (activated), `app/repositories/evidence.py` (`upsert_agent_candidate` + origin label),
  `app/runs/graph.py` (mapping call + evaluation backfill), `tests/test_a1_graph.py`
  (M9B assertion relaxed to "all A1, no A2/A3" since the stage now also runs mapping).
- **No frontend changes.**

## Migration

`f3c5d7e9a1b2` (`down_revision = e1b7f3a9c2d4`, M9B head): adds internal nullable columns
to `evidence_candidates` (`generation_origin` default `deterministic_lexical`,
`agent_invocation_id`, `profile_id`, `prompt_version`, `source_extracted_fact_id`) and
creates `agent_evidence_proposals`. The public anchor/link schemas are untouched.
UP/DOWN/REUP roundtrip verified clean.

## A1 evidence profile + prompt version

`A1.evidence_candidate_mapping` (`status: beta_active`, `advisory: true`): input
`EvidenceCandidateMappingInput@v1`, output `EvidenceCandidateMappingResult@v1`; tools =
the same 3 read-only context tools (already authorized, `network_access: none`); controls
add **CTRL.EVIDENCE_REQUIREMENT**; model `anthropic_haiku_45`/`openai_gpt_54_mini`; limits
`max_per_run: 1, max_retries: 1, timeout_seconds: 120, max_candidates_per_target: 5`;
data policy identical to M9B's A1. Prompt **`a1_evidence_candidate_mapping_v1`**
(`status: active_m9c`) requires structured output only, **exact (non-paraphrased) quotes
copied from a provided fragment**, valid fragment/target references, no verification
status, no requirement-status change, untrusted-source handling, and `unmapped_targets`
when support is insufficient.

## Context assembly

`assemble_evidence_mapping_context` reuses the M9B helpers (snapshot fragment retrieval +
requirement/field lookups, recorded as ToolInvocations under the mapping profile →
CTRL.TOOL_AUTHORIZATION) and adds the run's **ExtractedFacts** (ids/statements/status
only). Same payload minimization: deterministic selection, `max_input_fragments` cap +
char budget, boundary truncation, `context_hash` + selected/skipped counts on
`AgentInvocation.context_meta`; source text labelled untrusted; no secrets/keys.

## Candidate validation (STEP 5 — partial persistence)

The gateway validates the whole output against `EvidenceCandidateMappingResult@v1`
(invalid → reject the whole output). Per candidate, the orchestrator then (raw model
output never logged):
- target must be a **known requirement** (field/unknown targets → rejected/unmapped — see
  limitations);
- `fragment_id` must be in the selected snapshot set; `source_version_id`/`source_id` are
  derived from the DB fragment, never trusted from the model;
- the `quote` must occur in the fragment's `normalized_text` — **0 → reject**
  (paraphrased/invented), **1 → derive the span deterministically**, **>1 → reject**
  (`ambiguous_quote_position`);
- optional `extracted_fact_id` must belong to the run;
- `match_type` must be `exact_normalized`; the output carries **no** verification status
  (structurally impossible — `extra="forbid"`);
- per requirement, at most `max_candidates_per_target = 5`.
Valid candidates persist; each rejected one gets a warning ControlResult + audit. Valid
ones survive when others in the same output are rejected.

## Origin / deduplication design

`EvidenceCandidate.generation_origin` distinguishes `deterministic_lexical` (M5) from
`agent_a1_evidence_mapping` (A1) — **internal only; the public anchor/link contracts are
unchanged**. `upsert_agent_candidate` dedup-keys identically to M5
(`run, target_requirement_id, fragment_id, quote_hash`): a match against an existing
deterministic **or** agent candidate returns the existing row and creates **no duplicate**
(and the M5 `upsert_anchor` dedup means no duplicate anchor either). Every proposal —
persisted, deduplicated, or rejected — writes one **`agent_evidence_proposals`** row
(`proposed_by_agent`, outcome, candidate_id/existing_candidate_id,
`duplicate_of_deterministic`, reasons), backfilled after verify/link with
`verification_status` and `linked_assessment_id` for baseline-vs-agent evaluation
(internal; no OpenAPI exposure).

## Verification relationship (STEP 7 — authoritative, unchanged)

`verify_evidence_quote` remains the **only** source of `exact_verified`: an agent
candidate with `match_type=exact_normalized` whose derived span matches the frozen,
normalizer-locked version text → `exact_verified`; anything else → `unverified`/`rejected`.
A1 cannot set `verification_status` or create `human_verified`. Verified by tests
(agent quote → exact_verified only after the verifier runs; altered quote → unverified;
shared anchor with an identical deterministic candidate).

## Linking behaviour (STEP 8 — unchanged)

The existing `run_verification` and `materialize_links` iterate **all** candidates, so
agent anchors are verified and linked to RequirementAssessments by `target_requirement_id`
through the unchanged code (supplementary EvidenceLinks; **assessment status never
changes**). Existing `listEvidence`/`listRequirements` surface the new anchors/links via
existing APIs — no new endpoint.

## Data Policy behaviour

Identical to M9B: deterministic_only/local_only → skip (no provider call, no context);
confidential/NDA → blocked; internal/real_project → blocked without institutional approval
+ per-run confirmation (none in M9C → always blocked); public/synthetic cloud_assisted →
allowed if a route is available. No silent mode conversion; no UI cloud toggle.

## CostGuard behaviour

Reuses the M9B CostGuard (`max_per_run=1`, retry cap, timeout, token usage in
`UsageRecord`, `cost_chf=0.0` placeholder). **Replay-idempotency (corr #1):** a prior
**succeeded** AgentInvocation for `(run, A1.evidence_candidate_mapping)` short-circuits the
orchestrator — no second provider call, no new invocation, **not a new CostGuard call** —
so checkpoint replay / repeated stage execution is safe and cost-free.

## Fake-provider tests

All mandatory tests use the deterministic fake provider. Coverage: context (snapshot
facts/fragments, payload minimization, char budget + boundary truncation, fragment cap,
context_hash, tool authorization); gateway/fake (valid candidates, unmapped/missing,
malformed → info issue, timeout → info issue, provider-error → fallback → fail,
provider-unavailable → skip no issue, deterministic/confidential/internal gating,
CTRL.EVIDENCE_REQUIREMENT); validation (origin persistence, quote-must-exist, span
derived, requirement/field/unknown targets, out-of-snapshot, ambiguous, dedup vs
deterministic, per-target cap, no exact/human-verified from the model); verification
(exact_verified only via the verifier, altered quote unverified, anchor dedup, workspace
isolation); graph/replay/regression (cloud path creates candidates + completes;
deterministic-only skips with identical candidate counts; replay guard; only A1
invoked); evaluation trail (persisted_new/deduplicated/rejected proposals, backfilled
verification + link, idempotent backfill, issue discipline); security (no key / raw
output / full source in DB/audit; injection cannot verify evidence or change rules).

## Optional real-provider smoke status

`test_a1_mapping_real_provider_smoke.py`, gated by `RUN_REAL_PROVIDER_SMOKE=true`;
public/synthetic only; schema-valid-or-safe-failure; skips without the env or a key.
**Skipped** in this verification.

## Deterministic-baseline comparison

A1 evidence candidates are additive (own origin) and the verify/link code is unchanged, so
deterministic-only runs are functionally identical to the M5 baseline. A graph regression
test runs the stage on a deterministic-only run with a working agent provider available and
asserts **0 agent candidates** and a total candidate count equal to the baseline; the full
M4–M8.1 Playwright workflow (deterministic_only) is unchanged.

## Test results

- **Backend** `pytest`: **326 passed, 3 skipped** (289 baseline + 37 new mapping tests:
  context 5, validation 9, verification 4, gateway 10, evaluation 4, graph 3, security 2;
  3 env-gated smokes skipped). Migration roundtrip clean; app starts.
- **Frontend** `tsc --noEmit` 0, `pnpm lint` 0, `pnpm test` green — no frontend changes.
- **Playwright** (live servers): **9 passed + 1 seeded demo** (serial run). A parallel
  run showed transient single-writer-SQLite contention failures (different specs each run,
  all passing in isolation and serially) — not an A1 regression; these specs use
  deterministic_only runs where A1 mapping is skipped at the mode gate.

## Known limitations

- **Requirement-targeted candidates only.** `EvidenceCandidate` is requirement-targeted and
  `EvidenceLink` has no portal-field target; field-targeted evidence would require forbidden
  OpenAPI/model changes. A1 receives `target_field_ids` as context, but a field-targeted
  proposal is rejected/unmapped, never persisted.
- **Ambiguous quotes (the same passage appearing more than once in a fragment) are
  rejected** — the position-locked verifier needs an unambiguous span and recurring text is
  typically already covered by the deterministic baseline. (`needs_human_review` is a
  possible future enhancement.)
- Agent-origin metadata and the evaluation trail are internal (no OpenAPI exposure).
- In production without a provider key, mapping is invoked but the route is unavailable →
  skipped (internal-only, no user-visible issue); only genuine provider/timeout/schema
  failures create one info OpenIssue.

## Readiness verdict for M9D (A2 Solution & Innovation Drafting)

The A1 evidence-mapping path — context assembly via registered snapshot tools, ModelGateway
invocation with Data Policy + CostGuard + replay-idempotency, mandatory schema + provenance
validation, agent-origin candidate persistence with dedup, the deterministic verifier as the
sole authority for `exact_verified`, unchanged linking, the internal evaluation trail, and
full audit/control coverage — is implemented contract-faithfully and covered by
fake-provider tests, without touching the deterministic baseline, activating user-facing AI,
modifying a finalized contract, or leaking secrets/source text. The ModelGateway, the
context tool-services, the agent-origin pattern and the AgentInvocation/ControlResult/
ToolInvocation trail are reusable for **M9D A2 Solution & Innovation Drafting**, which will
generate draft text (a new output class, not evidence). Ready for M9D.
