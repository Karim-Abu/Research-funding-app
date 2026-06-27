# Milestone 2 — Source Ingestion, Versioning, Parsing & Normalization — Final Report

**Branch:** `feat/source-ingestion` (off committed M1 `1ecb962`). **Date:** 2026-06-22.
**Status:** ✅ Complete — all 14 acceptance criteria met. **Not committed** (per instruction; only the
M1 commit was authorized).

Live vertical slice delivered: **login → select/create project → upload/create a source → parse +
normalize → real processing status → survives refresh & backend restart → delete → logout**, behind
the single server-controlled `APP_BACKEND_MODE`. No LLM, agents, Firecrawl, rule evaluation, evidence
mapping, drafting, review, or export.

---

## 1. Changed / new files

**Backend (new):** `app/db/` (+ SourceDocument/SourceVersion/SourceFragment/ControlResult in
`models.py`), `app/storage/{__init__,base,local}.py`, `app/ingestion/{__init__,normalize,signatures,
parsers,pipeline}.py`, `app/policy/classification.py`, `app/repositories/{sources,controls}.py`,
`app/contracts/source.py`, `app/api/sources.py`, `app/migrations/versions/4fb52517c454_source_
ingestion.py`, `tests/{fixtures,test_sources}.py`. **Backend (modified):** `app/main.py` (sources
router + startup recovery), `app/api/capabilities.py`, `app/config/settings.py` (limits + storage),
`app/contracts/__init__.py`, `backend/.gitignore`, `requirements.txt`, `tests/conftest.py`.

**BFF (new):** `app/api/projects/[id]/sources/route.ts` (GET list, POST files),
`.../sources/text/route.ts`, `.../sources/url/route.ts`, `app/api/sources/[id]/route.ts` (GET, DELETE).

**Frontend (new):** `lib/sources.ts`, `lib/capabilities.ts`, `eslint.config.mjs`,
`playwright.config.ts`, `e2e/source-ingestion.spec.ts`, `test/{sources,source-table}.test.{ts,tsx}`.
**Frontend (modified):** `app/quellen/page.tsx` (live list/upload/text/delete + polling),
`components/quellen/source-table.tsx` (controlled live props + 5 statuses), `lib/app-mode.ts`
(+`sources`), `lib/quellen-mock-data.ts` (status/type aligned to contract), `package.json`,
`pnpm-workspace.yaml`, `.gitignore`.

## 2. Migration
One Alembic revision `4fb52517c454_source_ingestion` adds `source_documents`, `source_versions`,
`source_fragments`, `control_results` (+ indexes). Verified on a clean DB:
`alembic upgrade head` runs both revisions (initial + source ingestion) → exit 0; seed → exit 0.

## 3. Dependencies (justified)
- **Backend:** `python-multipart` (FastAPI multipart file upload), `pypdf` (pure-Python PDF text),
  `python-docx` (DOCX paragraphs + tables). No MVP parser exists in-repo to reuse.
- **Frontend (dev):** `@playwright/test` (live smoke, acceptance #12), `eslint` +
  `@next/eslint-plugin-next` + `@typescript-eslint/parser` (minimal Next-compatible lint, addresses
  audit FE-P1-08). *(eslint-config-next + FlatCompat were dropped — they crash on eslint 9.)*

## 4. Implemented operations (exact contract)
`GET /projects/{id}/sources` (list) · `POST …/sources/files` (**202** async, 413/415/422; multipart
`files[]` + `data_classification_json`; CSRF+Idempotency) · `POST …/sources/text` (**201** sync;
CSRF+Idempotency) · `POST …/sources/url` (**503** — disabled this milestone) ·
`GET /sources/{id}` (status polling) · `DELETE /sources/{id}` (**204**; **409** `SOURCE_PROCESSING`).
All workspace+project scoped, audited, Problem-Details errors. **Capabilities** truthfully report
`supported_source_types=[pdf,docx,txt]`, `max_upload_bytes`, `features.url_import=false`,
`source_parsing=true`.

## 5. Parser / normalizer behaviour
- **Parsers** (`PARSER_VERSION=parser-1`): PDF per-page text (encrypted / image-only → `needs_manual_
  input`, never silent `processed`); DOCX **paragraphs + tables** (unsupported structures → warnings,
  e.g. `inline_images_not_extracted`); TXT UTF-8 with a **warned** cp1252 fallback (binary/NUL →
  rejected).
- **Normalization** (`NORMALIZER_VERSION=normalizer-1`, deterministic): NFKC → line endings → strip
  soft-hyphen → conservative cross-line dehyphenation → collapse intra-line whitespace preserving
  paragraph boundaries.
- **Fragments** (`CHUNKER_VERSION=chunker-1`): SHA-256 content hash; deterministic ordinal; offsets
  relative to the stored full `normalized_text`; page/section; paragraph/page/table-based.
- **SourceVersion** is mutable only while processing, then immutable; reprocessing = a new version;
  `processing_started_at/finished_at/attempt/last_error_code`; on startup, interrupted rows →
  `failed` + `SOURCE_PROCESSING_INTERRUPTED`. Async via FastAPI `BackgroundTasks` with a bounded
  `max_parsing_concurrency` semaphore.
- **Classification** (Data Policy): effective = most-restrictive sensitivity, NDA = OR, origin =
  declared, processing/web_research = requested; **no silent downgrade**; stored on document **and**
  version; ControlResults persisted for size/type/signature/archive/classification/path/processing.

## 6. Security controls
Original binaries stored **outside SQLite** via `LocalSourceStorage` (uuid keys, sharded path,
resolved-path-within-root guard); original filename is metadata only. Per-file size + total-request +
file-count + archive-entry + expanded-archive limits (all deployment config). Extension+MIME+magic-byte
signature must agree; DOCX container validated; executables/scripts rejected. Session+CSRF+Origin on
mutations; Idempotency-Key (replay → original, conflicting → 409). Errors are user-safe German copy via
Problem Details — no stack traces, file paths, or parser internals; logs redact passwords/tokens; no
`NEXT_PUBLIC` secrets.

## 7. Tests & verification
| Check | Result |
|---|---|
| Backend `python -m pytest` | ✅ **30 passed** (PDF/DOCX/TXT, text, list/get/delete, isolation, CSRF+Origin, idempotency replay+409, 415/413, traversal-safe, corrupted→failed, image-only→needs_manual_input, no-downgrade, stable hashes + fragments persist on DB re-open) |
| Frontend `pnpm test` (Vitest+RTL+MSW) | ✅ **24 passed** (list, upload headers, text, delete, 413/415 UX, status rendering, mock mode) |
| `pnpm build` / `pnpm exec tsc --noEmit` | ✅ exit 0 (source BFF routes registered) |
| `pnpm lint` (eslint flat config) | ✅ exit 0 |
| `pnpm exec playwright test` (live) | ✅ **1 passed** — login→project→text source→processed→reload→persists→logout |
| Clean migration + seed | ✅ exit 0 |

## 8. Acceptance criteria — all met
1 clean migration ✓ · 2 binaries outside SQLite ✓ · 3 PDF/DOCX/TXT ✓ · 4 parse failures visible
(never silent processed) ✓ · 5 versions+fragments persisted ✓ · 6 hashes + parser/normalizer/chunker
versions stored ✓ · 7 survives refresh (Playwright) + backend restart (DB re-open test + startup
recovery) ✓ · 8 workspace isolation ✓ · 9 live Quellen uses real backend ✓ · 10 mock mode still works
✓ · 11 build/typecheck/frontend+backend tests pass ✓ · 12 Playwright live smoke passes ✓ · 13 no
LLM/external-search call ✓ · 14 no secret in client/logs ✓.

## 9. Known limitations
- URL import is disabled (`url_import=false`, endpoint 503) — Firecrawl + SSRF/DNS validation deferred.
- No OCR — image-only PDFs become `needs_manual_input` (by design).
- Async processing uses in-process `BackgroundTasks` (single-instance beta only; not a queue).
- Full ControlResult/Control engine not built — minimal control rows only.
- `needs_manual_input` renders with the amber "Manuelle Prüfung nötig" badge (no separate redesign).

## 10. Run commands
**Backend** (from `backend/`): `python -m venv .venv` → activate → `pip install -r requirements.txt`
→ `alembic upgrade head` → `python -m app.seed` → `uvicorn app.main:app --port 8000`. Tests:
`python -m pytest`.
**Frontend** (repo root): `.env.local` with `FASTAPI_BRIDGE_URL=http://127.0.0.1:8000/api/v1` and
`APP_BACKEND_MODE=live` → `pnpm install` → `pnpm dev`. Checks: `pnpm test`, `pnpm build`,
`pnpm exec tsc --noEmit`, `pnpm lint`. Live smoke (both servers up):
`pnpm exec playwright install chromium` then `pnpm exec playwright test`.
Dev login: `anna.keller@example.test` / `changeme-dev-lead`.

## 11. Remaining audit findings (next milestones)
Addressed this milestone: source list/upload/parse/version/delete (audit FE-P1-04, FE-P1-07),
`needs_manual_input` status, capability-driven gating (FE-P1-05 partial), ESLint (FE-P1-08).
Still open: **FE-P0-02** run start/202, **FE-P0-03** review split, **FE-P0-04** draft `base_version`/
409, **FE-P0-05** export model, **FE-P0-07** `RunStatus` enum, **FE-P0-09** runs/requirements mappers,
EvidenceLink/verification, AsyncOperation/getOperation polling (FE-P1-01/02). No M2 implementation is
auto-committed.
