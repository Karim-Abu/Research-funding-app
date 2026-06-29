# Milestone 9G — A3 Evidence Consistency Review

**Scope:** activate **exactly one** A3 profile, `A3.evidence_consistency`, which reviews
current draft text against available evidence and produces **advisory `ReviewFinding`s**.
It never approves/rejects, never edits drafts, and never mutates requirement or evidence
status. A3 runs only as part of a **targeted recheck** on an eligible cloud-assisted
(public/synthetic) run; the existing M7 ReviewPackage/approval gating absorbs the
findings. No finalized contract modified; no new endpoint, no migration.

## Branch / commit basis

- Branch **`feat/a3-evidence-consistency`**, created from **`e9f8fcd`**
  ("Milestone 9E: A2 Value Creation draft suggestions").
- Tag **`milestone-9e-a2-value-creation`** added on `e9f8fcd` (STEP 0 setup).
- No M9G auto-commit (only the STEP-0 tag + branch).

## Changed / new files

**Backend**
- `app/agents/schemas.py` — new Pydantic `CriticReviewInput` + `ReviewFindingBundle`
  (with `ReviewFindingRecord` / `ProfileReviewSummaryRecord`, `extra="forbid"`), both
  registered in `SCHEMA_MODELS`.
- `app/agents/a3_review.py` (new) — the A3 profile id + scoped fields, fail-closed
  validated against both registries at import.
- `app/agents/critic_review_context.py` (new) — `CriticReviewInput` assembly over the
  scoped fields (reuses the A2 read-only tool-services); proposed A1 facts are rendered
  as *unbestätigt* context only.
- `app/agents/critic_review.py` (new) — A3 orchestrator: `availability(run)` (cloud gate)
  + `run_a3_evidence_consistency(...)` (gateway invoke, output validation, deterministic
  fake) + `A3Finding`/`A3Outcome`.
- `app/review/package.py` — `apply_agent_findings(...)` (source=agent upsert/dedup/
  resolve) alongside the unchanged deterministic `apply_findings`.
- `app/review/recheck.py` — `recheck_executor` runs A3 on an eligible cloud run before
  `refresh_package`.
- `app/agents/prompts/a3_evidence_consistency_v1.md` — activated (`status: active_m9g`).
- `tests/test_a3_evidence_consistency.py` (new); `tests/test_agent_schemas.py` (the
  "unimplemented schema" example repointed to a still-unimplemented A3 schema).

**Frontend**
- `lib/review-view.ts` — `isAiFinding` / `aiFindings` / `deterministicFindings` +
  `AI_FINDINGS_LABEL`/`_DESCRIPTION`.
- `components/review/live-review.tsx` — a dedicated **"KI-gestützte Hinweise"** section
  (`AiFindingCard`); the deterministic groups/blocker cards/hints stay deterministic-only.
- `components/editor/live-editor.tsx` — a **"KI-Prüfung"** badge on field-level A3
  findings.
- `test/live-review.test.tsx`, `e2e/a3-evidence-consistency.spec.ts` (new).

## A3 profile + prompt + scoped fields

- Profile `A3.evidence_consistency` (agents_v1_1.yaml): input `CriticReviewInput@v1`,
  output `ReviewFindingBundle@v1`; model primary `openai_gpt_54` / fallback
  `anthropic_sonnet_46`; advisory; limits `max_per_run_bundle:1, max_retries:1,
  timeout 240, max_findings 10/30`. Prompt version `a3_evidence_consistency_v1`.
- Scoped fields (a permitted subset of the profile's selectors):
  **`SOL.INNOVATION_SOLUTION.EDITOR`** + **`VC.BUSINESS_TARGETS_MODEL.EDITOR`**.

## Context assembly

Minimal, evidence-focused, only for scoped fields with a current **non-empty**
DraftVersion: current draft text + field id/label; active draft EvidenceLinks +
exact-verified anchor quotes/status; requirement assessments + deterministic rule
results for the fields; A2 lineage when a version is `created_by=agent`; active blocker
open issues. **Corr 1:** `confirmed_facts` carries only genuinely confirmed facts (empty
in the current system); proposed A1 facts appear **only** as explicitly *unbestätigt*
context, never as confirmed. No full source documents, secrets, unrelated fields or other
projects. Deterministic selection, char budget, `context_hash`, selected/skipped counts,
no raw context stored in AgentInvocation.

## Output validation

The gateway validates the provider output against `ReviewFindingBundle@v1` (`extra=
"forbid"` rejects any approval/confidence/draft-replacement/status-mutation key →
`SafeFailure`). The orchestrator then drops any per-finding whose `field_id` is out of
scope or whose `requirement_id`/`evidence_anchor_id`/`evidence_link_id` does not exist in
the run; a per-finding target failure never fails the whole bundle. Severity/status are
enum-constrained. A skipped/failed/blocked run carries **no** findings.

## ReviewFinding mapping + persistence

Findings persist as `ReviewFinding` with `source="agent"`,
`profile_id="A3.evidence_consistency"`, `advisory = severity != "blocker"`, target
`field_id` (or `requirement_id`). Dedup uses a stable `finding_code = a3:sha256(profile,
field, requirement, anchor, link, normalized description)` under the existing
`(run_id, source, finding_code)` unique constraint. Repeated A3 runs upsert; agent
findings of the same profile no longer emitted auto-resolve. Deterministic and human
findings are never touched; historical findings are not deleted. **Corr 2:**
`apply_agent_findings` runs **only** after a successful schema-valid bundle — a policy
block / provider-unavailable / timeout / schema failure / CostGuard block preserves prior
A3 findings and records the failure separately. The public contract exposes `profile_id`
but not `source`/model/provider.

## ReviewPackage integration + recheck

`recheck_executor` runs A3 on an eligible cloud run, persists findings on success, then
`refresh_package(clear_recheck=True)`. The M7 counting is unchanged: `has_open_blocker` /
`counts` / `approval_status` already consider **all** open findings, so an active A3
blocker sets `approval_status="blocked"` and an info/warning does not. **Corr 3:** a
successful recheck clears `recheck_required=False` even when an A3 blocker keeps approval
blocked. Deterministic-only / ineligible runs skip A3 and stay purely deterministic. A3 is
**never** auto-run on edits; the user explicitly triggers the recheck.

## Data Policy + CostGuard

`critic_review.availability(run)` requires `cloud_assisted` + public/synthetic (via
`data_policy.evaluate` on the A3 profile) + an available provider/fake; otherwise A3 is
unavailable. Every invocation flows through the gateway, which enforces the A3 profile's
Data Policy + CostGuard (`max_per_run_bundle:1`) + the control set. Internal/confidential/
NDA and deterministic/local runs make **no** provider call.

## Frontend labels

Review Center shows A3 findings under **"KI-gestützte Hinweise"** (advisory, "Vorschläge
zur menschlichen Prüfung — keine Freigabe"); the editor tags field-level A3 findings with
a **"KI-Prüfung"** badge. No model/provider names, no confidence values, no wording
implying the KI grants approval. Deterministic blockers stay in their own sections.

## Tests / verification (fake provider only)

- **Backend** `pytest`: full suite green, incl. the new `test_a3_evidence_consistency.py`
  (context scope + `confirmed_facts` empty; scope-empty skip; eligibility deterministic/
  confidential/cloud; output validation incl. invalid field/anchor + approval-key
  rejection; agent-source persistence + dedup + deterministic-separate + resolve-unseen;
  blocker-blocks/info-doesn't; recheck triggers A3 on cloud, not on deterministic; recheck
  clears `recheck_required` with a blocker; failed A3 preserves prior findings).
- **Frontend** `vitest`: **115 passed** (incl. the A3 review grouping/labelling +
  no-provider assertion). `eslint` clean; `tsc --noEmit` clean; `next build` succeeds.
- **Playwright** (`--workers=1`, `AGENT_FAKE_PROVIDER=true`): all 15 specs green, incl.
  the new A3 spec (cloud recheck persists an A3 finding; deterministic recheck does not
  run A3) and the seeded demo.
- **Optional real-provider smoke:** not run — no provider key configured; the fake
  provider drives all mandatory tests.

## Security controls

A3 mutates no draft, RequirementAssessment, EvidenceAnchor or ReviewApproval and creates
**only** advisory ReviewFindings. Verified: no API key/secret in the live backend log; the
persisted/served finding carries `profile_id` + `source=agent` but no model/provider; no
raw source/prompt in logs or DB; prompt-injection treated as untrusted data; `features.ai`
stays false. A3 never auto-approves or auto-dismisses.

## Known limitations

- A3 is recheck-triggered only and runs only on public/synthetic cloud runs; internal/
  confidential/NDA and deterministic runs keep deterministic-only review.
- Scope is SOL + VC (the A2-enabled, highest-evidence-risk fields); the profile permits
  more prefixes (INTRO./ORG./PS.) which are intentionally out of M9G scope.
- `confirmed_facts` is empty until a human fact-confirmation flow exists; proposed A1
  facts are surfaced only as unconfirmed context.

## Readiness for M9H / M9I

A3 establishes the advisory, gated, auditable agent-review surface (source=agent
ReviewFindings, recheck-triggered, no contract/migration change) that the next A3 profiles
(M9H Innovation Challenge) or research milestones (M9I Market Research) can extend by
adding a profile + scope without re-opening the data-policy boundary or the ReviewFinding
mapping. **Ready for M9H/M9I.**
