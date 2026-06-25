# Milestone 8 — Deterministic Export Artifacts (DOCX, Markdown, Technical Evidence)

## Basis

- Branch: `feat/export` (created from `e159783`, tag `milestone-7-review-approval`
  created on `e159783` as part of STEP 0).
- Pre-implementation gate (clean tree, full suite green) verified first: backend
  `pytest` 171 passed, `pnpm test` 73 passed, `tsc`/`lint`/`build` clean,
  Playwright green on the unchanged tree.
- No automatic commit was created (only the STEP-0 tag + branch).

## Scope

From a **completed** run's immutable artifacts + current DraftVersions +
assessments/issues/evidence + ReviewPackage/ReviewApproval, create an **async**
`ExportArtifact`, generate DOCX / Markdown / technical-evidence JSON, persist an
immutable file + content hash, poll status, and download. Exports truthfully
distinguish a **review-approved working artifact** from a **draft (ENTWURF)**
artifact and never imply submission/funding approval, portal submission, complete
validation or AI QA. No LLM / provider / network / A1–A3 / ModelGateway / cloud /
Firecrawl / OneDrive / PDF / ZIP / export-history endpoint.

## Contract conformance (openapi-v1_1.yaml — no inventions)

| Operation | Method/Path | Response |
|---|---|---|
| `createExport` | POST `/runs/{run_id}/exports` (CSRF + Idempotency-Key, roles member/lead_admin, audit) | **202 `AsyncAccepted`** |
| `getExport` | GET `/exports/{export_id}` | 200 `ExportArtifact` |
| `downloadExport` | GET `/exports/{export_id}/download` | 200 `application/octet-stream`, **409** until available |

`ExportArtifact` public fields are exactly `export_id, run_id, type, status,
draft_marked, filename?, created_at?`; statuses `queued|generating|available|
failed`. `ExportCreate = {type: docx|markdown|technical_evidence, force_draft:
bool=false}`. The registered tool `create_export_artifact` (network_access none,
deterministic, 5 calls/(run,format), 60s) and its controls (`CTRL.EXPORT_CLASSIFICATION,
CTRL.APPROVAL_GATE, CTRL.OUTPUT_SCHEMA, CTRL.FILENAME_NORMALIZATION, CTRL.AUDIT_WRITE`
+ `CTRL.RUN_SNAPSHOT_SCOPE, CTRL.VERSION_LOCK`) are honoured. No new public path,
field, status or control was invented.

## Changed files

- **Persistence**: `app/db/models.py` (+`ExportArtifact`, `ToolInvocation`,
  `ControlResult.{run_id, tool_invocation_id}`); migration
  `c8f1a2d3e4b5_export_artifacts.py`; `app/repositories/controls.py` (link params);
  `app/config/settings.py` (export settings).
- **Export package** `app/exports/`: `eligibility.py`, `snapshot.py`, `transitions.py`,
  `tool.py`, `service.py`, `executor.py`, `generators/{common,docx,markdown,
  technical_evidence}.py`. Storage `app/storage/exports.py`.
- **API/wiring**: `app/api/exports.py`, `app/contracts/export.py`, `app/main.py`
  (router + recovery), `app/api/capabilities.py` (`export=true`).
- **Frontend**: BFF `app/api/runs/[id]/exports/route.ts`, `app/api/exports/[id]/route.ts`,
  `app/api/exports/[id]/download/route.ts`; `lib/exports.ts`,
  `components/export/live-export.tsx`, `app/export/page.tsx`, `lib/app-mode.ts`.
- **Tests**: backend `tests/test_export_{eligibility,async,generators,security}.py`
  + `export_helpers.py` + conftest export-dir; frontend `test/exports.test.ts`,
  `test/live-export.test.tsx`; e2e `e2e/export.spec.ts`.

## Migration

`c8f1a2d3e4b5` (`down_revision = b7e3f5a91c42`): new `export_artifacts` (public
columns + internal storage/hash/snapshot/classification/tool-invocation columns),
new `tool_invocations`, and nullable `control_results.{run_id, tool_invocation_id}`.
`upgrade head → downgrade -1 → upgrade head` roundtrip verified clean.

## Storage design

`app/storage/exports.py` (`var/exports`, gitignored via `backend/.gitignore` `var/`,
test-overridden to a temp dir). Server-generated 32-hex keys, traversal-safe
`root/<ab>/<key>`, **atomic write (temp + `os.replace`)** with partial cleanup on
failure, `max_export_bytes` cap (fail-closed), SHA-256 + size + MIME mapping.
`open_verified()` **re-verifies the SHA-256 before returning bytes** (corr. #6);
on mismatch it fails closed (409 + audit, no bytes served). Files are never
publicly addressable — download is authenticated + workspace-scoped.

## Export-input snapshot

Built in the same transaction as the artifact (`app/exports/snapshot.py`). It
freezes the **full generator-facing representation of every mutable entity**
(RequirementAssessments, RuleResults, OpenIssues, ReviewFindings, EvidenceLink
states, review-relevant HumanDecisions, full ReviewPackage + ReviewApproval) and
embeds the immutable referenced content (DraftVersion text + content hash,
EvidenceAnchors), plus meta, effective classification, registry versions, a
**frozen timestamp**, a **coverage manifest** and `draft_marked`/reasons. Canonical
JSON (`sort_keys`, `ensure_ascii=false`) → SHA-256 `export_snapshot_hash`.
**Generators read only the snapshot** — never a mutable current-state row (corr. #1).
**Atomic consistency (corr. #2):** the snapshot is built, then the current
`approval_scope_hash` + `review_package_version` are recomputed and compared
immediately before persisting (at most one controlled retry); on drift → 409
`export_state_changed`. A later edit never alters an accepted artifact (test).

## Draft-marking decision table (frozen atomically at createExport)

| Condition | draft_marked |
|---|---|
| `force_draft=true` | **true** |
| no current run-scope ReviewApproval | **true** |
| latest run-scope approval stale (`status != approved` / invalidated) | **true** |
| `approval_scope_hash` ≠ current | **true** |
| `review_package_version` ≠ current | **true** |
| `run.recheck_required=true` | **true** |
| run completed **and** valid run-scope approval **and** hash+version match **and** recheck_required=false **and** force_draft=false | **false** |

Field-scope approval is insufficient for a non-draft run export. Blockers / stale /
missing approval never prevent creating a (draft) export. No export is described as
submission-ready.

## DOCX structure

Title, draft/approved status block, metadata (Förderinstrument, Run, frozen export
time, review status, package version, snapshot hash, no-submission disclaimer),
**coverage section**, supported fields in canonical registry order (label, current
text, char count/limit, active-evidence count), appendices for open issues + review
findings and concise technical traceability. **Draft** → `_ENTWURF` filename +
"ENTWURF – Nicht zur Einreichung" + the not-review-approved sentence. **Approved** →
"Review-freigegebener Arbeitsstand" + still the no-submission disclaimer. Never
"bewilligt/einreichbereit/automatisch eingereicht/Förderung empfohlen". Core
document properties + frozen timestamp are normalized → **structurally/semantically
deterministic** (not byte-asserted, per corr. #3). Unicode preserved.

## Markdown structure

UTF-8, `\n` line endings, **byte-deterministic** for an identical snapshot: title +
status + metadata block + `> Disclaimer`, `## Abdeckung / Coverage`, `## Portalfelder`
(per-field heading, current text, char info, evidence count), `## Offene Punkte`
(OpenIssues + open ReviewFindings), `## Evidenzübersicht` (anchor source/page/quote/
verification). No HTML, no AI prose. Draft suffix `_ENTWURF.md`; approved retains the
no-submission disclaimer.

## Technical-evidence schema/version

Internal schema **`technical-evidence-1`**, UTF-8 JSON (`ensure_ascii=false`,
`sort_keys`, fixed indent → **byte-deterministic**). Top-level
`artifact_kind="internal_audit_export"`, disclaimer, draft marking, snapshot hash,
**coverage manifest**, export/run/project metadata + classification, config/registry
versions, field drafts (id, draft_version_id, content hash, char count, text,
links), RequirementAssessments, RuleResults, OpenIssues, EvidenceAnchors,
EvidenceLinks, ReviewFindings, ReviewPackage/ReviewApproval, and **review-relevant
HumanDecision data only**. Excludes secrets/passwords/session/provider payloads/
prompts/full source text/filesystem paths/PII (test-enforced). Extension `.json`;
draft suffix `_ENTWURF.json`.

## Async execution + recovery

`createExport` (one transaction): scope+completed check; idempotency (replay →
original AsyncAccepted; same key+different body → 409); **5-call/(run,type) limit →
429** (replays don't count, corr. #4); freeze snapshot + draft_marked; insert
ExportArtifact `queued` + deterministic filename + ToolInvocation + AsyncOperation
(`resource_type="export"`); audit; 202 AsyncAccepted. Executor (`app/exports/executor.py`,
bounded semaphore, mirrors run_executor): `queued→generating`, run the tool
(generate in-memory — synchronous, deterministic, no network/LLM; bounded by the
configured 60s timeout via a wall-clock check), validate, atomic store + hash/size,
`generating→available`, operation succeeded. **Compensating** removal if the
post-store DB transition fails. On error: remove partial, export→failed,
operation→failed, safe Problem detail, never a stack trace, never touches run/review/
approval state. **Recovery** `recover_interrupted_exports()` (lifespan): queued/
generating artifacts → failed (`EXPORT_INTERRUPTED`) with their operations failed,
orphaned files purged, audit preserved, no auto-regenerate. **Download** verifies
the content hash before streaming (fail-closed on mismatch).

## Tool boundary

`app/exports/tool.py` mirrors `create_export_artifact` (typed I/O) and **persists a
canonical `ToolInvocation`** (input_hash = snapshot hash, output_hash = content hash,
status, timings, safe error_class). The required ControlResults are recorded
before/after generation and **linked via `ControlResult.tool_invocation_id`**.
`ToolInvocation` is internal (no public endpoint/field); the Domain Model names the
entity and the public ControlResult schema carries `tool_invocation_id`, so this is
contract-supported (its field-level shape is not pinned by the machine-readable
contract).

## Classification and access

The export persists its **effective DataClassification, inherited from the run
snapshot** (`effective_data_classification`), recorded by `CTRL.EXPORT_CLASSIFICATION`.
Files are never publicly addressable; download is authenticated + workspace-scoped
(404 cross-workspace).

## API / BFF / frontend changes

- API `app/api/exports.py` + `app/contracts/export.py` + `main.py` router.
- BFF: `runs/[id]/exports` (POST), `exports/[id]` (GET, was a 501 stub),
  `exports/[id]/download` (GET binary) via `forwardToBridge`. `"exports"` added to
  `LIVE_RESOURCES`. **`Content-Length` is intentionally NOT forwarded** through the
  bridge — streaming the body through Next.js re-frames it, and a forwarded length
  stalls/truncates JSON responses (it broke the editor PATCH in testing); download
  works correctly without it.
- Frontend `lib/exports.ts` (createExport+poll, getExport, blob download from
  Content-Disposition), `components/export/live-export.tsx` (3 cards
  Word-Arbeitsdokument/Markdown-Zusammenfassung/Technischer Nachweis; per-card
  Erstellen/Wird erstellt …/Bereit zum Herunterladen/Fehler; advisory review banner;
  **post-creation `draft_marked` from the artifact is authoritative** for the badge +
  filename, corr. #8; fixed no-submission disclaimer; no "Letzte Exporte" in live
  mode), `app/export/page.tsx` (live/mock branch). Mock mode unchanged.

## Capability change

`features.export = true` (after the full slice + tests passed). AI/cloud/web_research/
redraft/critic stay false; review stays true.

## Controls and audit

ControlResults: `CTRL.RUN_SNAPSHOT_SCOPE, CTRL.APPROVAL_GATE, CTRL.EXPORT_CLASSIFICATION,
CTRL.VERSION_LOCK, CTRL.OUTPUT_SCHEMA, CTRL.FILENAME_NORMALIZATION, CTRL.AUDIT_WRITE`
(existing ids only, linked to the ToolInvocation). AuditEvents: `export.requested/
queued/started/generated/available/failed/downloaded` with ids/type/status/
draft_marked/hashes/size/approval ref. No full draft/source text, binary, paths or
secrets are logged.

## Test results

- **Backend** `pytest`: **206 passed** (171 baseline + 35 new across
  `test_export_eligibility.py`, `test_export_async.py`, `test_export_generators.py`,
  `test_export_security.py`); `compileall` clean. Covers the full draft-marking table,
  snapshot completeness + immutability, atomic-consistency 409, ToolInvocation +
  linked controls, 5-call/429, idempotency replay + 409, lifecycle to available,
  failure path, interrupted recovery + orphan purge + reconcile, compensating delete,
  hash-mismatch fail-closed download, classification inheritance, workspace isolation,
  run-must-be-completed, download 409-before / bytes+filename-after, DOCX (opens with
  python-docx, metadata, canonical order, Unicode, coverage, draft/approved markers,
  disclaimer, structural determinism), Markdown (deterministic bytes, sections,
  coverage, suffix), technical-evidence (deterministic JSON, internal-audit label,
  coverage manifest, traceability, no secrets/session/PII/full-source/paths), and
  security (401/403/CSRF/Origin/invalid-type 422/safe filename/no traversal/no network).
- **Migration**: upgrade/downgrade/upgrade roundtrip clean.
- **Frontend** `pnpm test`: **81 passed** (73 baseline + 8 new); `tsc --noEmit` 0,
  `pnpm lint` 0, `pnpm build` success.
- **Playwright** (live servers): **8 passed + 1 seeded demo passed**. `export.spec.ts`
  drives the draft flow (unapproved run → DOCX → ENTWURF filename + zip body →
  technical_evidence → `draft_marked=true`) and the approved flow (all fields filled →
  recheck → run-scope approval → Markdown → no `_ENTWURF` + no-submission disclaimer)
  plus a live Export-Center UI smoke. All prior M4–M7 specs + the M6.1 demo-dataset
  spec still pass.

## Demo impact

The demo seed is unchanged and still completes both runs through the (unchanged)
graph; `features.export=true` is now advertised. No demo run is auto-exported. The
dev DB was reset to clean after verification; `backend/var/exports` stays gitignored.

## Known limitations

- DOCX is structurally/semantically deterministic, not byte-identical (python-docx
  writes zip timestamps; core properties are normalized — corr. #3). Markdown +
  technical-evidence JSON are byte-deterministic.
- The 60s tool timeout is enforced as a wall-clock bound around the synchronous
  in-memory generator (a thread cannot be preempted on the local single-instance
  beta); deterministic generation completes in milliseconds.
- Coverage is limited to the M6-supported portal fields by design; structured/
  repeated areas (work packages, milestones, budget) are disclosed as deferred in
  every export (DOCX/Markdown section + JSON coverage manifest).

## P0/P1 findings

- **P0**: none.
- **P1**: public draft-version-history display/restore remains deferred (carried over
  from M7 — no contract endpoint). No export-specific P1.

## Readiness verdict

The deterministic export flow — immutable input snapshot, scope-aware draft marking,
atomic consistency, DOCX/Markdown/technical-evidence generators, atomic + integrity-
checked storage, async execution + safe recovery, the registered-tool boundary with a
persisted ToolInvocation and linked controls, and a live Export Center — is implemented
contract-faithfully and fully covered by automated backend, frontend and live
end-to-end tests, without breaking any prior milestone or the demo seed, and without
any LLM/provider/cloud/portal-submission. Ready for **Milestone 9 (Agent Activation)**.
