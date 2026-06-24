# Milestone 6 — Deterministic Template Drafts, Versioned Field Workspace & Optimistic Concurrency — Final Report

**Branch:** `feat/template-drafts` (off tag **`milestone-5-deterministic-evidence`** @ M5 commit
`793aa26`). **Date:** 2026-06-24. **Status:** ✅ Complete — all 22 acceptance criteria met.
**Not committed** (only the `milestone-5-deterministic-evidence` tag + branch were created).

Delivers the complete **deterministic** Draft/Edit/Version/Conflict foundation before LLM drafting:
deterministic **template drafts** → `PortalFieldDraft` + immutable `DraftVersion` →
`listFields/getField/updateField` → **base_version_id optimistic concurrency (409 on stale)** →
**draft-version `EvidenceLink`s** (stale on edit) → `recheck_required` → live Proposal Editor. **No** LLM,
agent, provider, cloud, redraft, critic, review, approval or export. Templates are scaffolding (headings +
visible placeholders), invent no facts, and are never marked reviewed.

## 1. Supported & deferred field scope (registry-driven)
Resolved from `innosuisse_innovation_project_v1_1.yaml:portal_fields` by the rule
`agent_writable=true ∧ support_mode=draft_text ∧ field_kind∈{narrative_text,composite_editor} ∧ no "[]" in
structured_data_path ∧ not a repeated budget-position family`.
**Supported (8 singletons, in registry order):** `INTRO.APP.NAME` (no limit), `INTRO.APP.NAME_EN` (no
limit, placeholder-only — never auto-translated), `INTRO.APP.ABSTRACT` (300), `INTRO.APP.EXECUTIVE_SUMMARY`
(2000), `ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS` (300), `VC.BUSINESS_TARGETS_MODEL.EDITOR`
(composite, 15000), `SOL.INNOVATION_SOLUTION.EDITOR` (composite, 25000),
`PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION` (1000).
**Deferred — repeated instances with no contract `field_instance_id`:** `PS.WORK_PACKAGE.{DESCRIPTION,
ACTIVITIES,DELIVERABLES}` (`work_packages[]`), `PS.MILESTONE.DESCRIPTION` (`milestones[]`),
`PS.MATERIAL_POSITION.*`, `PS.CASH_CONTRIBUTION.*` (repeated budget positions). Modelling them as
singletons would require a contract change → out of scope (STOP condition respected).

## 2. Changed / new files
**Backend (new):** `app/drafts/{__init__,charcount,templates,pipeline}.py`, `app/contracts/draft.py`,
`app/api/fields.py`, `app/repositories/drafts.py`,
`app/migrations/versions/f4b8c1d6e9a2_template_drafts.py`, `tests/{test_draft_scope,test_draft_flow}.py`.
**Backend (modified):** `app/registry/loader.py` (+PortalFieldDef + portal_fields parsing + m6 scope +
mandatory_questions), `app/registry/__init__.py`, `app/db/models.py` (+2 models), `app/runs/{graph,
constants}.py` (+2 nodes, 8-stage progress), `app/repositories/evidence.py` (+draft-link helpers),
`app/api/{capabilities,main}.py`, `app/contracts/requirement.py` (already typed).
**BFF (new):** `app/api/runs/[id]/fields/[field]/route.ts` + `.../evidence-links/route.ts` +
`.../evidence-links/[link]/route.ts`; updated `app/api/runs/[id]/fields/route.ts` (forwardToBridge).
**Frontend (new):** `lib/fields.ts`, `components/editor/live-editor.tsx`,
`test/{fields.test.ts,live-editor.test.tsx}`, `e2e/template-drafts.spec.ts`.
**Frontend (modified):** `lib/{app-mode,capabilities}.ts`, `app/editor/page.tsx`.

## 3. Migration
`f4b8c1d6e9a2` adds `portal_field_drafts` (unique `(run_id, field_id)`) + `draft_versions`. Upgrade +
downgrade verified clean.

## 4. Template catalogue (`template-drafts-1`) + placeholder syntax
Internal versioned config; not an Innosuisse rule. Each template uses only the registry's verbatim
`label_or_question` text + visible, machine-detectable placeholders
**`[[Angabe ergänzen: …]]`** (placeholder version `placeholder-1`, regex `\[\[Angabe ergänzen:[^\]]*\]\]`).
Composite editors are built from the registered Mandatory-Content main questions in registry order
(VC → `3.1`/`3.2`; SOL → `4.1`–`4.5`), each verbatim as a heading + placeholder. No prose, no translation,
no invented facts/claims, no evidence quotes inserted. Inputs are immutable run data only (RunProjectSnapshot,
RequirementAssessments, OpenIssues, exact-verified anchors, registry field profiles); mutable live
project/partner state is never read.

## 5. Persistence / versioning
`PortalFieldDraft` (one per run+field, status `needs_review`, `template_catalog_version`,
`current_version_id`, `open_issue_count`; run_id/timestamps internal). `DraftVersion` immutable
(`created_by` template|user — **never agent**, SHA-256 `content_hash` over exact UTF-8,
internal `base_version_id`/`source_operation_id`). Initial drafts via upsert (idempotent on
checkpoint replay); **identical submitted text returns the current version** (no redundant version);
terminal-run versions never deleted/rewritten.

## 6. Character-count semantics
One canonical counter: **Unicode code points** — backend `app/drafts/charcount.py::char_count = len(str)`,
frontend `lib/fields.ts::charCount = [...text].length` (identical for all code points). User text is never
trimmed/rewritten; over-limit → **422 `character_limit_exceeded`** (no version; browser keeps text).

## 7. Conflict behaviour (optimistic concurrency)
`updateField` requires `base_version_id`. If it is not the current version → **409 `stale_base_version`**:
no version created, no overwrite, no DB internals leaked. The live editor shows a conflict dialog
("Dieser Abschnitt wurde zwischenzeitlich geändert.") and **preserves the user's local text**, offering
"Neueste Version laden" or "Eigenen Text behalten". No automatic merge.

## 8. Evidence-link lifecycle (reuses the M5 EvidenceLink)
`createEvidenceLink` (CSRF + Idempotency-Key): anchor must belong to the run/workspace; `base_version_id`
must be current (else 409); creates `target_type=draft_version, target_id=current_version_id,
status=active`; idempotent replay returns the same link. On every successful text edit, active links
targeting the **previous** version → `stale` (never copied forward; user must relink). `deleteEvidenceLink`
(CSRF) → `removed`, history preserved → 204. M6 never creates human_verified / claim / extracted-fact /
review-finding links; unverified anchors are linkable but shown as *Prüfen* and not counted as verified
coverage.

## 9. Graph + run staleness
8-stage canonical order: `… → evaluate_requirements_and_rules → draft_fields → create_template_drafts →
finalize_run` (progress 12/25/37/50/62/75/87/100). `draft_fields` records a `CTRL.DATA_POLICY` control
(`a2_disabled deterministic_template`) — no provider call — and continues. `create_template_drafts` builds
drafts idempotently. Every draft edit / evidence-link change sets **`run.recheck_required=true`** + audit;
historical RequirementAssessments and EvidenceAnchors are unchanged; M6 executes no targeted recheck.
Completed-run meaning: *"Fördervoraussetzungen geprüft und Strukturvorlagen erstellt."* — not reviewed/
ready/approved. M5 historical runs are not backfilled.

## 10. API / frontend
Exact OpenAPI operations `listFields` (stable canonical registry order, supported fields only, exact
`PortalFieldDraft[]` incl. `current_version`/`evidence_links`/`open_issues`), `getField` (404
unsupported/foreign), `updateField` (PATCH, CSRF, DraftPatch → 200/409/422/404), `createEvidenceLink`
(POST, CSRF + Idempotency → 201), `deleteEvidenceLink` (DELETE, CSRF → 204). No undocumented response
fields. `createRedraft` is a non-goal — not implemented. The live editor (live mode + latest completed
run) shows the **"Strukturvorlage"** badge, "Bitte fachlich prüfen und ergänzen.", live char count, save
states (Änderungen / Speichert … / Gespeichert / Konflikt / Fehler), the conflict dialog, the recheck
notice, and an evidence panel (run anchors + active/stale/removed links + Verknüpfen/entfernen + the
"bestätigt nicht automatisch den gesamten Text" note + stale-link notice). **No** AI suggestion / Redraft /
provider/model / human-check / Review / Approval / Export. Mock `ProposalEditor` unchanged.

## 11. Capabilities, controls & audit
`features.drafts=true` (after the full slice + tests). AI-drafting/redraft/critic/review/approval/export/
cloud/web_research stay false; runs `deterministic_only`. ControlResults use existing IDs only
(`CTRL.DATA_POLICY, CTRL.RUN_SNAPSHOT_SCOPE, CTRL.OUTPUT_SCHEMA`). AuditEvents:
`draft.template_created/version_created/update_attempted/update_succeeded/version_conflict/fields_a2_skipped/
stage_completed`, `evidence_link.created/removed`, `run.recheck_required`. No full draft text/source in
logs — content hashes + IDs only.

## 12. Test results
| Suite | Result |
|---|---|
| Backend `python -m pytest` | ✅ **136 passed** (116 prior + **20 new**: scope/templates, persistence, updateField 409/422/no-dup/recheck/CSRF/isolation, evidence-link lifecycle, M4/M5 intact) |
| Frontend `pnpm test` (vitest) | ✅ **58 passed** (+10: fields client + LiveEditor render/conflict-preserves-text/recheck/no-AI) |
| `pnpm exec tsc --noEmit` / `pnpm lint` / `pnpm build` | ✅ exit 0 |
| `pnpm exec playwright test` | ✅ **6 passed** (+ **M6 template drafts: edit, persist, link, stale, conflict**) |
| Alembic upgrade/downgrade | ✅ clean |

## 13. Known limitations
- The project title is not in the immutable run snapshot, so `INTRO.APP.NAME`/`NAME_EN` stay placeholders
  (no invented/translated content) — a later milestone could freeze the title into the snapshot.
- Repeated work-package / milestone / budget-position drafts are deferred until the contract models a
  `field_instance_id`.
- Drafts are scaffolding only; semantic completeness is never assessed (a below-limit text is not
  "complete"). No fuzzy/semantic logic, no agent versions.

## 14. Remaining P0/P1 & readiness for M7 (Review, Recheck, Approval) — GO
The versioned field workspace, optimistic-concurrency edits, draft-version evidence links and the
`recheck_required` flag are in place and tested. M7 can add `critic_review`/`aggregate_review`/
`human_review` stages, `ReviewFinding`, `HumanDecision`, `ReviewApproval` and the targeted-recheck
execution on top of these mechanics without reworking the draft foundation. **No M6 implementation is
auto-committed** (only the STEP-0 tag + branch).
