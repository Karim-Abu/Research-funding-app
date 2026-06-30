# Milestone 9I-B — Market & Competitor Comparison from Imported Public Sources

**Scope:** a structured market/competitor comparison layer built **only** from the public
sources imported in M9I-A. Each shown item is **source-backed** by a deterministically
verified exact quote, or marked **needs_human_review / insufficient_evidence**. It never
rewrites proposal text, never updates A2, never approves, never creates EvidenceAnchors
from snippets, and never invents market facts. **No finalized contract is modified** — the
structuring agent profile + its I/O schemas are code-only; the endpoints are documented
beta-internal.

## Branch / commit basis
- Branch **`feat/market-competitor-comparison`**, created from **`c4e340c`** ("Milestone
  9I-A: public web research foundation").
- Tag **`milestone-9i-a-public-web-research`** added on `c4e340c` (STEP 0 setup).
- No M9I-B auto-commit (only the STEP-0 tag + branch).

## Contract decision
No market/competitor comparison object, operation, tool, or agent profile exists in any
finalized contract (OpenAPI, schema_catalog, Domain_Model, agents_v1_1, tools, controls,
data_policy — all checked). Per the milestone's IMPORTANT CONTRACT NOTE and the user's
explicit authorization, M9I-B is a **beta-internal** implementation: internal tables +
beta-internal endpoints + a **code-only** structuring agent. The competence/partner
`ResearchTask` purposes are **not** repurposed; M9I-B only *reads* the imported public
sources. **No finalized contract YAML was edited** (`git status` shows no change under
`final_backend_contracts_v1_1/`).

## Persistence design (migration `d7a3f1c9e524`, head `c5f9a2d7b3e1`)
- **`market_comparisons`**: comparison_id, project_id, workspace_id, `run_id` **nullable**
  (decoupled from runs), research_task_ids, status (draft|ready_for_review|stale|failed),
  research_gaps, warnings, comparison_version, source_scope_hash, generation_status
  (once-per-comparison guard), operation_id, error_code/safe_error_detail, created_by/at,
  updated_at.
- **`market_comparison_items`**: item_id, comparison_id, name, name_normalized (dedup),
  category, description, target_customer_segment, offering_summary, strengths, weaknesses,
  differentiation_relevance, relation_to_project, confidence_label (source_backed|
  needs_review|insufficient_evidence), status (proposed|accepted|rejected|
  needs_human_review), source_document_ids, **`verified_quote_refs`** (JSON), timestamps.
- **`verified_quote_refs`** (rule 6) = {source_document_id, source_version_id, fragment_id,
  quote, start_char, end_char, quote_hash, normalizer_version, verification_method
  (`deterministic_position_match`), verified_at, linked_evidence_anchor_id (nullable)}.
- No changes to evidence_* tables; **no fake EvidenceAnchors** are ever created.

## Source scope + extraction (`app/market/source_scope.py`)
Only imported public sources: `SourceDocument.type=="url"` + `origin=="public_source"` +
`sensitivity=="public"`, processed. `prefilter_fragments` deterministically selects the
market-signal-bearing fragments using the **M5 tokenizer** (`content_terms`) against a
small versioned `MARKET_SIGNAL_TERMS` set (DE+EN; not domain synonyms, not company names),
budget-limited. The pre-filtered fragments — **and nothing else** (no draft/private text,
no snippets, no provider payloads, rules 3 & 11) — are passed to the structuring agent.

## Beta-internal structuring agent (`app/market/agent_profile.py`, code-only)
A code-level `AgentProfileDef` (`MC.market_comparison`, agent_id `MC`, advisory,
`allowed_tools=()` so it cannot search/fetch/network) is injected into the in-memory agent
registry at startup; its I/O schemas (`MarketComparisonInput@v1` /
`MarketComparisonResult@v1`) live only in `app/agents/schemas.py::SCHEMA_MODELS`. It runs
through the existing `gateway.invoke(run_id=None)` (fake provider in tests). Prompt
`prompts/market_comparison_v1.md`: structure **only** the supplied public fragments; every
item must cite a `source_fragment_id` + an exact `quote`; never invent competitors/
numbers/market-size; never "market leader/unique/we are better" as fact; abstain →
research_gaps/warnings.

## Evidence linking (`app/market/verify.py`)
Reuses the M5 exact-match discipline (`quote_hash` + position match against the frozen
`SourceVersion.normalized_text`) **without** the run-scoped `verify_candidate` (which
requires a RunSourceSnapshot — `EvidenceCandidate/Anchor/Link` all have non-nullable
`run_id`). For each item: if the model's quote occurs **exactly** in the cited imported
fragment → `source_backed` + a full `verified_quote_refs` record; `linked_evidence_anchor_id`
is set **only** when a pre-existing `exact_verified` EvidenceAnchor already covers the same
source/version/span/quote_hash (never created). No exact match → `insufficient_evidence` /
`needs_human_review`, and the quote is dropped (snippets/payloads are never evidence).

## Generation (`app/market/{service,executor,cost_guard,recording}.py`)
`createMarketComparison` (member OR lead_admin; public/synthetic gate via the M9I-A web
policy) → 202 AsyncAccepted → background `comparison_executor`: once-per-comparison guard
→ pre-filter → `validate_payload` → `gateway.invoke(run_id=None)` → per-item standalone
verification + **dedup by normalized name** + item cap (20) → persist; status
`ready_for_review`. **Rule 13:** no imported sources / no usable passages → an **empty**
comparison with research_gaps (generation_status `skipped`), never invented content. Safe
failure → `failed` + safe detail; never raises. CostGuard is comparison-scoped (the gateway
performs no `run_id=null` aggregation — verified: all MC AgentInvocations have run_id null).

## API / BFF / frontend
- Backend `app/api/market.py` (beta-internal, registered in `main.py`): `POST
  /projects/{id}/market-comparisons`, `GET /market-comparisons/{id}`, `GET
  /projects/{id}/market-comparisons/latest`, `POST /market-comparison-items/{id}/status`.
- BFF proxies under `app/api/projects/[id]/market-comparisons[/latest]`,
  `app/api/market-comparisons/[id]`, `app/api/market-comparison-items/[id]/status`;
  `lib/market-comparison.ts` client.
- **Quellen**: `components/quellen/market-comparison-section.tsx` — full table
  (Lösung/Anbieter · Kategorie · Kurzbeschreibung · Relevanz · Differenzierungshinweis ·
  Quelle · Status), evidence quotes, research gaps, safe status labels ("Quelle erwähnt" /
  "Unklar — prüfen" / "Nicht ausreichend belegt"), accept/needs-review actions, **no "Für
  Antrag verwenden"**. Gated by a new `market_comparison` capability.
- **VC editor**: `components/editor/live-market-comparison.tsx` — a **compact, read-only**
  context rendered in the editor's "Markt"-tab (`market-competition-panel.tsx` live branch,
  threaded `projectId`); source-backed items + open questions only, no actions, no draft
  mutation.
- `capabilities`: `market_comparison` = web_research available; `url_import` stays false;
  mock mode unchanged. No provider/model/confidence anywhere in the UI.

## A2 integration boundary
A2 is **not** changed. Documented future hook only: `assemble_a2_context` could later add a
read-only `retrieve_market_comparison` that includes **only** accepted + source_backed
items (each with evidence), missing/weak items as placeholders/warnings, no auto-draft.

## Data policy + CostGuard
Public/synthetic only; the model call uses a **public** classification (only public
fragments are sent) → `data_policy.evaluate` allows; internal/confidential/NDA projects are
blocked at the availability gate. Comparison-scoped guards (once-per-comparison + item cap);
never aggregate under `run_id=null`. Fake provider drives mandatory tests (gated by
`web_research_fake_provider`); real provider optional/env-gated. No API key/provider/model/
raw-payload logged or surfaced.

## Tests / results (fake provider only)
- **Backend** `pytest`: **446 passed, 3 skipped** (new `test_market_comparison.py`, 12
  tests: standalone quote verification exact/altered; source-scope + prefilter incl.
  skip-without-market-terms; source-backed item with quote + no provider leak; empty +
  research_gaps when no sources; internal project blocked (422); fabricated quote →
  needs_human_review/insufficient_evidence (never evidence); dedup; **no draft/assessment/
  anchor mutation**; once-per-comparison guard; item status update; capability).
- **Frontend** `vitest`: **122 passed** (new `market-comparison-section.test.tsx`, 3:
  table+quote+status+gaps with no provider/confidence/"use in draft"; empty state;
  generate flow). `eslint` clean; `tsc --noEmit` clean; `next build` OK.
- **Playwright** (`--workers=1`, fakes): **18 passed, 1 skipped** — new
  `market-comparison.spec.ts`: (API) import two public sources → generate → ≥1 source_backed
  item with a verified quote → no drafts created; (UI) Quellen section renders the table +
  "Quelle erwähnt", no `firecrawl`/`anthropic`/`haiku` text. The `demo-dataset` spec is
  environment-gated and self-skips (unchanged by M9I-B).
- **Security**: backend log free of API key / provider / model / secret; all
  `MC.market_comparison` AgentInvocations have `run_id=null` (no run aggregation); no
  EvidenceAnchors created by the comparison flow.
- One incidental M9I-A test-fixture change: the deterministic web **fake fetch body** now
  includes market vocabulary so the comparison demo/e2e has source-backed text (dev/test
  fake only; no test asserted the old body; no contract/behaviour change).

## Known limitations
- Public/synthetic only; internal/confidential/NDA comparison is intentionally not built.
- Items carry a verified quote OR are needs_review/insufficient_evidence; there is no fuzzy
  evidence and no run-scoped EvidenceAnchor creation (anchors are only *linked* when they
  already exist from a prior analysis run).
- The structuring model is fake-driven in CI; the real provider path is env-gated and
  unexercised by tests.
- A2 consumption of the comparison is deferred (documented hook only).

## Readiness for M9H / M10
M9I-B delivers the auditable, source-backed comparison surface (beta-internal tables +
endpoints, deterministic verification reuse, advisory items, no draft/approval mutation,
no contract edits). The same verified-quote discipline and code-only-profile pattern
extend cleanly to **M9H Innovation Challenge** (another advisory review profile) and feed
**M10 Evaluation** (the comparison is an evidence-linked, human-reviewable artifact).
**Ready for M9H / M10.**
