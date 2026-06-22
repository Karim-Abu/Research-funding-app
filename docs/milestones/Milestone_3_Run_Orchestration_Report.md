# Milestone 3 — Run Orchestration, Async Operations & Minimal LangGraph — Final Report

**Branch:** `feat/run-orchestration` (off tag **`milestone-2`** @ M2 commit `bbebcbc`).
**Date:** 2026-06-22. **Status:** ✅ Complete — all 17 acceptance criteria met. **Not committed**
(only the `milestone-2` tag + branch were created).

Delivers the persistent technical foundation for analysis: **createRun → 202 AsyncAccepted → persist
AsyncOperation → freeze immutable source+policy snapshot → minimal LangGraph workflow (initialize →
validate_source_snapshot → finalize_run) with SQLite checkpoints → operation/run polling → cancellation
→ audit/controls/usage → survives refresh + restart.** Resolves the infrastructure of FE-P0-02 (202 +
project path), FE-P0-07 (canonical RunStatus), FE-P1-01 (AsyncOperation polling). **No** LLM/agents/
Firecrawl/rules/requirements/evidence/drafts/review/approval/export. The live "Analyse starten" UI
action stays disabled until M4.

---

## 1. Changed / new files
**Backend (new):** `app/runs/{__init__,constants,transitions,policy,snapshot,graph,executor}.py`,
`app/contracts/run.py`, `app/api/{runs,operations}.py`, `app/repositories/{runs,operations}.py`,
`app/migrations/versions/c0774f9f2c38_run_orchestration.py`, `tests/test_runs.py`.
**Backend (modified):** `app/db/models.py` (+5 models + partial unique index), `app/config/settings.py`
(checkpoint path, run concurrency, policy defaults), `app/main.py` (routers + run recovery),
`app/api/sources.py` (SOURCE_IN_USE guard), `requirements.txt`, `tests/conftest.py`.
**BFF (new/updated):** `app/api/projects/[id]/runs/route.ts` (GET,POST), `app/api/runs/[id]/cancel/
route.ts`, `app/api/operations/[id]/route.ts`; updated `app/api/runs/[id]/route.ts` + `…/resume/route.ts`
to `forwardToBridge`.
**Frontend:** new `lib/runs.ts`, `lib/operations.ts`, `test/{runs,operations}.test.ts`,
`e2e/run-orchestration.spec.ts`; modified `lib/app-mode.ts` (+runs/operations), `lib/backend-contract.ts`
(canonical RunStatus), `lib/capabilities.ts` (features.runs/review/export), `app/quellen/page.tsx`
(canonical poll statuses + `features.runs` gate on "Analyse starten").

## 2. Migration
`c0774f9f2c38_run_orchestration` adds `analysis_runs` (+ **partial unique index**
`uq_active_run_per_project ON project_id WHERE status IN ('created','running','paused_for_review')`),
`async_operations`, `run_source_snapshots`, `run_policy_snapshots`, `usage_records`. Clean migration
verified (3 revisions + seed → exit 0). LangGraph checkpoint tables are created by `SqliteSaver.setup()`
(not Alembic).

## 3. Dependencies (justified)
`langgraph==0.2.76` (minimal typed workflow + checkpointing) and `langgraph-checkpoint-sqlite==2.0.11`
(official SQLite checkpointer — `SqliteSaver`, matching `run_state.checkpoint_policy.backend:
sqlite_for_beta`). No LLM-provider packages. No frontend deps added.

## 4. Implemented operationIds (exact v1.1)
`createRun` (POST /projects/{id}/runs → **202 AsyncAccepted**), `listProjectRuns`, `getRun`,
`cancelRun` (POST /runs/{id}/cancel → **200 AnalysisRun**, 409 terminal), `resumeRun`
(POST /runs/{id}/resume → **409 run_not_resumable** in M3), `getOperation`. Mutations require session +
CSRF + Origin; createRun/cancel/resume require `Idempotency-Key`.

## 5. State-transition table (the single transition service owns these)
**Run:** created→running (executor start) · created→cancelled (cancel) · created→failed (recovery) ·
running→completed (finalize) · running→cancelled (cancel) · running→failed (exec error/recovery) ·
running→stopped (cost; unused in M3) · {completed,stopped,failed,cancelled} terminal.
**Operation:** queued→running (start) · queued→{cancelled,failed} · running→succeeded (graph done) ·
running→{cancelled,failed} · {succeeded,failed,cancelled} terminal. Invalid transitions → **409 Problem**.

## 6. LangGraph & checkpoint design
Typed `StateGraph` (state = `{run_id, project_id, workspace_id}` refs only) → `initialize →
validate_source_snapshot → finalize_run` → END. `SqliteSaver` checkpoints after each node, `thread_id =
run_id`. Each node **reloads the run and short-circuits on cancellation**; `finalize_run` reloads again
and never sets `completed` over `cancelled` (transition guard). No LLM/network. **Checkpoint DB:**
`backend/var/checkpoints.db` — gitignored (under `var/`), backed up with the app data dir; **the app DB
run status is authoritative**; **fail-closed** — a checkpoint/execution failure marks operation+run
`failed` (never silent continue).

## 7. Source snapshot, recovery & cancellation
**Snapshot:** only terminal **processed**, in-project/workspace, non-deleted SourceVersions; explicit
`source_version_ids` are validated (invalid/foreign → 422), none eligible → 422 `no_valid_sources`;
frozen into immutable `RunSourceSnapshot` rows + a `RunPolicySnapshot`. **Deletion:** a frozen source →
**409 `SOURCE_IN_USE`** (no physical delete). **Cancellation:** sets `cancel_requested` + transitions
run→cancelled + operation→cancelled atomically; nodes observe it between stages. **Recovery (startup,
documented):** operations `queued|running` → `failed`+`OPERATION_INTERRUPTED`; their nonterminal runs →
`failed`; checkpoints preserved; **no auto-resume**.

## 8. Security / control / audit / usage
Session+CSRF+Origin on mutations; workspace/project scoping (foreign → 404); Problem Details, no stack
traces. **ControlResults** for authorization/source-snapshot/classification/policy/one-active-run/
operation-state + processing. **AuditEvents** for run.requested, source_snapshot.frozen, operation
queued/started/succeeded/failed/cancelled, run.stage_changed/completed/failed/cancelled, cancel.requested.
**UsageRecord** zero/no-provider per run (no fabricated cost). `processing_mode`: deterministic_only/
local_only accepted; **cloud_assisted → 403 `cloud_processing_unavailable`** (no silent downgrade).

## 9. Test results
| Suite | Result |
|---|---|
| Backend `python -m pytest` | ✅ green (M1/M2/M3; **+18 run tests**: 202 shape, snapshot filtering, idempotency replay+409, one-active-run, processing_mode 403, lifecycle→completed, cancel + terminal-reject, resume 409, checkpoint persists+reopen, finalize-never-overwrites-cancelled, startup recovery→failed, SOURCE_IN_USE, isolation, CSRF, 401) |
| Frontend `pnpm test` | ✅ **33 passed** (+ run client headers/202/409-429-503 UX, generic poller terminal+unmount+bounded-retry, canonical status, capability-disabled) |
| `pnpm build` / `tsc --noEmit` / `pnpm lint` | ✅ exit 0 |
| `pnpm exec playwright test` | ✅ **2 passed** (M2 source ingestion + M3 run technical smoke via API context) |

## 10. Capability distinction (clar. #1)
`capabilities.features.runs=false` gates **only the user-facing live "Analyse starten" button** — the
run/operation API endpoints + frontend client are fully implemented and tested. M4 flips the flag.

## 11. Known limitations
- Minimal 3-stage technical graph only (no requirement/evidence/draft/review stages — M4+).
- BackgroundTasks + in-process semaphore (single-instance beta; not a distributed queue).
- resumeRun always 409 in M3 (graph never reaches `paused_for_review`).
- Cancellation is cooperative (between nodes); a stage already committing may complete before observing
  cancel (SQLite-serialized; never overwrites a committed `cancelled`).

## 12. Run commands
**Backend** (from `backend/`): venv → `pip install -r requirements.txt` → `alembic upgrade head` →
`python -m app.seed` → `uvicorn app.main:app --port 8000`. Tests: `python -m pytest`.
**Frontend** (root): `.env.local` with `FASTAPI_BRIDGE_URL=http://127.0.0.1:8000/api/v1` +
`APP_BACKEND_MODE=live` → `pnpm install` → `pnpm dev`. Checks: `pnpm test`, `pnpm lint`, `pnpm build`,
`pnpm exec tsc --noEmit`; with both servers up: `pnpm exec playwright test`.

## 13. Remaining P0/P1 (next milestones)
M4 enables `features.runs` + implements the real stages: extract_facts/evidence, evaluate_requirements_
and_rules, draft_fields, critic_review, aggregate_review, human_review (→ FE-P0-03 review split,
FE-P0-04 draft base_version/409, FE-P0-05 export, EvidenceLink/verification). Drafts use
`base_version_id`/409 (run_state concurrency).

## 14. Milestone 4 readiness — GO
The canonical run state machine, async-operation + checkpoint persistence, immutable snapshots, one
transition service, bounded executor, recovery, and the v1.1 run/operation client/BFF are in place and
tested. M4 can add real stages by extending the graph + transition map and flipping `features.runs`,
without reworking the foundation. No M3 implementation is auto-committed.
