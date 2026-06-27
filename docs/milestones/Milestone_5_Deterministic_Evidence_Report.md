# Milestone 5 — Deterministic Evidence Baseline, Exact Quote Verification & Live Evidence Workspace — Final Report

**Branch:** `feat/deterministic-evidence` (off tag **`milestone-4-1-unicode-ingestion`** @ M4.1 commit
`18c5ada`). **Date:** 2026-06-23. **Status:** ✅ Complete — all 22 acceptance criteria met.
**Not committed** (only the `milestone-4-1-unicode-ingestion` tag + branch were created).

Delivers a reproducible **deterministic (no-LLM)** evidence baseline: frozen `SourceFragment`s →
deterministic lexical candidate discovery → `EvidenceCandidate` → exact-quote verification against the
frozen normalized `SourceVersion` → `EvidenceAnchor` → links to `RequirementAssessment` → `listEvidence`
→ live "Quellen & Evidenz" workspace. **No** LLM, agent, embedding, vector DB, provider, Firecrawl,
cloud_assisted or semantic-similarity code. It is the comparison baseline for future A1-assisted
discovery (M9).

## 1. Changed / new files
**Backend (new):** `app/evidence/{__init__,tokenize,discovery,verification,pipeline}.py`,
`app/contracts/evidence.py`, `app/api/evidence.py`, `app/repositories/evidence.py`,
`app/migrations/versions/e7c2a9d4b8f1_deterministic_evidence.py`,
`tests/{test_evidence_discovery,test_evidence_verification,test_evidence_flow}.py`.
**Backend (modified):** `app/db/models.py` (+3 models + candidate.anchor_id), `app/runs/{graph,constants}.py`
(2 new nodes + 6-stage progress), `app/repositories/requirements.py` (+evidence_links),
`app/contracts/requirement.py` (evidence_links typed), `app/api/capabilities.py` (evidence=true),
`app/main.py` (router), `app/config/settings.py` (max candidates).
**BFF (new):** `app/api/runs/[id]/evidence/route.ts`.
**Frontend (new):** `lib/evidence.ts`, `components/quellen/live-evidence.tsx`,
`test/{evidence.test.ts,live-evidence.test.tsx}`, `e2e/evidence.spec.ts`.
**Frontend (modified):** `lib/{app-mode,capabilities,requirements}.ts`, `app/quellen/page.tsx`.

## 2. Migration
`e7c2a9d4b8f1` adds `evidence_candidates`, `evidence_anchors`, `evidence_links` with the stable
uniqueness constraints (below). Upgrade + downgrade verified clean through all revisions.

## 3. Deterministic retrieval algorithm — `evidence-lexical-1`
Tokenizer `evidence-tokenizer-1`: NFKC → casefold → Unicode word tokens (`\w+`, `re.UNICODE`) minus a
**versioned generic German + English stopword list** (function words only — articles, pronouns,
prepositions, conjunctions, auxiliaries; no domain synonyms, no stemming). Content terms = distinct
non-stopword tokens of length ≥ 2.
- **Search terms** per active user-facing `RequirementDefinition` derived mechanically from
  `title + description`.
- **Spans** = deterministic sentence/paragraph boundaries (`(?<=[.!?])\s+|\n+`), whitespace-trimmed so
  each quote is an **exact substring** of the fragment's normalized text, with its
  `span_start/end_in_fragment` recorded.
- **Scoring** = distinct non-stopword **token overlap** between requirement terms and span terms; a span
  is a candidate **only if ≥ 1 non-stopword token overlaps**.
- **Ranking** = score desc, then the **explicit canonical order** computed in code
  `(SourceVersion.created_at, source_id, fragment.ordinal, span start)` — never DB query order.
  Top-N per requirement (`evidence_max_candidates_per_requirement`, default 3); dedup by quote hash.
- Internal lexical relevance is stored as `retrieval_score` only — **separate from verification, never
  surfaced as confidence**.

## 4. EvidenceCandidate / Anchor / Link design + dedup
- **EvidenceCandidate** (internal): target requirement, fragment, source version, `proposed_quote`,
  `quote_hash`, `span_start/end_in_fragment`, `match_type=exact_normalized`, `retrieval_score`,
  `status=proposed`, `retrieval_algorithm_version`, `anchor_id`. Unique
  `(run, target_requirement, fragment, quote_hash)`.
- **EvidenceAnchor** (openapi): exact schema; **`match_score`/`coverage` left NULL** (contract defines no
  exact semantics; `exact_verified` = technical source existence). `human_checked_by/at` always NULL.
  `source_accessed_at` = `SourceVersion.created_at` (canonical local acquisition). Unique
  `(run, source_version, start_offset, end_offset, quote_hash)` — distinct occurrences of an identical
  quote stay distinct.
- **EvidenceLink** (openapi): `target_type=requirement_assessment`, `target_id=assessment_id`,
  `status=active`; `claim_id/claim_text` null. Unique `(anchor, target_type, target_id)`. Repository
  supports `active|stale|removed` (M5 creates only `active`).
- **Immutability + idempotency:** all persistence is **upsert-only** (insert-if-not-exists on the unique
  keys); a terminal run's artifacts are never deleted or rewritten; re-execution (checkpoint replay)
  produces no duplicates. A new evaluation requires a new run.

## 5. Exact verification algorithm (`verify_evidence_quote`, orchestrator-only)
Per candidate: assert the source version belongs to the run snapshot; assert the fragment belongs to the
version; **normalizer-version lock**; compute expected absolute offsets
`fragment.start_offset + span_*`; **validate the quote at that exact position**
(`normalized_text[start:end] == proposed_quote`) — **position-anchored, not a global first-match**, so
identical recurring quotes are disambiguated. Only `match_type=exact_normalized` + exact position +
valid offsets + version match → `exact_verified`. Otherwise `unverified` (missing/altered/position
mismatch) or `rejected` (out-of-snapshot / version mismatch / missing source). **fuzzy/semantic/manual
never become exact_verified; `human_verified` is never produced; no fuzzy threshold is invented.**

## 6. Graph changes
Canonical order now `initialize → validate_source_snapshot → extract_facts_and_map_evidence →
verify_evidence → evaluate_requirements_and_rules → finalize_run` (`STAGE_PROGRESS` 16/33/50/66/83/100).
- `extract_facts_and_map_evidence`: **A1 disabled** → deterministic discovery only, **no ExtractedFacts**;
  records a `deterministic_baseline` ControlResult.
- `verify_evidence`: exact verification → anchors; continues when candidates are unverified or none found
  (never fails the run).
- `evaluate_requirements_and_rules`: unchanged M4 rule engine, then materializes supplementary
  `EvidenceLink`s to the new assessments. **Evidence never changes a deterministic M4 status**
  (verified ≠ auto-fulfilled; unverified ≠ auto-blocked). Cancellation is checked before/after each node;
  SqliteSaver checkpointing preserved.

## 7. API / BFF / frontend
- **`listEvidence`** `GET /runs/{id}/evidence` → exact OpenAPI `EvidenceAnchor[]` (no extra fields),
  session + workspace/run isolation (foreign → 404), **explicit deterministic order in code**
  (source acquisition → page → start_offset → anchor_id), quote-only. **`listRequirements`** now returns
  contract-faithful `evidence_links`.
- **BFF + client:** `lib/evidence.ts` (typed `EvidenceAnchorDto`/`EvidenceLinkDto`, German labels).
- **UI:** `components/quellen/live-evidence.tsx` rendered in the Evidenz tab when live + a completed run
  exists. It fetches **both** `listEvidence` and `listRequirements` and **joins client-side**
  (anchor → link → assessment → requirement title); the anchor API stays schema-pure. Shows source
  name/type, page/section, exact quote, requirement context, status (Fundstelle bestätigt / Prüfen /
  Nicht bestätigt), a details disclosure, and an explicit note that "Fundstelle bestätigt" means the
  quote exists — not that it is fachlich approved. **No** human-check mark, "Geprüft von", confidence,
  provider/model or raw rule IDs. **Unverified anchors show as *Prüfen* but are not counted as verified
  coverage** (the indicator counts only `exact_verified`). Mock `EvidenceTab` + `dummyEvidence` unchanged.

## 8. Capabilities
After the full slice + tests pass: `capabilities.features.evidence=true`. `review/export/web_research`
and all AI/drafting stay false; runs remain `deterministic_only`; no cloud toggle.

## 9. Controls & audit
ControlResults (existing IDs only): `CTRL.RUN_SNAPSHOT_SCOPE, CTRL.LEAST_CONTEXT` (deterministic
retrieval), `CTRL.VERSION_LOCK` (version + normalizer lock), `CTRL.EVIDENCE_VERIFICATION` (exact-only
auto-verification), `CTRL.OUTPUT_SCHEMA, CTRL.EVIDENCE_REQUIREMENT`. AuditEvents:
`evidence.discovery_started/completed`, `evidence.candidate_created`,
`evidence.verification_started/completed`, `evidence.anchor_created/unverified`,
`evidence.link_created`. No full documents are logged — only quotes as evidence records.

## 10. Test results
| Suite | Result |
|---|---|
| Backend `python -m pytest` | ✅ **116 passed** (95 prior + **21 new**: discovery units, verification incl. position-anchored/version-lock/fuzzy-never/no-human_verified, flow incl. exact schema, evidence_links, status-unchanged, reproducible-across-runs, snapshot/dedup/cap, zero-candidate success, 401/404) |
| Frontend `pnpm test` (vitest) | ✅ **48 passed** (+7: evidence client, capability, LiveEvidence render incl. join, no-human-check, rejected/unverified, empty) |
| `pnpm exec tsc --noEmit` / `pnpm lint` / `pnpm build` | ✅ exit 0 |
| `pnpm exec playwright test` | ✅ **5 passed** (+ **M5 deterministic evidence end-to-end**) |
| Alembic upgrade/downgrade | ✅ clean |

## 11. Known limitations
- Lexical baseline only — discovery finds passages by exact token overlap; it does **not** assess
  relevance, sufficiency or truth (by design). Requirements whose German vocabulary does not appear
  verbatim in a source yield no candidates (allowed/safe).
- `match_score`/`coverage` are null (no contract-defined exact semantics); `retrieval_score` stays
  internal.
- No fuzzy/semantic matching, no human verification, no draft-target links (Drafting milestone).

## 12. Comparison baseline for future A1 (M9)
M5 establishes the deterministic ground truth: every anchor is an exact, position-verified substring of a
frozen source, fully reproducible across runs. M9's A1 (LLM) evidence discovery can be measured against
this baseline (precision/recall of candidates, verification agreement) using the same
`verify_evidence_quote` contract and the same `EvidenceAnchor` schema.

## 13. Remaining P0/P1 (next milestones)
M6 Template Drafts: `PortalFieldDraft` + `DraftVersion` + `base_version_id`, the public
`createEvidenceLink/deleteEvidenceLink` (field-draft) endpoints, and draft-target evidence links — all
deferred here. A1/A2/A3 + ModelGateway + providers + cloud remain in M9.

## 14. Readiness for M6 (Template Drafts) — GO
The evidence schema (anchors + links), exact verification, the immutable upsert persistence, the 6-stage
graph and the live Evidenz workspace are in place and tested. M6 can add field drafts + draft-target
evidence links on top of `EvidenceLink.target_type` without reworking this baseline. **No M5
implementation is auto-committed** (only the STEP-0 tag + branch).
