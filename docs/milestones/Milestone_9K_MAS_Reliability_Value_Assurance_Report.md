# Milestone 9K — MAS Reliability & Value Assurance

**Scope:** a deterministic, testable reliability layer over the current DraftVersions of a
completed run. It extracts *claims*, maps their *lineage*, checks whether evidence actually
*supports* each claim (a sufficiency check separate from mere anchor presence), gates strong
unsupported claims, detects false consensus and semantic drift, and emits a per-run
**RunQualitySummary** for M10 evaluation. Fully deterministic — **no provider call** (A3 is
read only as an already-persisted advisory signal). Not a new product feature.

## Branch / commit basis
- Branch **`feat/mas-reliability-assurance`**, from **`7d67dd0`** ("Milestone 9J: privacy
  leakage controls and search query firewall").
- Tag **`milestone-9j-privacy-leakage-controls`** added on `7d67dd0` (STEP 0).
- No M9K auto-commit (only the STEP-0 tag + branch).

## Contract decision
No reliability object exists in any finalized contract (schema_catalog / controls / openapi /
Domain_Model — all checked). M9K is **code-only beta-internal**: three internal tables, a
beta-internal endpoint, and reliability findings that **reuse `ReviewFinding`** (see below).
`git status` shows **no change under `final_backend_contracts_v1_1/`**.

## Changed files
- **New (backend):** `app/reliability/` (`extract, sufficiency, lineage, scope, gate,
  false_consensus, glossary, drift, summary, approval, service, executor, __init__`),
  `app/api/reliability.py`, `app/contracts/reliability.py`,
  `app/migrations/versions/f3d7a9c2e5b1_reliability_tables.py`,
  `tests/test_reliability_pass.py`, `tests/reliability_fixtures/`.
- **Modified (backend):** `app/db/models.py` (+3 tables), `app/review/{package,service}.py`
  (scope-bound reliability gating), `app/exports/{snapshot,generators/technical_evidence}.py`,
  `app/api/capabilities.py` (+`reliability`), `app/main.py` (router).
- **New (frontend):** `lib/reliability.ts`, `components/review/quality-summary.tsx`,
  `app/api/runs/[id]/reliability/route.ts`, `test/quality-summary.test.tsx`,
  `e2e/reliability.spec.ts`.
- **Modified (frontend):** `components/review/live-review.tsx`, `lib/capabilities.ts`.
- **Docs:** `docs/reliability/{M9K_Reliability_Gap_Audit,Architecture_Assurance_Matrix}.md`,
  this report.

## Data model (migration `f3d7a9c2e5b1`, down_revision `e2b6c4f8a1d3`)
- **`draft_claims`** — deterministic, **position-aware `claim_id`** = hash(run_id,
  draft_version_id, field_id, start_char, end_char, source_text_hash); `claim_type`,
  `strength`, `requires_evidence`, `source_text_hash` (=`claim_hash`), `source_scope_hash`.
  `claim_text` is internal-only.
- **`claim_lineages`** — per claim: `lineage_status`, `sufficiency_status`, `provenance`
  (fact/anchor/candidate/fragment/suggestion/market/a3 ids), `matched_terms`, `reason`.
- **`run_quality_summaries`** — all named metrics + `source_scope_hash` + `status`
  (current|stale|failed) + `quality_flag`.

## Claim lineage & evidence-sufficiency design
Claims are extracted deterministically (`discovery._spans` + versioned keyword lexicons;
conservative `requires_evidence`). Lineage gathers in-run provenance; an anchor counts as
*coverage* when linked to the field's draft version. **Sufficiency is a separate check**
(`app/reliability/sufficiency.py`): key-term overlap + type-specific terms (market/innovation/
partner_fit) + number matching for quantified claims. **`exact_verified` never auto-implies
`supports_claim`** — a verified-but-off-topic quote is `does_not_support`; generic overlap is
`weakly_supports`; a quantified claim without a matching number is `insufficient`. Wording is
an "evidence sufficiency check … appears to support under defined criteria / needs human
review", never "verified as true".

## Unsupported-claim gate & scope-bound approval
`gate.py` maps (strength × lineage × sufficiency) → findings persisted via a dedicated
`apply_reliability_findings` as `ReviewFinding(source="agent",
profile_id="M9K.reliability_assurance", finding_code="reliability:*",
target_type="draft_claim")` — the **binding-correction-1 fallback** (verified: `source` is a
free string; no new enum, no migration for findings). `review/service.py::approval_blockers`
and `review/package.py::{has_open_blocker,counts}` were extended (guarded) so a **strong
unsupported claim blocks approval**, but **only** when its target claim belongs to the
**current, non-stale** `RunQualitySummary` (corr 3/13). M9K findings are excluded from the
generic blocker path; the scope-bound check adds them. Runs with no pass are unaffected.

## False-consensus & semantic-drift guards
- **False consensus:** an A2-authored claim + no open A3 finding on the field + M9K
  sufficiency no/insufficient → risk finding. "A3 silence is not evidence"; A3 agreement never
  overrides a missing/insufficient anchor (corr 8).
- **Semantic drift:** a versioned glossary + deterministic co-occurrence patterns
  (exact_verified=approved, ReviewApproval=submission, eligibility=decision, public=
  confidential-safe, Innovation/Value-Creation reductions) → field-level warning findings.

## Conservative uncertainty marking
Reuses `ReviewFinding`/`ReviewPackage` only — strong unsupported/conflicting → blocker (not
ready); weak/insufficient/proposed-A1-as-certain/market-without-quote/overconfident → warning
(needs_review). No new public status; no draft/Requirement/EvidenceAnchor/Approval mutation.

## RunQualitySummary & metric discipline
Deterministic, reproducible. `evidence_coverage` (any linked evidence) is kept **separate
from** `evidence_correctness_sample_pass_rate` (sufficiency). High coverage + low sufficiency
⇒ **`quality_flag = risky`**, never success (corr 9). Cost is **nullable + `cost_placeholder`**
(never invented). `source_scope_hash` **excludes this pass's own M9K findings** (corr 11) so a
pass never staleifies itself; a later input change flips `status` to `stale`. Idempotent per
scope hash (corr 6): re-running on the same scope reuses the summary and re-derives no
duplicate claims/findings.

## API / UI / export
- Beta-internal `POST /runs/{id}/reliability` (202 async) + `GET /runs/{id}/reliability`
  (summary + per-claim lineage/sufficiency + findings). The authenticated, workspace-scoped
  GET may include `claim_text` (same authz as `DraftVersion.text`); audit/logs/export never do.
- Read-only **"Qualitätsübersicht"** card in the Review Center (`quality-summary.tsx`), gated
  by the `reliability` capability — counts + risk flag + blockers/warnings; **no confidence
  %, no provider/model names**.
- Technical-evidence export gains a `reliability` block: RunQualitySummary + a
  `claim_lineage_summary` of **`claim_hash` + field_id + claim_type + strength +
  lineage_status + sufficiency_status only — never `claim_text`** (corr 5/14). No raw
  prompts/provider outputs/D1-D2 queries/secrets.

## Tests & results (deterministic, no provider)
- **Backend `pytest`: 487 passed, 3 skipped** (+18 — `test_reliability_pass.py`): the 10
  regression fixtures (unsupported market, wrong quote, generic evidence, quantified-missing-
  number, proposed-A1-as-confirmed, A2-invented-competitor, A3-false-non-flag, drift,
  conflicting, properly-supported), plus exact_verified≠supports, coverage≠correctness,
  scope-bound approval blocking, idempotency + no-draft-mutation, stale-on-change,
  no-claim_text-in-audit, export block without claim_text, and endpoint + workspace isolation.
- **Frontend `vitest`: 128 passed** (+2 — `quality-summary.test.tsx`: metrics + risk flag +
  blockers, no provider/model/%; empty-state → run pass). `eslint` clean; `tsc --noEmit`
  clean; `next build` OK.
- **Playwright (`--workers=1`, fakes): 24 passed, 1 skipped** (+2 — `reliability.spec.ts`:
  pass → summary → **no draft mutation** → technical export carries the summary without
  claim_text; UI Quality Summary renders in the Review Center, no provider branding). All
  M9E/M9G/M9I/M9J specs stay green.

## Acceptance criteria — status
1 claims extracted ✓ · 2 strong unsupported detected ✓ · 3 sufficiency ≠ presence ✓ ·
4 exact_verified ≠ supports ✓ · 5 A1 proposed ≠ confirmed ✓ · 6 A3 silence ≠ validation ✓ ·
7 drift detected ✓ · 8 weak/uncertain → needs_review/blocker ✓ · 9 RunQualitySummary ✓ ·
10 Architecture Assurance Matrix ✓ · 11 regression fixtures (false/wrong/weak/drift) ✓ ·
12 no silent mutation ✓ · 13 export has reliability summary without raw leaks ✓ ·
14 full suite green ✓ · 15 no finalized contract modified ✓.

## Known limitations
- Deterministic extraction/sufficiency are conservative heuristics (lexical/quantitative
  criteria), not semantic understanding — hence "needs human review" and block-on-uncertainty.
  `agent_assisted_if_available` extraction is a documented hook (not built; no provider).
- The Playwright e2e runs on template drafts (pipeline + export + no-mutation guarantees);
  the specific negative-case detections are covered exhaustively by the backend fixtures.
- The reliability pass changes the review-package scope hash (new findings), which correctly
  invalidates a prior sign-off; a fresh pass is required after any draft edit.

## Readiness verdict for M10 Evaluation & Hardening
M9K delivers exactly what M10 needs: a deterministic, reproducible, per-run **RunQualitySummary**
that separates evidence *coverage* from *correctness*, plus auditable claim-level lineage and
scope-bound reliability findings — all beta-internal with no finalized-contract change and all
prior flows intact. The summary + Architecture Assurance Matrix give M10 a concrete metric
surface and a risk→control→test→artifact map. **Ready for M10 Evaluation & Hardening.**
