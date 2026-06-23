# Milestone 4 — Requirement Registry, Deterministic Rule Engine, Partner Eligibility & Live Requirements Workspace — Final Report

**Branch:** `feat/requirements-rules` (off tag **`milestone-3-run-orchestration`** @ M3 commit `f848bda`).
**Date:** 2026-06-23. **Status:** ✅ Complete — all acceptance criteria met. **Not committed**
(only the `milestone-3-run-orchestration` tag + `feat/requirements-rules` branch were created).

Delivers the **first real analysis slice**: load the versioned **RequirementDefinitions** + **12 official
core RuleDefinitions** → freeze an immutable **project + partner snapshot** at run creation → run a
deterministic **rule engine** in the new graph stage `evaluate_requirements_and_rules` → persist
**RuleResults**, aggregate **RequirementAssessments**, generate **OpenIssues** → expose
`listRequirements` → a **live Anforderungen workspace** + **partner management UI** → `features.runs`
activated. A completed run now means *"Fördervoraussetzungen und verfügbare formale Angaben wurden
geprüft"* — **not** a complete proposal analysis.

**No** LLM/semantic assessment, evidence/anchors/links, drafting, critic, review/approval, export,
recheck, human overrides, portal-field gates, Firecrawl/URL/OCR. **No** generic expression evaluator —
no `eval`/`exec` anywhere in the rule path (guarded by a test).

---

## 1. Changed / new files
**Backend (new):** `app/registry/{__init__,loader}.py`, `app/rules/{__init__,inputs,handlers,engine,
aggregation}.py`, `app/runs/{project_snapshot,evaluation}.py`, `app/contracts/{partner,requirement}.py`,
`app/api/{partners,requirements}.py`, `app/repositories/{partners,requirements}.py`,
`app/migrations/versions/d3a1b6e4f2c7_requirements_rules_partners.py`, `tests/{test_registry_rules,
test_partners,test_requirements_flow}.py`.
**Backend (modified):** `app/db/models.py` (+5 models), `app/api/{runs,capabilities}.py`,
`app/runs/{graph,constants}.py`, `app/main.py` (routers + fail-closed registry load), `app/config/
settings.py`, `requirements.txt` (PyYAML pin).
**BFF (new):** `app/api/projects/[id]/partners/route.ts` (GET,POST), `app/api/partners/[id]/route.ts`
(PATCH,DELETE), `app/api/runs/[id]/requirements/route.ts` (GET).
**Frontend (new):** `lib/{partners,requirements}.ts`, `components/partner/partner-manager.tsx`,
`components/anforderungen/live-requirements.tsx`, `test/{partners,requirements}.test.ts`,
`e2e/requirements-rules.spec.ts`.
**Frontend (modified):** `lib/{app-mode,capabilities}.ts`, `app/{partner,anforderungen}/page.tsx`,
`test/runs.test.ts` (capability assertion).

## 2. Registry loading + validation (fail-closed)
`app/registry/loader.py` loads `requirements.yaml` (RequirementDefinitions) + the
`official_core_rules` of `innosuisse_innovation_project_v1_1.yaml`, validates `registry_id`,
`schema_version`, referential integrity (every linked rule must exist) and `assessment_basis`, then
builds the **evaluable subset** = active, user-facing requirements whose linked rules are all known core
rules → exactly the **12 REQ.INNO.\*** (REQ.PORTAL.\* quality-gate requirements have empty
`linked_rule_ids` and are out of M4 scope). Any corruption/drift raises `RegistryError`; the app loads
+ validates the registry **at startup** so a broken policy stops the app rather than evaluating runs.
Versions: requirement registry **1.0.0**, rule registry **1.1.0** (frozen onto each run snapshot).

## 3. Deterministic rule engine (no eval/exec, registry-driven)
Dispatch by `condition.type` (10 handlers: `exists`, `human_reviewed_questionnaire`,
`max_exclusive_percent`, `range_percent`, `min_percent`, `no_upper_threshold`, `advisory_range`,
`max_value`, `aggregate_submission_gate`, `conditional_human_gate`). Each handler is a **pure function**
that determines which `result_mapping` branch holds; thresholds/ranges (20 %, 40–60 %, 5 %, 6–36, 18) are
**read from the registry condition**, never hardcoded. `applies_when` gates applicability
(`implementation_partner_count` gte/eq). **Missing inputs → `needs_input`**, never a guessed pass/fail.
The richer `result_mapping` outcome label (`warning`, `human_decision_required`, …) is preserved
alongside the canonical **RuleResult status** `passed | failed | needs_input | not_applicable`
(Domain Model). **All 9 registry `test_cases` pass** as parameterized tests.

## 4. Structured inputs (Partner schema, M4 scope)
`RuleInputs` is built from the **frozen** project + partner snapshot only. The four partner rules are
evaluable from the Partner schema (`swiss_value_creation`, `research_partner_eligibility_status` +
`country`, `personnel_independence_status`, `financial_independence_status`). Budget, duration,
portal-field and scientific-integrity inputs are **not captured in M4** → those rules resolve to
`needs_input` (honest), and `MAX18`/`TYPICAL`/`NO_FORMAL_MAX` resolve to `not_applicable` /`needs_input`
via `applies_when` on the implementation-partner count.

## 5. Aggregation → RequirementAssessment (conservative, contract-faithful)
`aggregate()` maps a RuleOutcome + the requirement's `assessment_basis`/`severity` to the contract
status enum (`fulfilled | partial | open | needs_input | blocked`); `basis` = the registry
`assessment_basis`:
- missing input → **needs_input**; applicable blocker rule fails → **blocked**;
- hybrid rule passes at machine level but needs human confirmation → **partial**;
- advisory `warning` outside range → **partial** (never blocked unless the registry marks it blocker);
- `human_decision_required` / semantic-with-inputs unresolved → **open**;
- deterministic rule passes with no outstanding condition → **fulfilled**;
- **not applicable** → persisted as a `not_applicable` RuleResult, **omitted** from the user list
  (the status enum has no "not_applicable" value — omission is contract-faithful).
No confidence percentages.

## 6. OpenIssues (deduplicated)
One OpenIssue per unmet/unresolved requirement (unique on `(run_id, target_type, target_id)`):
blocked→blocker, needs_input→warning, open→blocker/warning by severity, partial→info; each with a German
`recommended_next_action`. Fulfilled requirements create none. `target_type="requirement"`,
`target_id=requirement_id`, `status="open"`.

## 7. Immutable project+partner snapshot + staleness
`RunProjectSnapshot` freezes the structured project + partner inputs + a deterministic SHA-256
`content_hash` + both registry versions at run creation. The run is always evaluated against this frozen
copy. `listRequirements` recomputes the current inputs hash and surfaces **staleness** when it differs —
shown as *"Projektangaben wurden seit dieser Prüfung geändert. Starten Sie die Prüfung erneut."* The run
is **never** silently re-evaluated.

## 8. Graph stage + persistence
The LangGraph workflow gains a `evaluate_requirements_and_rules` node between
`validate_source_snapshot` and `finalize_run` (the canonical fact-extraction + drafting stages remain
out of scope). The node reloads the run, short-circuits on cancellation, runs `evaluation.evaluate_run`
(idempotent: clears prior artifacts first), records a `run.requirements_evaluated` control + audit event
with issue counts, then advances the stage. `STAGE_PROGRESS` is now 25/50/75/100.

## 9. API (exact v1.1 operationIds)
`listPartners` (GET `/projects/{id}/partners`), `createPartner` (POST → **201**, CSRF +
Idempotency-Key), `updatePartner` (PATCH `/partners/{id}` → 200, full replace via PartnerCreate),
`deletePartner` (DELETE → **204**), `listRequirements` (GET `/runs/{id}/requirements` → 200
`[RequirementAssessment]`). All workspace+project scoped (foreign → 404); mutations require
session + CSRF + Origin; partner enums validated (invalid → 422). Migration `d3a1b6e4f2c7` adds
`partners`, `run_project_snapshots`, `rule_results`, `requirement_assessments`, `open_issues`
(unique constraints on `(run_id, requirement_id)` and `(run_id, target_type, target_id)`); upgrade +
downgrade verified clean through all 4 revisions.

## 10. Frontend (mock preserved)
`lib/partners.ts` + `lib/requirements.ts` clients (CSRF + Idempotency on mutations); BFF routes forward
through the bridge. **Partner management** (`/partner`) — live list + create + delete form; mock mode
keeps the placeholder. **Anforderungen** (`/anforderungen`) — in live mode loads the latest completed
run's assessments, renders German status labels (Erfüllt/Teilweise/Offen/Angaben nötig/Blockiert), basis
labels, recommended actions, and the staleness banner; mock mode keeps the elaborate mock screen
unchanged. `features.runs/partners/requirements` advertised true; `review`/`export`/`web_research`
remain false; `processing_mode` stays `deterministic_only`.

## 11. Capability activation
`capabilities.features.runs=true` (+ `partners`, `requirements`) was flipped **after** the full flow +
all tests pass. AI/semantic/review/export features stay **false** — truthful advertisement of the
deterministic-only slice.

## 12. Security / control / audit
Session + CSRF + Origin on all mutations; workspace/project scoping; Problem Details, no stack traces.
**Controls:** `run.requirements_evaluated`. **Audit:** `partner.create/update/delete`,
`run.requirements_evaluated`. **No source text, secrets, or full private payloads** are logged — rule
`observed` values are structured (counts, statuses, percentages, registry condition), never raw text.

## 13. Test results
| Suite | Result |
|---|---|
| Backend `python -m pytest` | ✅ **81 passed** (+33 M4: registry load/fail-closed, 9 parametrized rule test_cases, applies_when/not_applicable/advisory, aggregation mapping, no-eval guard, partner CRUD/auth/CSRF/idempotency/isolation, end-to-end eligibility/blocked/staleness/isolation) |
| Frontend `pnpm test` (vitest) | ✅ **41 passed** (+8: partner + requirements clients, capability flip) |
| `pnpm exec tsc --noEmit` / `pnpm lint` / `pnpm build` | ✅ exit 0 |
| `pnpm exec playwright test` | ✅ **3 passed** (M2 source, M3 run, **M4 requirements precheck + partner UI + staleness**) |
| Alembic upgrade/downgrade | ✅ clean (4 revisions, both directions) |

## 14. Resolved decisions (no contract invented)
- RuleResult status enum taken from **Domain_Model_v4** (4 values); the richer `result_mapping` labels
  kept as a separate `outcome_label`.
- The M4-evaluable set = the 12 REQ.INNO.\* (REQ.PORTAL.\* excluded: empty `linked_rule_ids`).
- FINANCIAL_20 uses `financial_independence_status` (the Partner schema has no ownership/percent fields);
  PERSONNEL uses `personnel_independence_status`; both only ever reach `passed`/`needs_input` from
  structured data (never auto-`confirmed_conflict`).
- `not_applicable` requirements are omitted from `listRequirements` (status enum has no such value).

## 15. Known limitations
- Budget/duration/scientific-integrity/portal inputs are not captured in M4 → those requirements report
  `needs_input` (honest). Capturing them is a later milestone.
- No semantic assessment, evidence, drafting, review, export, recheck, or human overrides (M5+).
- A **pre-existing M2** limitation: text sources containing non-ASCII (umlaut) content fail ingestion;
  unrelated to M4 (the run only needs one processed source — M4 evaluates structure, not source text).

## 16. Run commands
**Backend** (`backend/`): venv → `pip install -r requirements.txt` → `alembic upgrade head` →
`python -m app.seed` → `uvicorn app.main:app --port 8000`. Tests: `python -m pytest`.
**Frontend** (root): `.env.local` with `FASTAPI_BRIDGE_URL` + `APP_BACKEND_MODE=live` → `pnpm install`
→ `pnpm build` → `pnpm start`. Checks: `pnpm test`, `pnpm lint`, `pnpm build`, `pnpm exec tsc --noEmit`;
with both servers up: `pnpm exec playwright test`.

## 17. Dependencies
`PyYAML==6.0.3` pinned explicitly (already transitive via langgraph) — parses the versioned YAML
registries. No LLM-provider packages, no frontend deps added.

## 18. Milestone 5 readiness
The registry, deterministic engine, immutable project+partner snapshot, persistence (RuleResults/
RequirementAssessments/OpenIssues), graph stage and v1.1 partner/requirement client+BFF are in place and
tested. M5 can add `extract_facts_and_map_evidence` + semantic assessment (basis `semantic_assessment` /
`human_override`), evidence anchoring/verification and drafting by extending the graph + inputs, without
reworking the deterministic foundation. **No M4 implementation is auto-committed.**
