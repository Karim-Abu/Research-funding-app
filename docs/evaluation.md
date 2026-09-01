# Evaluation and Validation

This repository separates deterministic technical validation from optional live-provider evaluation.

## Deterministic Validation (Default)

Run these checks locally:

```bash
# Frontend
corepack pnpm test
corepack pnpm lint
corepack pnpm exec tsc --noEmit
corepack pnpm build

# Backend
cd backend && .venv/bin/python -m pytest -q

# End-to-end
corepack pnpm exec playwright test --workers=1
```

One-command technical gate:

```bash
scripts/verify_all.sh
# Windows: .\scripts\verify_all.ps1
```

This gate validates migration, backend tests, frontend tests, lint/typecheck/build, targeted E2E flows, and smoke checks.

## Optional Live Evaluation Paths

The repository includes scripts for opt-in checks that depend on provider configuration, for example:

- `scripts/run_model_quality_eval.py`
- `scripts/run_role_model_eval.py`
- `scripts/run_live_research_smoke.py`
- `scripts/run_provider_preflight.py`

These are intentionally not mandatory for the deterministic local gate.

## Test Data Policy

For fixture and evaluation data handling constraints, see:

- `docs/evaluation/testdata-policy.md`
