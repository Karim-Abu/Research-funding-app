# Milestone 10.1 — Post-Audit Remediation Patch

**Scope:** fix the two High findings (F1, F3) from the post-M10 audit
([docs/audits/Post_M10_Code_Risk_Audit.md](../audits/Post_M10_Code_Risk_Audit.md)), clarify
the F2 documentation wording, and correct the related M10 report overclaim (F6). **No new
product feature, no finalized-contract change, no DB migration, fakes/deterministic only —
no real provider key anywhere.**

## Branch / commit basis
- Branch **`feat/evaluation-hardening`**, on top of `f23dd96` (post-M10 audit report) /
  `2309d9e` (Milestone 10).
- `git status` clean under `final_backend_contracts_v1_1/` (0 changes) and under
  `backend/app/migrations/` (0 changes — the pinned migration head `f3d7a9c2e5b1` is
  untouched).

## Audit findings addressed
| Finding | Severity | Status in M10.1 |
|---------|----------|-----------------|
| F1 — no-raw-log smoke did not prove the sanitized-query→provider path (`ResearchTask.query_text` + provider payload unchecked) | High | **Fixed** (new provider-path smoke + extended surfaces) |
| F3 — stale reliability neither surfaced nor enforced in the normal ReviewPackage/approval path | High | **Fixed** (Option A: stale blocks approval; visible run-level blocker finding; Review-Center banner) |
| F2 — deterministic sanitization presented as stronger than it is | Medium | **Clarified** (docs) |
| F6 — M10 report claimed provider-payload coverage the smoke did not provide | Info | **Corrected** (report wording) |
| F4 (pinned migration head), F5 (verify_all summary aliasing) | Low | Open — post-beta hygiene (unchanged) |

## Changed files
- **Backend:** `app/reliability/approval.py` (stale reason + `sync_stale_finding`),
  `app/review/package.py` (`refresh_package` syncs the stale finding; docstrings).
- **Backend tests:** `tests/test_m10_smoke.py` (new provider-path smoke; `test_no_raw_log`
  hardened to the deterministic block path + `ResearchTask.query_text` surface),
  `tests/test_review_approval.py` (new F3 regression test),
  `tests/test_reliability_pass.py` (stale-summary test updated to the new gate).
- **Frontend:** `lib/review-view.ts` (`reliabilityStaleFinding` detection),
  `components/review/live-review.tsx` (stale banner), `test/live-review.test.tsx` (+2 cases).
- **E2E:** `e2e/reliability-stale.spec.ts` (new).
- **Docs:** `docs/security/Search_Query_Firewall.md`, `docs/evaluation/Known_Limitations.md`,
  `docs/evaluation/Provider_Mode_Matrix.md`,
  `docs/milestones/Milestone_10_Evaluation_Hardening_Report.md` (corrected wording),
  `docs/audits/Post_M10_Code_Risk_Audit.md` (M10.1 remediation status appended), this report.

## F1 remediation details
New smoke **`test_m10_smoke.py::test_no_raw_d2_query_reaches_research_task_or_provider_payload`**
covering the sanitized-**approval** path (the block path alone was proven before):
- A D2 project carries synthetic markers (partner `Quellwerk Robotik AG`, codename
  `Silberfuchs` as project title, budget `484848`, secret-like token). The raw D2 query
  contains exactly the two **lexicon-removable** markers (partner + budget → risk 4), so the
  firewall deterministically returns `require_human_approval` — asserted hard, never block.
- Flow: firewall preview → human approval → research task with `approval_id` → execution
  against the **fake** provider (spy subclass injected via the existing test-only
  `set_override` hook in `app/research/providers/resolver.py` — no production change).
- Assertions: `ResearchTask.query_text == SearchQueryApproval.sanitized_query` (never the
  raw query); the spy received **exactly** the sanitized query (the test fails if the raw
  query were ever sent); `task.provider == "fake"`; raw markers absent from
  `AuditEvent`/`ControlResult`/`ToolInvocation`/`UsageRecord`/`ResearchTask.query_text`;
  only `raw_query_hash` + `sanitized_query` remain where designed.
- **Fake-provider guard:** the test asserts `web_research_fake_provider=True` and
  `d2_web_research_enabled=False` — no real Firecrawl/OpenAI/Anthropic/Azure call is
  possible or made.
- **`test_no_raw_log`** now pins the deterministic **block path** (codename = project title
  → partner + project + budget = risk 6 → block): nothing stored or sent, all markers —
  including the out-of-lexicon secret token — absent from every surface, now including
  `ResearchTask.query_text`.
- **Honest scope (F2 tie-in):** extending the checked surfaces demonstrated the F2
  limitation in practice — out-of-lexicon tokens (codename/secret) inside a raw query
  survive sanitization *by design* and would be stored/sent on the approval path. The test
  suite therefore separates the two paths and does **not** claim arbitrary secret tokens
  are detected. Technical-evidence export coverage of forbidden markers remains in
  `test_export_all_types`.

## F3 remediation details (Option A — stale blocks until a fresh pass)
- **Blocking:** `app/reliability/approval.py::reliability_blocker_reasons` now yields a
  run-level `reliability_stale:{run_id}` reason whenever a pass ran but its
  `RunQualitySummary` no longer matches the current inputs (`is_stale`). Because this
  function already feeds `review/service.py::approval_blockers`,
  `review/package.py::has_open_blocker` and `counts`, the stale state consistently:
  409-blocks `create_approval` (`approval_blocked`, reason visible in the problem detail),
  sets `approval_status="blocked"`, and raises `blocker_count` — through the **existing**
  approval path, for run **and** field scope (fail closed). Claim-bound M9K blocker
  semantics (corr 3/13: scope-bound, stale claim findings never block) are unchanged.
- **Surfacing:** `sync_stale_finding` idempotently maintains a **run-level blocker
  ReviewFinding** (`source="agent"`, `profile_id="M9K.reliability_assurance"`,
  `finding_code="reliability:stale:{run_id}"`, `target_type="run"`, `field_id=None`) —
  visible in the normal `ReviewPackage.findings`. Created/refreshed by
  `refresh_package` (i.e. on every recheck), **resolved — never deleted — after a fresh
  reliability pass** makes the summary current. No new ReviewPackage field, no contract
  change: the review UI identifies it by profile + missing field_id (claim-bound findings
  always carry a field_id).
- **Review Center:** `live-review.tsx` shows a visible banner —
  **"Qualitätsprüfung veraltet — bitte erneut ausführen."** — in the normal review path
  (not only the reliability GET view); the finding also appears as a blocker card and the
  approve button is disabled via the blocker count.
- **No silent mutation:** the pass/recheck still never mutate drafts, requirements,
  anchors or approvals; the only new write is the reliability-stale ReviewFinding row
  (+ audit events).
- **Lifecycle guarantees verified by test:** stale blocks; fresh pass resolves (stale
  findings do not falsely block forever); runs that never ran a pass are unaffected;
  approval afterwards follows the *current* findings (a still-unsupported strong claim
  keeps blocking via its scope-bound reason).

## F2 documentation clarification
Precise wording added (no code change): the **raw submitted D1/D2 query is not stored or
sent** (hash only); the `sanitized_query` is used after firewall + human approval; the
`sanitized_query` **may still contain undetected confidential terms** — deterministic
sanitization is **risk reduction, not a secrecy guarantee**; **D2 live-provider execution
remains default-off** and enabling it requires explicit governance approval and reviewer
diligence. Applied to `Search_Query_Firewall.md` (new "Limits of deterministic
sanitization" section), `Known_Limitations.md`, `Provider_Mode_Matrix.md`.

## Tests added / updated
| Test | Kind | Purpose |
|------|------|---------|
| `test_m10_smoke.py::test_no_raw_d2_query_reaches_research_task_or_provider_payload` | backend, **new** | F1: sanitized-approval path → stored query + provider payload clean |
| `test_m10_smoke.py::test_no_raw_log` | backend, updated | F1: deterministic block path; `ResearchTask.query_text` added to checked surfaces |
| `test_review_approval.py::test_stale_reliability_blocks_approval_or_requires_fresh_pass` | backend, **new** | F3: pass → blocker → edit → recheck → stale finding + 409 `reliability_stale` → fresh pass resolves → current findings govern |
| `test_reliability_pass.py::test_changed_draft_marks_summary_stale` | backend, updated | claim-bound reasons still empty when stale; the run-level stale reason replaces them |
| `test/live-review.test.tsx` (+2) | vitest, updated | banner shown for the run-level stale finding; NOT shown for claim-bound reliability findings |
| `e2e/reliability-stale.spec.ts` | Playwright, **new** | full UI flow: pass → edit → recheck → banner visible + approval 409 → fresh pass → banner gone |

## Verification results (fakes only, no real key)
- **Backend `pytest`: 499 passed, 3 skipped** (M10: 497 + the two new M10.1 tests).
- **Frontend:** vitest **130 passed** (M10: 128 + 2), `eslint` clean, `tsc --noEmit` clean,
  `next build` OK.
- **`verify_all.ps1` (one-command verification): ALL GREEN** — backend tests pass ·
  migration pass · vitest pass · build/typecheck/lint pass · **Playwright 27 passed**
  (M10: 26 + the new `reliability-stale.spec.ts`) · **API smoke 18/18** · export smoke pass
  · no-raw-log pass · EvaluationRunSummary written.

## Remaining limitations
- **F2 stays a by-design limitation** (now precisely documented): deterministic
  sanitization cannot detect arbitrary confidential tokens; the human approval + the
  default-off D2 live gate remain the load-bearing controls.
- **F4/F5 (Low)** remain open post-beta hygiene: pinned migration head; verify_all summary
  lines aliasing the backend pytest result.
- All M10 Known Limitations continue to apply (no NDA/D3 processing, Azure documented-not-
  deployed, etc.).

## Readiness verdict for supervised user evaluation
With F1 and F3 remediated and verified (both High audit findings closed; F2 clarified in
docs; no finalized contract modified; no new feature; no migration), the audit's gate
condition is met: **the supervised user evaluation can start.** The system remains a
supervised beta — human review is required for every claim, and it is **not**
production-ready (Azure target architecture documented, not deployed; DPA + FHNW
data-protection review outstanding).
