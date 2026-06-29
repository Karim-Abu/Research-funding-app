# Milestone 9I-A — Public Web Research Foundation

**Scope:** the safe, auditable foundation for **public** web research. A user-initiated
`ResearchTask` runs a controlled public web search through a provider (Firecrawl, with a
deterministic fake for tests), returns selectable candidate results, and imports a chosen
result as a **normal `SourceDocument`** so the existing deterministic evidence pipeline
can later process it. Public/synthetic only. It never rewrites proposal text, never
auto-approves, never creates EvidenceAnchors from snippets, and never sends
confidential/internal/NDA text to a provider. Implemented exactly to the finalized
contract surface (competence/partner-research purposes); market/competitor comparison is
deferred to **M9I-B**. **No finalized contract modified.**

## Branch / commit basis

- Branch **`feat/public-web-research`**, created from **`15b801b`** ("Milestone 9G: A3
  evidence consistency review").
- Tag **`milestone-9g-a3-evidence-consistency`** added on `15b801b` (STEP 0 setup).
- No M9I-A auto-commit (only the STEP-0 tag + branch).

## Decisions / binding corrections honoured

1. **Contract-faithful purposes** — `ResearchTaskCreate.purpose` is the finalized enum
   `partner_role_suggestion | competence_gap_analysis | publication_track_record`. M9I-A
   is the *foundation*, not market/competitor analysis (deferred to M9I-B).
2. **Role deviation (documented)** — OpenAPI marks `createResearchTask` lead_admin-only;
   for beta usability **member OR lead_admin** may start a task on accessible public/
   synthetic projects. Data policy still gates the external call.
3. **URL import stays disabled** — `features.url_import=false`, `/sources/url` stays 503,
   `supported_source_types` is not changed. Web import is an **internal** Research path
   that creates `SourceDocument.type=url`; no free-form URL-import surface is exposed.
4. **Research-task-scoped CostGuard** — web search/fetch/A1 limits count by
   `research_task_id`; a nullable `run_id` is **never** an aggregation key (verified: 0
   tool invocations with both ids null).
5. **Separate fake flag** — the web fake provider is gated by **`WEB_RESEARCH_FAKE_PROVIDER`**
   only, never implied by `AGENT_FAKE_PROVIDER`.
6. **A1 synthesis is non-blocking** — import success never depends on A1; a failure/skip
   keeps the imported SourceDocument/Version/Fragments, leaves the advisory arrays empty
   and records a safe failure.
7. **Internal data blocked in beta** — public/synthetic only; no internal-data web path
   or internal-confirmation UX.
8. **Fresh cloud confirmation** — imported web sources create **new** SourceVersions; the
   existing M9D.2 confirmation gate binds `source_version_ids`, so a future
   `cloud_assisted` run needs a fresh confirmation covering them (import never reuses one).
9. **No provider branding** — no Firecrawl/provider/API/token/policy-code text in normal
   UI; only "Öffentliche Recherche" / "Quelle importieren" / "Als Quelle gespeichert".
10. **Evidence discipline** — snippets are not evidence; imported page text becomes source
    material; EvidenceAnchors only ever come from the deterministic pipeline on a later run.

## Migration

`c5f9a2d7b3e1_public_web_research` (on head `b4e8f1a3c6d2`):
- New tables **`research_tasks`** and **`research_results`** (internal; the public surface
  is the OpenAPI `ResearchTask`/`ResearchResult` schemas).
- `tool_invocations.run_id` and `usage_records.run_id` made **nullable**; added nullable
  **`research_task_id`** to `tool_invocations`, `control_results`, `usage_records` for
  research-task-scoped cost/audit.

## Changed / new files

**Backend**
- `app/db/models.py` — `ResearchTask` + `ResearchResult`; `run_id` nullable +
  `research_task_id` on `ToolInvocation`/`UsageRecord`; `research_task_id` on `ControlResult`.
- `app/research/` (new) — `policy.py` (`evaluate_web_research`), `url_safety.py`
  (SSRF/URL validation), `providers/` (`base`, `fake`, `firecrawl`, `resolver`),
  `cost_guard.py` (research-task scope), `recording.py`, `service.py`, `executor.py`,
  `import_service.py`.
- `app/agents/public_competence_research.py` (new) — advisory, non-blocking A1 synthesis
  via the ModelGateway; `app/agents/prompts/a1_public_competence_research_v1.md` (active);
  `app/agents/schemas.py` — `PublicCompetenceResearchInput@v1` /
  `PublicCompetenceResearchResult@v1` (+ nested records) registered in `SCHEMA_MODELS`.
- `app/contracts/research.py` (new); `app/api/research.py` (new, registered in `main.py`).
- `app/api/capabilities.py` — truthful `web_research` flag (`url_import` stays false).
- `app/config/settings.py` — `web_research_enabled`, `firecrawl_api_key`,
  `web_research_fake_provider` + limits.
- `app/ingestion/parsers.py` — `url` sources parsed as text (provider-extracted page text).
- `app/repositories/controls.py` — `research_task_id` passthrough.
- `tests/test_public_web_research.py` (new, 29 tests).

**Frontend**
- `lib/research.ts` (new) — `createResearchTask` / `listResearchResults` /
  `importResearchResult` (+ DTOs, localized errors).
- BFF routes `app/api/projects/[id]/research-tasks`, `app/api/research-tasks/[id]`,
  `app/api/projects/[id]/research-results`, `app/api/research-results/[id]/import`.
- `components/quellen/public-research-panel.tsx` (new); wired into `app/quellen/page.tsx`
  (gated by `capabilities.features.web_research`).
- `test/public-research-panel.test.tsx` (new); `e2e/public-web-research.spec.ts` (new).

## Data policy (web research)

`evaluate_web_research` (deny-by-default, most-restrictive wins): requires
`web_research_mode == validated_public`; blocks `local_only`; blocks NDA; allows only
**public + origin∈{public_source,synthetic}**; **internal/confidential/missing →
blocked** in the beta (no internal path). Every allow/block writes a `CTRL.DATA_POLICY`
ControlResult + AuditEvent. The external query is **only** the user-confirmed
`query_preview` — restricted project text is never converted into a public query.

## Query construction

The user explicitly enters/confirms the public query (`query_preview`,
`user_confirms_public_professional_purpose: const true`). Only the normalized public
query + its hash are stored (`query_text` / `normalized_query_hash`). UI warns: "Nur
öffentliche Suchbegriffe verwenden. Keine vertraulichen oder personenbezogenen
Informationen eingeben."

## Provider / fake design

Backend-only boundary (`app/research/providers/`), separate from the LLM ModelGateway.
`FirecrawlProvider` is **env-gated** (`firecrawl_api_key`, backend-only, never logged/
audited/exported; `available()` false without a key → feature unavailable, no crash).
`FakeWebProvider` is deterministic (no network), gated **only** by
`WEB_RESEARCH_FAKE_PROVIDER`, with a paired DNS resolver that resolves its own hosts to a
fixed public IP and blocks unknown hosts. All mandatory tests use the fake.

## URL / SSRF safety

`validate_public_url` (used on candidates, the source URL at import, and the final URL
after redirects): https-only; no credentials; DNS-resolve and reject loopback / private /
link-local / reserved / metadata; content-type allowlist; byte limit. Controls
`CTRL.PUBLIC_URL_VALIDATION` / `CTRL.SSRF_PREVENTION` / `CTRL.REDIRECT_REVALIDATION`.

## ResearchTask / result / import / A1

- `createResearchTask` → 202 AsyncAccepted → background `research_executor`: data-policy
  gate → research-task CostGuard → provider search → SSRF-validate each candidate →
  persist `candidate` results (empty evidence arrays, `identity_match_status=
  not_applicable`). Safe failure → task `failed`; policy block → task `blocked`
  (surfaced as `failed` + safe detail in the public contract).
- `importResearchResult` → re-gate policy + SSRF → provider fetch → revalidate final URL
  → create `SourceDocument(type=url)` (forced public/public_source classification) + new
  `SourceVersion` → existing `process_source_version` pipeline → fragments → result
  `imported` + `source_document_id`. **No EvidenceAnchor created.** Returns 201
  SourceDocument; import succeeds independently of A1.
- **A1 synthesis** (`A1.public_competence_research`, advisory, ≤1 success/task,
  non-blocking): over imported source versions → populates
  `professional_evidence`/`partner_role_suggestions` (each with source URL + access date
  + evidence ref, `human_review_required=true`). Failure/skip → empty arrays + safe
  failure; the imported source is preserved.

## API / BFF / frontend

Four contract operations only (`createResearchTask`/`getResearchTask`/
`listResearchResults`/`importResearchResult`); no new undocumented routes. BFF proxies
mirror the sources pattern. The Quellen page shows an "Öffentliche Recherche" panel
(states: enter query → searching → results → import → "Als Quelle gespeichert" → error)
gated by the `web_research` capability; A1 suggestions are labelled advisory; no provider
names anywhere.

## Capability changes

`web_research = web_research_enabled AND (firecrawl configured OR web fake)` — truthful,
false when no provider is ready. `url_import` stays **false**; `supported_source_types`
unchanged.

## Tests / results (fake provider only)

- **Backend** `pytest`: **434 passed, 3 skipped** (incl. the new
  `test_public_web_research.py`, 29 tests: URL/SSRF battery; data-policy matrix;
  fake/real provider incl. missing-key/timeout/error/credit; task lifecycle/idempotency/
  workspace-isolation/blocked; import → SourceDocument(url)+Version+Fragments, in
  listSources, **no EvidenceAnchor**; advisory A1 + **non-blocking** failure; capabilities).
- **Frontend** `vitest`: **119 passed** (incl. 4 panel tests: warnings, search→results,
  import→saved, blocked-422; no provider/key text). `eslint` clean; `tsc --noEmit` clean;
  `next build` succeeds.
- **Playwright** (`--workers=1`, web fake + agent fake): **16 passed, 1 skipped**,
  including the two new specs — (a) API-context: search → import as `SourceDocument(url)`
  → appears in sources → a deterministic analysis run consumes the imported version; (b)
  UI: Quellen → "Öffentliche Recherche" → query → run → import → "Als Quelle gespeichert",
  asserting **no `firecrawl` text** on the page. The `demo-dataset` spec is environment-
  gated (`DEMO_DATA_ENABLED` in the runner, own DB reset) and self-skips — unchanged by
  M9I-A.
- **Security**: backend log free of API key / `firecrawl` / bearer / secret; web/A1 cost
  rows scoped by `research_task_id` with **0** orphan (run_id=null & research_task_id=null)
  rows; no real Firecrawl contacted.
- **Optional real-provider smoke**: not run — no Firecrawl key configured; the fake drives
  all mandatory tests.

## Known limitations

- Public/synthetic only; internal/confidential/NDA web research is intentionally not built.
- `ResearchResult` carries the contract's competence/partner fields (empty until A1
  runs); market/competitor specialization is M9I-B.
- A1 synthesis runs at most once per task on import; subsequent imports do not re-run a
  successful synthesis.
- Firecrawl adapter is implemented but unexercised by CI (no key); its network paths are
  guarded and `# pragma: no cover`.

## Readiness for M9I-B (Market & Competitor Comparison)

M9I-A establishes the user-initiated, SSRF-safe, audited public-research surface
(ResearchTask → search → candidates → import → normal SourceDocument), the research-task-
scoped cost/audit model, and the advisory A1 synthesis — all without contract/endpoint
changes beyond internal tables. M9I-B can build market/competitor comparison on top by
adding analysis over the already-imported public sources (and, if needed, an authorized
contract extension for new purposes) without re-opening the data-policy or SSRF boundary.
**Ready for M9I-B.**
