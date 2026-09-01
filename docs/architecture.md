# Architecture

This document summarizes the current implementation architecture reflected in the repository.

## System Components

1. Frontend (`app/`, `components/`, `lib/`)
   - Next.js UI for intake, source import, run tracking, draft editing, review, and export.
   - Calls backend endpoints under `/api/v1` through bridge utilities.

2. Backend API (`backend/app/api`)
   - FastAPI routers for auth, projects, sources, runs, research, review, exports, and system status.
   - Typed request/response contracts and problem-style error handling.

3. Core Services (`backend/app/*`)
   - Ingestion pipeline (`ingestion/`): parse, normalize, fragment, persist.
   - Run orchestration (`runs/`): LangGraph workflow with staged transitions.
   - Draft/review flows (`drafts/`, `review/`, `agents/`).
   - Research and security gates (`research/`, `security/`).
   - Export pipeline (`exports/`).

4. Persistence
   - SQLite via SQLAlchemy models and Alembic migrations.
   - Operational entities include runs, operations, drafts, findings, controls, and exports.

5. External Providers (optional)
   - OpenAI and Anthropic adapters for AI-assisted stages.
   - Firecrawl adapter for web research.
   - Fake providers available for deterministic local/demo execution.

## Run Workflow (High Level)

The orchestration graph in `backend/app/runs/graph.py` executes stages in sequence:

1. Initialize
2. Validate source snapshot
3. Extract facts and map evidence
4. Verify evidence
5. Evaluate requirements and rules
6. Web research (policy-gated)
7. Create template drafts
8. Draft fields (advisory AI suggestions)
9. Critic review
10. Aggregate review
11. Human review availability
12. Finalize run

## Reliability and Safety Signals

- Startup fails closed on registry/contract loading errors.
- Interrupted runs, source processing jobs, and exports are recovered as failed rather than silently completed.
- Research query firewall prevents unsafe externalization of sensitive data classes.
- Live provider paths are explicit and configuration-gated.

## Contract Artifacts

Versioned contract and policy artifacts are stored in:

- `final_backend_contracts_v1_1/`
