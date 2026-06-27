# Milestone 6.1 Demo Dataset Report

## Basis

- Branch: `feat/demo-dataset`
- Current branch basis used for implementation: `b825db1`
- `5f8a397` = Milestone 6 template drafts baseline
- `milestone-6-template-drafts` points to `5f8a397`
- `b825db1` = reviewed logo/confidentiality UI fixes included in the demo branch
- No automatic commit was created.

## Changed Areas

- Backend settings: explicit `APP_ENV` and `DEMO_DATA_ENABLED` gates.
- Persistence: `demo_seed_manifest` migration and ORM model.
- Seed package: `backend/app/demo/` with dataset, fixtures, seed, and reset.
- Shared services: source creation, run creation, and field evidence-link logic
  made reusable by HTTP API and demo seed.
- Repositories: deterministic ID injection for project, partner, source, and
  source-version creation.
- WorkflowSummary: deterministic versioned project summary from persisted
  artifacts only.
- Frontend dashboard: consumes `workflow_summary`, shows Demo badges, sets
  `rf_active_project_id`, routes Project A to editor and Project B to
  requirements.
- Quellen live flow: uses canonical `createRun` + `AsyncOperation` polling in
  live mode.
- Tests: backend demo seed tests, frontend dashboard/project tests, and
  Playwright demo flow.
- Docs: demo walkthrough, data dictionary, and this report.

## Seed And Reset Design

The seed is explicit only:

```powershell
python -m app.demo.seed
python -m app.demo.seed --reset
```

It fails closed unless:

- `APP_ENV` is `development` or `test`
- `DEMO_DATA_ENABLED=true`

No startup seed and no production seed were added.

All IDs are deterministic UUIDv5 values derived from seed version, object kind,
and stable keys. The manifest records owned demo objects and storage refs. Reset
deletes only manifest-owned objects and manifest-owned storage files.

In test mode, the seed verifies that exactly two projects exist. In development,
it verifies that both demo projects exist without deleting or hiding non-demo
projects.

## Artifact Generation

Derived artifacts are generated through normal application services:

- `projects_repo.create`
- `partners_repo.create`
- `source_service.prepare_text_source` + `process_source_version`
- `run_service.prepare_run` + `run_executor`
- `drafts_repo.apply_update`
- `fields_service.create_draft_evidence_link`

The seed does not directly insert rule results, assessments, issues, evidence
anchors, draft versions, or evidence links.

## WorkflowSummary

Version: `workflow-summary-v1`

The calculator reads persisted sources, runs, requirements, open issues, and
draft versions. It does not hardcode fixture percentages or next actions.

Project A reaches `continue_draft` because current persisted artifacts include
user-created draft versions. Project B remains `review_analysis` because it has
open/blocking requirements and no user draft progress.

`approval_open` is not emitted before the Review/Approval milestone.

## Demo Truthfulness

Project A:

- State: `Entwurf in Bearbeitung`
- Has completed deterministic run, template drafts, user draft edits, and active
  evidence links.
- Still has draft gaps/placeholders.
- Does not imply review, approval, export, or submission readiness.

Project B:

- State: `Anforderungen offen`
- Has completed deterministic run.
- Missing eligible research partner is produced as a blocker by the rule engine.
- Does not imply draft, review, approval, export, or submission readiness.

## Test Results

Pre-implementation gate results:

- `backend/.venv/Scripts/python.exe -m pytest`: passed, 136 tests
- `pnpm test`: passed, 58 tests
- `pnpm lint`: passed
- `pnpm build`: passed
- `pnpm exec tsc --noEmit`: passed
- `pnpm exec playwright test`: passed, 6 tests

Post-implementation final verification:

- `backend/.venv/Scripts/python.exe -m compileall app`: passed
- `backend/.venv/Scripts/python.exe -m pytest`: passed, 139 tests,
  8 warnings
- `pnpm exec vitest run test/projects.test.ts test/dashboard.test.tsx`: passed,
  6 tests
- `pnpm test`: passed, 62 tests
- `pnpm lint`: passed
- `pnpm build`: passed
- `pnpm exec tsc --noEmit`: passed
- `alembic upgrade head`: passed, upgraded to `a6d1c7e9f024`
- `python -m app.demo.seed --reset`: passed, seeded 2 demo projects
- `DEMO_DATA_ENABLED=true pnpm exec playwright test e2e/demo-dataset.spec.ts`:
  passed, 1 test
- `DEMO_DATA_ENABLED=true pnpm exec playwright test`: passed, 7 tests

## Limitations

- Demo seed uses the current local database connection; the schema must be at
  Alembic head before running the seed command.
- Playwright demo flow expects `DEMO_DATA_ENABLED=true`; otherwise it is skipped
  to avoid mutating ordinary smoke-test databases.
- The demo dataset is synthetic and public-only by design.

## P0/P1 Findings

- P0: none found.
- P1: none found.

## Verify-and-close-gaps pass (2026-06-24)

A dedicated verification pass against the full spec + the 8 binding verification
additions. **No production code required changes** — the committed implementation
(`3e5a6b0`) already routes seeded draft edits + evidence links through the same
services as the API (`drafts_repo.apply_update`, `fields_service.create_draft_evidence_link`),
so character-limit, `base_version_id` currency, immutable `DraftVersion`,
`recheck_required` and audit invariants are identical to normal user actions.
The only change is **5 new safety tests** added to `backend/tests/test_demo_seed.py`.

Results (all green):
- **Full suites:** backend `pytest` **144 passed** (139 + 5 new); frontend
  `pnpm test` **62 passed**; `pnpm lint` / `pnpm build` / `tsc --noEmit` exit 0;
  `pnpm exec playwright test` **7 passed** (incl. `demo-dataset.spec.ts`).
- **Isolated seed run** (fully separate temp `DATABASE_URL` + `CHECKPOINT_DB_PATH`
  + `SOURCE_STORAGE_DIR`; all artifacts removed afterward, binding #1):
  - **Migration chain** (#3): `upgrade head → downgrade base → upgrade head` clean.
  - **Idempotent**: first seed → `projects=2 manifest=21 sources=6 completed_runs=2`;
    re-seed → identical counts (no duplicates); `--reset` → reseeds clean.
  - **Production fail-closed** (#5): `APP_ENV=production python -m app.demo.seed`
    exits non-zero and creates **no project, manifest row, source or storage file**.
- **New tests** (binding #2/#4/#5/#6/#7): no-network-during-seed (all sockets
  blocked → seed still succeeds, proving no provider/OpenAI/Anthropic/Firecrawl/HTTP
  call); partial-failure safety (a mid-seed run failure leaves no draft-ready
  dashboard for the aborted project); production-guard-creates-nothing;
  capabilities (`review`/`export`/`web_research` stay false, no cloud capability)
  unchanged after seeding; seeded edits/links satisfy user-action invariants
  (`created_by` template→user chaining, within character limit, `recheck_required`).
- **Conformance audit** (persisted artifacts, not fixtures): Project A — 12
  RuleResults, requirement assessments, exact-verified anchors, ≥2 user
  DraftVersions, ≥2 active draft EvidenceLinks, a retained placeholder + untouched
  templates, `recheck_required` truthful, never reviewed/approved; Project B —
  `REQ.INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE` blocker + OpenIssue produced by the
  real Rule Engine. `main.py` lifespan does not auto-seed. Dashboard summaries are
  derived: A → `continue_draft` / step 5 (Entwurf), B → `review_analysis` / step 3
  (Anforderungen).

**Cosmetic deviation (non-functional, left as implemented):** the demo partner
locations/FTE (`Aarau` / 42 FTE; research partner `Windisch`) differ from the spec's
example values (`Winterthur` / 68; `Brugg`). These are intentional synthetic values
and do not affect any rule, assessment, evidence or dashboard outcome.

## Readiness Verdict

M6.1 is ready for review and **verified**. The deterministic demo seed, live
dashboard states, draft continuation path, open requirements path, reset
isolation, production fail-closed guard, migration chain, no-network guarantee and
partial-failure safety are all confirmed by automated tests + an isolated end-to-end
seed run. Ready for **Milestone 7 (Review, Recheck, Approval)**.
