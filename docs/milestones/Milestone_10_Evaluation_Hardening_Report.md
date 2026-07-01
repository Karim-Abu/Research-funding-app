# Milestone 10 — Evaluation & Hardening

**Scope:** freeze the backend feature scope and make the system a *reproducible, evaluable,
defensible beta*. No new product features, no finalized-contract changes. Delivers
one-command verification, a deterministic evaluation dataset, migration hardening,
API/export/no-raw-log smokes, a provider-mode matrix, an EvaluationRunSummary metrics export,
and the evaluation/limitations documentation.

## Branch / commit basis
- Branch **`feat/evaluation-hardening`**, from **`4b3625e`** ("Milestone 9K: MAS reliability
  and value assurance").
- Tag **`milestone-9k-mas-reliability-assurance`** added on `4b3625e` (STEP 0).
- No M10 auto-commit (only the STEP-0 tag + branch).

## Feature freeze status
Feature scope frozen at M9K. Full audit in
[docs/evaluation/M10_Feature_Freeze_Audit.md](../evaluation/M10_Feature_Freeze_Audit.md).
Explicitly **out of M10**: M9H, full Azure production, NDA (D3) processing, full SNF/Horizon,
automatic portal submission, automatic approval, automatic funding-probability. **No finalized
contract modified** (`git status` clean under `final_backend_contracts_v1_1/`).

## Changed files
- **New (backend):** `app/demo/evaluation.py` (eval enrichment), `app/evaluation/`
  (`summary.py`, `__main__.py`, `__init__.py` — EvaluationRunSummary),
  `tests/test_m10_migrations.py`, `tests/test_m10_eval_seed.py`, `tests/test_m10_smoke.py`.
- **Modified (backend):** `app/demo/seed.py` (`--evaluation` flag; plain `--reset`
  byte-identical), `app/demo/reset.py` (cleans reliability/market/review rows).
- **New (root):** `scripts/verify_all.sh`, `scripts/verify_all.ps1`, `scripts/smoke_api.py`,
  `e2e/m10-acceptance.spec.ts`, `docs/evaluation/*` (feature freeze, dataset, provider matrix,
  baseline template, known limitations, EvaluationRunSummary example), this report.

## Verification commands
```
bash scripts/verify_all.sh          # or: pwsh scripts/verify_all.ps1
# individually:
cd backend && python -m pytest
corepack pnpm test && corepack pnpm lint && corepack pnpm build && corepack pnpm exec tsc --noEmit
corepack pnpm exec playwright test --workers=1     # servers + fakes
python scripts/smoke_api.py                        # against a running server
```
`verify_all` detects the package manager (`corepack pnpm` → `pnpm` → `npm`), starts and tears
down the servers itself, and prints a final summary (backend · migration · frontend · build/
typecheck/lint · Playwright · API smoke · export smoke · no-raw-log · evaluation-summary path).
**No real provider/key is required for any mandatory step.**

## Full test results (fakes only)
- **Backend `pytest`: 497 passed, 3 skipped** (+10 M10): 3 migration hardening, 4 eval-seed
  (separation + determinism + idempotency), 3 smoke (export all types, no-raw-log, log
  redaction).
- **Frontend**: vitest **128 passed**, `eslint` clean, `tsc --noEmit` clean, `next build` OK.
- **Playwright (`--workers=1`)**: **26 passed** — including the env-gated `demo-dataset.spec`
  and the new API-driven `m10-acceptance.spec` (run → reliability → review Quality Summary →
  DOCX/Markdown/technical exports → Innolink → no raw leaks/provider branding → logout).
- **API smoke** (`scripts/smoke_api.py`): **18/18** (login → capabilities → project → source →
  run → requirements → evidence → review → reliability → 3 exports + downloads → web research +
  market comparison with fakes).

## Migration test results
`tests/test_m10_migrations.py` (real `alembic` subprocess against a throwaway SQLite DB,
inspected with stdlib `sqlite3`): (1) **fresh DB** upgrade → head `f3d7a9c2e5b1` + all key
tables; (2) **existing DB** no-op upgrade preserves a core row (documented **hardening check**,
not a full historical production migration test — M10 adds no migration); (3) latest-migration
**down/up roundtrip** restores the reliability tables. Test DB (`create_all`) is unchanged; the
migrated path is now exercised separately.

## Seed/reset dataset
`python -m app.demo.seed --reset --evaluation` (superset of the demo seed) enriches the main
demo project deterministically: a Value Creation draft, a **strong unsupported** claim
(reliability blocker) + a hedged claim, a **supported** technical claim backed by a verified
anchor, a **source-backed** MarketComparison item (verified via `app/market/verify.py`), and a
real reliability pass → `RunQualitySummary`. Plain `--reset` is **byte-identical** (proven by
`test_m10_eval_seed.py::test_plain_demo_seed_has_no_evaluation_artifacts`); reset cleans the
reliability/market/review rows. Details:
[docs/evaluation/Evaluation_Dataset.md](../evaluation/Evaluation_Dataset.md).

## API / export / no-raw-log smoke results
- **API smoke** — 18/18 (above).
- **Export smoke** (`test_export_all_types`) — DOCX + Markdown + technical_evidence created,
  downloadable, non-empty; technical-evidence JSON carries the reliability `quality_summary`
  and contains **no** `claim_text` / raw prompts / provider payloads / raw queries / secrets.
- **No-raw-log smoke** (`test_no_raw_log`) — synthetic markers (partner, codename, budget, raw
  D2 query, secret token) carried through the D2 firewall path never appear in
  `AuditEvent`/`ControlResult`/`ToolInvocation`/`UsageRecord`/logs/export; only hashes + the
  sanitized query remain. `RedactingFilter` scrubs query markers from logs.

## Provider mode matrix
[docs/evaluation/Provider_Mode_Matrix.md](../evaluation/Provider_Mode_Matrix.md): deterministic
· fake · real OpenAI/Anthropic · real Firecrawl · **Azure = target architecture, not deployed**
(no production compliance claimed; DPA + FHNW review required for productive confidential use).

## Evaluation metrics export
`python -m app.evaluation` writes a deterministic
`var/evaluation/EvaluationRunSummary.{json,md}` (git-ignored runtime dir);
[docs/evaluation/EvaluationRunSummary.example.md](../evaluation/EvaluationRunSummary.example.md)
is the committed example. Representative eval run: 5 sources, 11 requirements, 8 draft fields,
9 exact-verified anchors, claim_count 10 (supported 1 / weakly 1 / unsupported 2), blocker 2,
warning 5, **evidence_coverage 0.5 kept separate from evidence_sufficiency_pass_rate 0.5**,
`quality_flag=risky`, cost = explicit placeholder (no CHF invented).

## Known limitations
[docs/evaluation/Known_Limitations.md](../evaluation/Known_Limitations.md): no auto funding
decision / Innolink submission / NDA processing; no factual-correctness guarantee without human
review; deterministic sufficiency is conservative/heuristic; market comparison uses only
imported public sources; Azure documented-not-deployed; SNF/Horizon not implemented; structured
repeated portal fields (work packages, milestones, budget tables) not fully covered; real
Firecrawl/provider smoke optional/env-gated; no provider vector stores for confidential data.
Baseline evaluation template:
[docs/evaluation/Baseline_Comparison_Template.md](../evaluation/Baseline_Comparison_Template.md).

## Acceptance criteria — status
1 one-command verification ✓ · 2 full suite green ✓ · 3 eval seed/reset works ✓ · 4 fresh-DB
migration works ✓ · 5 existing-DB migration check (documented hardening check) ✓ · 6 API smoke
passes ✓ · 7 export smoke passes ✓ · 8 no-raw-log smoke passes ✓ · 9 provider modes documented
✓ · 10 EvaluationRunSummary generated ✓ · 11 baseline template exists ✓ · 12 known limitations
documented ✓ · 13 reliability summary in technical export ✓ · 14 no mandatory test needs a real
provider ✓ · 15 no finalized contract modified ✓ · 16 no new product feature ✓ · 17 ready for
supervised beta evaluation ✓.

## Readiness verdict
The system is a **reproducible, evaluable, defensible beta**: one-command verification (fakes,
self-orchestrated servers), a deterministic evaluation dataset with the full reliability
surface, migration hardening, and privacy/export smokes that prove no raw sensitive data leaks
— all with no finalized-contract change and all prior milestones intact. **Ready for supervised
beta evaluation.**

## Remaining post-beta backlog
M9H Innovation Challenge · structured repeated portal fields (work packages / milestones /
budget tables) · SNF & Horizon instruments · production Azure deployment (Regional/Standard +
Private Endpoint + DPA + FHNW data-protection review) · optional real-provider hardening ·
larger real-evaluation study using the baseline template.
