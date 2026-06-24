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

## Readiness Verdict

M6.1 is ready for review. The deterministic demo seed, live dashboard states,
draft continuation path, open requirements path, reset isolation, and automated
verification are in place.
