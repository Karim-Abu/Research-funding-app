# Post-M10 Code, Architecture & Risk Audit

**Date:** 2026-07-02 · **Basis:** branch `feat/evaluation-hardening`, commit `2309d9e`
(Milestone 10), working tree clean, no changes under `final_backend_contracts_v1_1/`.
**Method:** read-only inspection of code, tests, scripts and docs (no code executed against
live providers; no state-changing commands). Every finding cites file + function evidence.
Anything that could not be proven from code/tests/docs is marked **not verified**.

**Finding categories used throughout:** `code defect` · `test coverage gap` ·
`documentation overclaim` · `by-design limitation`.

---

## 1. Executive verdict: **CONDITIONAL PASS**

- **0 Critical · 2 High (F1, F3) · 1 Medium (F2) · 2 Low (F4, F5) · 1 Informational (F6).**
- **No confirmed code defect** was found in the must-not-fail areas. The two High findings
  are a test-coverage gap on a NO-FAIL surface (F1) and a by-design approval-staleness gap
  with High evaluation-readiness impact (F3).
- The core privacy invariant holds, stated precisely (and only this precisely):
  1. The **raw submitted D1/D2 query is not stored and not sent** — it is hashed and
     discarded (`app/research/service.py::_firewall_query`,
     `app/security/approval_service.py::consume_for_task`).
  2. External calls use the **`sanitized_query`** only after deterministic firewall
     screening **plus** single-use human approval.
  3. The `sanitized_query` **may still contain undetected confidential terms** — the
     deterministic firewall removes only structured-lexicon terms and generic patterns (F2).
  4. **Therefore D2 live-provider execution is gated and default-off**
     (`d2_web_research_enabled=false`; fake provider only in the beta,
     `app/research/executor.py`).
  This audit does **not** claim "D1/D2 confidential content can never be sent"; the accurate
  claim is the four-part statement above.
- **Gate:** evaluation should **not** start before F1 and F3 are remediated **or explicitly
  accepted (documented) as supervised-evaluation risks.**

---

## 2. Top risks

| # | Risk | Finding | Severity |
|---|------|---------|----------|
| 1 | The no-raw-log smoke does not check `ResearchTask.query_text` or the provider-received payload, and does not pin the sanitized-query→provider path — the strongest privacy claim is under-proven by tests | F1 | High |
| 2 | After a draft edit + deterministic recheck, a run with a previously open M9K reliability blocker can be **approved without a fresh reliability pass and without any `reliability_stale` warning** in the ReviewPackage/approval path — the run *appears* reliability-checked while the current draft is not | F3 | High |
| 3 | The deterministic firewall cannot detect arbitrary confidential tokens (codenames, product names, secret-like strings); "public-safe query" wording overstates the machine guarantee — the real controls are the human approval + the D2 live-gate | F2 | Medium |
| 4 | M10 report wording ("no-raw-log smoke … provider payloads") overstates what the smoke proves | F6 (→F1) | Info |
| 5 | Migration test pinned to head `f3d7a9c2e5b1`; only the latest migration is round-tripped | F4 | Low |
| 6 | `verify_all` summary lines for "export smoke"/"no-raw-log" alias the whole backend-pytest result rather than the named test cases | F5 | Low |

---

## 3. Critical no-fail area assessment

### A. Raw confidential data must not leak — **PASS** (with F1 proof-gap + F2 caveat)
- **Evidence:** `app/research/service.py::_firewall_query` is the service-layer chokepoint:
  D3/UNKNOWN → `ResearchBlocked` (fail closed); D1/D2 require an `approval_id`, and
  `_consume` → `app/security/approval_service.py::consume_for_task` validates the raw-query
  **hash** (mismatch → expired), enforces single-use (`status="used"`), and returns only
  `approval.sanitized_query`. `create_research_task` persists `query_text = sanitized query`
  — never the raw. `approval_service._record_decision` stores metadata only, with an
  `assert_no_raw_query` backstop. The technical export forbids `raw_query`/`prompt_text`/
  `provider_payload`/`sk-` markers (`tests/test_m10_smoke.py::test_export_all_types:115`).
  `RedactingFilter` scrubs query markers from logs (`test_log_redaction_scrubs_query_marker`).
- **Precise wording (see §1):** raw not stored/sent; sanitized after firewall + approval;
  sanitized may retain undetected confidential terms; D2 live gated default-off.
- **Files inspected:** `app/research/service.py`, `app/security/approval_service.py`,
  `app/security/search_query_firewall.py`, `app/security/confidential_terms.py`,
  `app/research/executor.py`.
- **Tests inspected:** `tests/test_m10_smoke.py::test_no_raw_log`,
  `::test_export_all_types`, `::test_log_redaction_scrubs_query_marker`.
- **Remaining concern:** the test proof is narrower than the code guarantee (F1); the
  sanitizer's coverage limit is real (F2).

### B. Agents must not bypass policy gates — **PASS**
- **Evidence:** all research goes through `create_research_task`/`_firewall_query` (service
  layer, not agent code); the only provider construction point is
  `get_web_provider(settings)` in the executor; grep found no direct
  Firecrawl/Anthropic/OpenAI client construction outside the gateway/resolver chokepoints.
  `executor.py` re-checks class defensively (D3/UNKNOWN → `_block_task`) and enforces
  `d2_web_research_enabled or web_research_fake_provider` before any D2 call. Fake flags
  select fake implementations; they cannot flip a real call on (resolver returns the fake).
- **Remaining concern:** none confirmed. That *every* future agent path will route through
  the service is an architectural convention, not compiler-enforced — **not verified**
  beyond current call sites.

### C. Evidence must not be falsely trusted — **PASS**
- **Evidence:** sufficiency logic keeps `exact_verified` distinct from "supports";
  coverage is computed separately from sufficiency (M10 EvaluationRunSummary keeps
  `evidence_coverage` separate from `evidence_sufficiency_pass_rate`); quantified claims
  require matching numbers; generic evidence does not satisfy specific claims; A1 output is
  proposed-not-confirmed; A3 is advisory (silence ≠ correctness, agreement does not override
  missing evidence — `review/recheck.py::_maybe_run_a3` persists findings only on a
  successful schema-valid bundle and never auto-approves).
- **Remaining concern:** the sufficiency check is lexical/heuristic — documented honestly in
  `docs/evaluation/Known_Limitations.md` ("appears to support under defined criteria").

### D. Approval gating must be correct — **RISK (F3, High)**
- **Evidence for the correct part:** `review/service.py::create_approval` enforces the
  scope-hash stale-guard (409 `review_package_stale`) and `approval_blockers` (409
  `approval_blocked`), which includes scope-bound reliability blockers
  (`reliability_approval.reliability_blocker_reasons`, service.py:398). ReviewApproval
  invalidation on edit works; `approval_status` reads invalidated approvals as "stale".
- **The gap (verified escalation chain, F3):**
  1. Draft edit sets `recheck_required=True` (`repositories/drafts.py:271`,
     `fields/service.py:46`, `api/fields.py:206`) and changes the reliability scope hash →
     the `RunQualitySummary` goes stale (`reliability/approval.py::current_summary:27–35`).
  2. The deterministic recheck (`review/recheck.py::recheck_executor` →
     `review/package.py::refresh_package(clear_recheck=True)`:381–387) clears
     `recheck_required` "even if blocker findings remain" (docstring) and **never re-runs the
     reliability pass** ("NEVER re-runs the graph"; only optional advisory A3).
  3. `has_open_blocker` (`review/package.py:283–298`) excludes M9K findings from the generic
     blocker path, and `_reliability_blocks` → `[]` when the summary is stale; `counts`
     (:318–324) reports `blocker_count` **without** the still-open M9K blocker finding.
  4. `approval_status` is not "blocked"; `approval_blockers` yields no reliability reason;
     `create_approval` **succeeds** while an open `severity=blocker` M9K ReviewFinding exists.
  5. `reliability_stale` exists **only** in the reliability GET view
     (`reliability/service.py:72,112`; `contracts/reliability.py:69`) — grep confirms zero
     occurrences in `review/` or `contracts/review.py`. Partial mitigation: the open blocker
     finding is still *listed* in `ReviewPackage.findings` (`review/service.py:116–126`),
     but `blocker_count=0` + `approval_status="open"` contradict it and approval proceeds.
- **Tests inspected:** approval/stale-guard tests exist for the current-scope path; **no test
  covers** draft-edit → recheck → approve-with-open-M9K-blocker.
- **Status:** the code matches its own spec (M9K corr 3: stale ≠ block) — a **by-design
  limitation**, not a code defect — but High for evaluation readiness (see F3).

### E. No silent mutation — **PASS**
- **Evidence:** the reliability pass writes only its own artifacts (DraftClaim lineage,
  RunQualitySummary) + ReviewFindings (source="agent", profile `M9K.reliability_assurance`)
  + ReviewPackage metadata; recheck "NEVER … mutates historical artifacts" and never changes
  `run.status` (`review/recheck.py` docstrings + code); export writes only `ExportArtifact`.
  No M9G/M9K/M10 path mutates `DraftVersion.text`, Requirements, EvidenceAnchors,
  EvidenceLinks, ReviewApprovals or MarketComparison.

### F. Workspace / auth isolation — **PASS**
- **Evidence:** `api/market.py`, `api/firewall.py`, `api/reliability.py` all use
  `require_session`/`require_unsafe_guards` and scope loads via
  `projects_repo.get_scoped(db, project_id, workspace_id)` /
  `approval_service.get_scoped(db, approval_id, context.user.workspace_id)`; cross-workspace
  IDs 404. **Not verified:** endpoints outside the M9/M10 surfaces were sampled, not
  exhaustively re-audited in this pass.

### G. Export safety — **PASS**
- **Evidence:** technical evidence export uses `claim_hash` (no `claim_text`), carries the
  reliability `quality_summary`, and the smoke asserts absence of
  `claim_text`/`raw_query`/`sk-`/`prompt_text`/`provider_payload`
  (`test_export_all_types:115–116`). Research `query_text` (sanitized) is project-scoped and
  not part of the run export.

### H. M10 reproducibility — **PASS**
- **Evidence:** `scripts/verify_all.{sh,ps1}` export one shared `DATABASE_URL` for servers +
  Playwright's seed subprocess; `--evaluation` seed is a deterministic superset and plain
  `--reset` is byte-identical (`test_m10_eval_seed.py`); migration tests run a real
  `alembic` subprocess on a throwaway SQLite DB (`test_m10_migrations.py`); **no mandatory
  step requires a real provider key** (verified across scripts + test env flags).
- **Remaining concern:** F4/F5 (pinned head; aliased summary lines).

---

## 4. Confirmed findings

| ID | Severity | Type | Category | Finding | Evidence | Impact | Suggested fix | Suggested test |
|----|----------|------|----------|---------|----------|--------|---------------|----------------|
| F1 | **High** | Test coverage gap (privacy NO-FAIL surface) | test coverage gap | `test_no_raw_log` omits `ResearchTask.query_text` and the provider-received payload from its checked surfaces, and does not pin whether the sanitized-query→provider path runs | `backend/tests/test_m10_smoke.py:156–175` — blob built only from `AuditEvent.detail`, `ControlResult.detail`, `ToolInvocation.input_hash/output_hash`, `UsageRecord.provider/model`. Lines 144–154 enter the approval branch only *if* the firewall returns `require_human_approval` (with these markers — partner + budget + currency + keyword — the block branch is likely; branch outcome **not pinned by an assertion**), and even then nothing asserts on the stored query or the fake provider's received query | The system's strongest privacy claim is proven only for 4 of its ~6 persistence/egress surfaces; the M10 report cites this smoke as covering provider payloads | **MUST-FIX before evaluation.** Extend the smoke to cover: (a) `ResearchTask.query_text`, (b) the fake provider's received query / provider request payload, (c) the **sanitized-query approval path** (an approved D1/D2 task that actually reaches the provider), not only the block path — proving raw codename, raw D2 query, secret-like token and budget marker reach neither the stored query nor the provider payload | Extend `test_no_raw_log`: force/assert the `require_human_approval` branch, run the task to completion, then assert markers absent from `ResearchTask.query_text` and from the fake provider's captured request |
| F2 | **Medium** | Security/Privacy (risk, not a default-config leak) | **primary:** by-design limitation (F2a) · **secondary:** documentation overclaim (F2b) | F2a: the deterministic firewall cannot detect arbitrary confidential tokens — it removes only structured-lexicon terms (project title, partner names, representatives, budget) + generic regex (email/phone/currency/NDA/keyword); internal codenames, product names, secret-like tokens and short technical IP remain in `sanitized_query`, which is stored in `ResearchTask.query_text` and, for D2, would be sent to a provider. F2b: "public-safe query" wording overstates this guarantee | `app/security/search_query_firewall.py::evaluate_query/build_lexicon/_decide`; `app/security/confidential_terms.py::CATEGORY_WEIGHTS`; mitigations: HITL approves the *visible* sanitized query; `app/research/executor.py` `d2_web_research_enabled` gate (default false → fake provider only in beta) | If D2 live research is ever enabled, an undetected confidential term could reach an external provider despite "sanitization"; the real controls are the human + the live-gate, not the sanitizer | Documentation-level: state sanitized ≠ machine-clean; require explicit reviewer diligence + risk sign-off before enabling `d2_web_research_enabled`; consider an entropy/unknown-token heuristic post-beta | A test asserting an out-of-lexicon codename survives sanitization (documents the limit) + a config test that `d2_web_research_enabled` defaults to false |
| F3 | **High (evaluation readiness)** | Approval/HITL · MAS reliability | by-design limitation (with High impact) | A run with a previously open M9K reliability blocker can be **approved after a draft edit** without a fresh reliability pass and without any `reliability_stale` warning in the ReviewPackage/approval path — full chain in §3.D | `reliability/approval.py:27–35, 43–49`; `review/recheck.py` (never re-runs reliability); `review/package.py:283–298, 318–324, 381–387`; `review/service.py:116–126, 398`; `reliability_stale` only in `reliability/service.py:72,112` + `contracts/reliability.py:69` (zero hits in review layer) | M9K is the main protection against unsupported claims and false consensus; in this state the run *appears* reliability-checked (a pass exists, approval succeeds) while the **current** draft was never checked — false assurance during the very evaluation meant to measure it, and it undermines the reviewer-facing trust signal (UX goal) | **MUST-FIX before user/supervisor evaluation.** (1) Surface `reliability_stale` in the ReviewPackage / Review Center; (2) block approval — or require an explicit fresh reliability pass — when stale reliability + an open prior M9K blocker finding exist together; (3) add the regression test (next column) | Reliability pass with blocker → edit draft → deterministic recheck → **approval must be blocked or a stale warning must be visible** |

**Classification note (per audit directive):** none of F1–F3 is a *code defect* — the code
matches its own specs. F1 is a test coverage gap on a NO-FAIL surface; F2 is a by-design
limitation whose documentation overstates it; F3 is a by-design limitation (M9K corr 3
docstrings: stale ≠ block; the promised "non-blocking `reliability_stale` note" was only ever
implemented in the reliability view, not the review surface) whose *impact* on evaluation
readiness is High.

---

## 5. Potential risks (lower severity)

| ID | Severity | Type | Category | Risk | Evidence | Suggested handling |
|----|----------|------|----------|------|----------|--------------------|
| F4 | Low | Data model / migration | test coverage gap | `test_m10_migrations.py` hardcodes `_HEAD="f3d7a9c2e5b1"` and round-trips only the latest migration (`-1`); the next migration breaks the test instead of the test adapting | `backend/tests/test_m10_migrations.py` | Post-beta: derive head from `alembic heads`; keep the pinned value as a change-detector only if intentional |
| F5 | Low | Evaluation / reproducibility | documentation overclaim | `verify_all` prints "export smoke" and "no-raw-log" summary lines that alias the whole backend-pytest result (`verify_all.sh:115` `R_EXPORT="$R_BACKEND"; R_NORAWLOG="$R_BACKEND"`; `verify_all.ps1:123`) — misleading if those cases are later renamed/removed/skipped | `scripts/verify_all.sh:114–115,128–129`; `scripts/verify_all.ps1:123,132–133` | Post-beta: run the two named test cases explicitly (`pytest tests/test_m10_smoke.py::test_...`) for those lines |
| F6 | Informational | Docs / overclaim | documentation overclaim | M10 report says the no-raw-log smoke covers "provider payloads" — it does not (ties to F1; the *export* smoke's provider-payload check is accurate). `EvaluationRunSummary.dataset_id` is an unlabelled project UUID | `docs/milestones/Milestone_10_Evaluation_Hardening_Report.md:81–84`; `app/evaluation/summary.py` | Correct the report sentence when fixing F1; optionally label the dataset id |

---

## 6. Test coverage matrix (no-fail areas × tests)

| No-fail area | Covering tests (inspected) | Coverage judgment |
|---|---|---|
| A. Raw D1/D2 never stored/sent | `test_no_raw_log`, `test_export_all_types`, `test_log_redaction_scrubs_query_marker`, firewall/approval unit tests (M9J suite) | **Partial — F1**: 4 persistence surfaces + logs + export covered; `ResearchTask.query_text` + provider payload + approval path not asserted |
| B. No policy-gate bypass | M9J firewall tests (block/approve/single-use/hash-mismatch), executor gate tests, fake-provider mode tests | Adequate for current call sites |
| C. Evidence not falsely trusted | M9K sufficiency suite (exact_verified≠supports, coverage≠sufficiency, quantified claims), A1/A3 boundary tests | Adequate |
| D. Approval gating | scope-hash stale-guard tests, `approval_blocked` tests (current scope) | **Gap — F3**: no test for edit→recheck→approve-with-open-M9K-blocker |
| E. No silent mutation | recheck/reliability read-only tests, export artifact tests | Adequate |
| F. Workspace isolation | scoped-404 tests on market/firewall/reliability endpoints | Adequate for beta surfaces (full-API sweep **not verified**) |
| G. Export safety | `test_export_all_types` forbidden-marker assertions | Adequate |
| H. Reproducibility | `test_m10_migrations.py` (3), `test_m10_eval_seed.py` (4), `verify_all` orchestration | Adequate (F4/F5 hygiene notes) |

---

## 7. Code paths reviewed

1. **Research query lifecycle:** `app/research/service.py::_firewall_query/_consume/
   create_research_task` → `app/security/approval_service.py::run_preview/decide/
   consume_for_task/_record_decision` → `app/security/search_query_firewall.py::
   evaluate_query/build_lexicon/_decide` → `app/security/confidential_terms.py`.
2. **Execution + provider boundary:** `app/research/executor.py` (D0/D1/D2/D3 branches,
   `d2_web_research_enabled` gate, `_block_task`) → `app/providers/resolver.py::
   get_web_provider`.
3. **Review/approval:** `app/review/service.py::read_review_package/approval_blockers/
   create_approval` → `app/review/package.py::compute_scope_hash/package_version/
   _open_findings/_reliability_blocks/has_open_blocker/counts/approval_status/
   refresh_package` → `app/review/recheck.py::prepare_recheck/recheck_executor/_maybe_run_a3`.
4. **Reliability gating:** `app/reliability/approval.py::latest_summary/current_summary/
   is_stale/reliability_blocker_reasons/has_reliability_blocker`;
   `app/reliability/service.py` (view, `reliability_stale`).
5. **Edit-invalidation triggers:** `app/repositories/drafts.py:271`,
   `app/fields/service.py:46`, `app/api/fields.py:206`.
6. **Auth/workspace:** `app/api/market.py`, `app/api/firewall.py`, `app/api/reliability.py`
   (`require_session`, `require_unsafe_guards`, `get_scoped`).
7. **M10 surfaces:** `backend/tests/test_m10_smoke.py`, `test_m10_migrations.py`,
   `test_m10_eval_seed.py`, `scripts/verify_all.sh`, `scripts/verify_all.ps1`,
   `scripts/smoke_api.py`, `app/evaluation/` , `app/demo/seed.py`/`reset.py`.
8. **Docs vs code:** `docs/milestones/Milestone_10_Evaluation_Hardening_Report.md`,
   `docs/evaluation/Known_Limitations.md`, `Provider_Mode_Matrix.md` (Azure = target
   architecture, not deployed — consistent with code).

---

## 8. Commands run (all read-only)

- `git status` (clean) · `git log --oneline` (M10 = `2309d9e`) · `git branch` /
  `git tag` (through `milestone-9k-mas-reliability-assurance`) ·
  `git diff HEAD -- final_backend_contracts_v1_1/` (empty — contracts untouched).
- ripgrep sweeps: provider-client construction outside the gateway/resolver (none);
  `reliability_stale` across `backend/app` (reliability view + reliability contract only);
  `recheck_required` write sites; `get_scoped`/`workspace_id` on beta endpoints.
- **`verify_all` was NOT re-run** in this audit (it starts servers and writes DBs — outside a
  read-only pass). The M10 report's recorded results are cited instead: backend pytest
  **497 passed / 3 skipped**, vitest **128**, Playwright **26**, API smoke **18/18**.
  Those numbers are therefore **reported, not independently reproduced, by this audit**.

---

## 9. Final recommendation

- **Safe for supervised thesis demo** after this audit report.
- **Safe for supervised user evaluation ONLY after F1/F3 remediation or explicit, documented
  risk acceptance.** Evaluation should not start before then.
  - **F1:** extend the no-raw-log smoke to `ResearchTask.query_text`, the provider-received
    payload, and the sanitized-query approval path.
  - **F3:** surface `reliability_stale` in the ReviewPackage / Review Center; block approval
    or require an explicit fresh reliability pass when stale reliability + an open prior M9K
    blocker coexist; add the regression test (pass-with-blocker → edit → recheck → approval
    blocked or stale warning visible).
- **Not production-ready.** Azure AI is a documented target architecture, not a deployment;
  a DPA + FHNW data-protection review are outstanding; the F2 firewall limitation must be
  revisited before any `d2_web_research_enabled` (live D2) enablement.
- **Can wait post-beta:** F2 doc clarification can ship with/before the evaluation; F4
  (migration-head pinning), F5 (verify_all summary aliasing), F6 (report wording +
  dataset-id label) are post-beta hygiene.
