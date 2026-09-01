# Contributing

Thank you for your interest in improving this repository.

## Principles

- Keep changes small, focused, and reviewable.
- Preserve existing architecture boundaries and naming conventions.
- Do not commit secrets, credentials, or sensitive project data.
- Do not degrade reproducibility, traceability, or reviewability.

## Development Workflow

1. Describe the problem and intended outcome.
2. Implement minimal, targeted changes.
3. Run relevant checks before review.
4. Document key decisions and known limitations.

## Validation Before Review

Frontend (repository root):

```bash
corepack pnpm test
corepack pnpm lint
corepack pnpm exec tsc --noEmit
corepack pnpm build
```

Backend (`backend/`):

```bash
.venv/bin/python -m pytest -q
```

Windows equivalent:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

## Pull Request Quality

A good pull request should include:

- clear problem statement
- concise explanation of the approach
- validation evidence (commands and outcomes)
- explicit note on remaining risks or follow-up work

## Communication

Please keep communication clear, specific, and respectful.
