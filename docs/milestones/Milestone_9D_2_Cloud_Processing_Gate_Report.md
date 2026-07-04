# Milestone 9D.2 — Cloud Processing Gate & A2 Runtime Availability

**Scope:** privacy + runtime-availability milestone (not a new agent). Open a safe,
explicit, auditable path so a public/synthetic project can run `cloud_assisted`,
making A2 `SOL.INNOVATION_SOLUTION.EDITOR` suggestions reachable. Internal,
confidential and NDA data stay blocked. No finalized contract was changed; no new
public endpoint, processing mode, data classification, AI capability, provider route
or approval semantic was invented.

## Branch / commit basis

- Branch: **`feat/cloud-processing-gate`**, created from **`c36d474`**
  ("Milestone 9D_1: stabilize M9D E2E acceptance after UX changes").
- Tag **`milestone-9d-a2-solution-innovation`** added on **`73754c8`** (Milestone 9D).
- **M9D.1 baseline note:** at the start of this milestone the M9D.1 acceptance work
  was uncommitted; the user committed it as `c36d474` before the new branch was cut,
  so M9D.2 builds on a clean tree. No auto-commit was performed for M9D.2 itself
  (only the tag + branch).

## Authorized contract deviation (role)

The finalized OpenAPI pins `createProcessingConfirmation` to
`x-required-roles: [lead_admin]`. Per the binding role correction, and with explicit
user authorization, the implementation allows **member OR lead_admin** (any project
participant with access). This is a documented, intentional, *more-permissive*
deviation of the role guard only — path, request/response schema, audit-required,
CSRF/Origin, and the data-policy block are unchanged. The confirmation is a per-run
user acknowledgement, **not** an institutional provider approval.

## Changed / new files

**Backend**
- `app/db/models.py` — new `ProcessingConfirmation` table; `RunPolicySnapshot` gains
  nullable `cloud_confirmation_id` + `provider_route_class`.
- `app/migrations/versions/b4e8f1a3c6d2_processing_confirmations.py` — migration
  (UP/DOWN/REUP verified).
- `app/contracts/processing.py` — `ProcessingConfirmationCreate` / `ProcessingConfirmation`
  (matches the pinned OpenAPI schemas; `extra="forbid"`).
- `app/repositories/processing_confirmations.py` — create / get_scoped / mark_used /
  project_source_version_ids / to_contract.
- `app/api/projects.py` — `createProcessingConfirmation` endpoint (member+lead_admin,
  CSRF/Origin, Idempotency-Key, audit-required).
- `app/runs/cloud_policy.py` — the run-creation gate (`validate_cloud_run`),
  eligibility, provider route class, ControlResult + AuditEvent on every decision.
- `app/runs/policy.py` — `validate_processing_mode` removed; `build_policy_snapshot`
  now freezes the confirmation ref + provider route class + allowed routes.
- `app/runs/service.py` — `prepare_run` calls the gate and consumes the confirmation.
- `app/agents/field_drafting.py` — `availability()` adds a provider-availability check.
- `tests/test_processing_gate.py` (new), `tests/test_runs.py` (updated cloud test).

**Frontend**
- `lib/runs.ts` — `RunSettings.internal_cloud_confirmation_id`.
- `lib/processing-confirmations.ts` — `createProcessingConfirmation` client (new).
- `app/api/projects/[id]/processing-confirmations/route.ts` — BFF proxy (new).
- `lib/types.ts` — `AnalyseSettings.cloudConfirmed`.
- `components/run/analyse-einstellungen-dialog.tsx` — cloud opt-in explanation +
  required one-run confirmation checkbox; start blocked until confirmed.
- `app/quellen/page.tsx` — `handleAnalysisStart` derives the processing mode from the
  KI opt-in + confirmation (the previously hard-coded `deterministic_only` is gone),
  creating the confirmation then the cloud run; surfaces `RunError` messages.
- `test/processing-confirmations.test.ts`, `test/analyse-einstellungen-dialog.test.tsx`
  (new); `test/setup.ts` (jsdom PointerEvent polyfill for base-ui controls).
- `e2e/a2-solution-innovation.spec.ts` — added **Flow A** (cloud → A2 → accept →
  recheck); kept/clarified **Flow B** (deterministic → safe 503).

## Processing-confirmation design

A confirmation is a per-run, one-run acknowledgement bound to `(project,
source_version_ids, policy_version 1.1.0)`. It is created with `status=valid` and
consumed (`status=used`, `used_by_run_id`) exactly once when a `cloud_assisted` run
that references it is created. It freezes `provider_route_class` (`anthropic_direct`,
the A2 primary route) and a `confirmation_text_version`. It records, but never
exposes to users: the data classification shown, the policy version, the provider
route class, and the confirming user.

## Data Policy decision table (each row → ControlResult + AuditEvent)

| sensitivity | origin | nda | mode | confirmation | provider | result |
| --- | --- | --- | --- | --- | --- | --- |
| public | synthetic / public_source | false | cloud_assisted | valid | available | **allowed** — freeze + mark used |
| public | synthetic | false | cloud_assisted | missing/invalid | — | blocked `cloud_confirmation_required` (422) |
| internal | real_project | false | cloud_assisted | any | — | blocked `cloud_not_eligible_for_classification` (403) |
| confidential | any | any | cloud_assisted | any | — | blocked (403) |
| any | any | **true** | cloud_assisted | any | — | blocked (NDA, 403) |
| missing | — | — | cloud_assisted | any | — | blocked (deny-by-default, 403) |
| any | any | any | deterministic_only / local_only | n/a | n/a | allowed — no external call |
| public | synthetic | false | cloud_assisted | valid | **unavailable** | run created; A2 returns safe 503 |

Block decisions are committed independently of the failed request so every
allow/block is auditable.

## Run-creation changes

`prepare_run` calls `cloud_policy.validate_cloud_run` before any run state is built.
Non-cloud modes pass through unchanged. `cloud_assisted` is allowed only when the
classification is eligible AND a matching valid confirmation exists; the policy
snapshot then freezes `processing_mode`, the limits, `policy_version=1.1.0`,
`cloud_confirmation_id`, `provider_route_class`, and `allowed_routes=[route_class]`.
The mode is never silently up- or down-graded; no partially-cloud run is created.

## A2 availability behaviour

`field_drafting.availability(run)` (createRedraft's 503 pre-check) keeps the mode +
data-policy checks and now also requires an available provider: a real configured
route adapter OR `settings.agent_fake_provider` (dev/test). So `deterministic_only`/
`local_only` → 503; eligible `cloud_assisted` with confirmation **and** an available
provider/fake → 202; a real route with no key in dev → 503 (no failing job). A2 stays
scoped to `SOL.INNOVATION_SOLUTION.EDITOR`; other fields 404. No model/provider name
surfaces to users.

## Audit / control behaviour

Confirmation creation and every run-gate decision record `CTRL.DATA_POLICY` +
AuditEvent. The audit detail carries confirmation_id, user_id, project_id,
source_version_ids, processing_mode, the classification shown, confirmation text
version, policy version, provider route class and timestamp — and **never** API keys,
raw source content, prompt text or provider payloads. Verified: no secret strings in
the live backend log; the user-facing `ProcessingConfirmation` response contains no
provider/model field; `features.ai` stays absent/false.

## UI / wording

The run-settings dialog shows, for public/synthetic and **all** participants with
access: *"Cloud-KI kann für diesen Durchlauf bewusst freigegeben werden, sofern die
Daten öffentlich oder synthetisch sind."* plus the exact policy lines (*"Cloud-KI kann
ausgewählte Inhalte an den konfigurierten KI-Dienst übermitteln." / "Diese Beta
erlaubt Cloud-KI nur für öffentliche oder synthetische Inhalte." / "Interne,
vertrauliche oder NDA-Inhalte werden blockiert."*) and the required checkbox
**"Cloud-KI für diesen Durchlauf erlauben"** with the confirmation sentence. No
provider/model ids, token/API jargon or policy codes; no wording implying data stays
local, the provider never processes it, output is automatically correct, funding
chances improve, or the application is submitted. Internal/confidential/NDA show the
local-only banner; a backend role/permission rejection surfaces the normal permission
message.

## Test results

- **Backend** `pytest`: all pass (baseline 353 + 3 skipped, plus 18 new gate tests in
  `test_processing_gate.py`; `test_runs.py` cloud test updated). Migration UP/DOWN/REUP
  verified; app starts; route registered; `features.ai` false.
- **Frontend** `vitest`: **113 passed** (27→29 files; +2 confirmation-client, +3 dialog
  tests). `tsc --noEmit` clean; `eslint .` clean; `next build` succeeds.
- **Playwright** (`--workers=1`, backend `AGENT_FAKE_PROVIDER=true`): all specs green —
  **Flow A** (public/synthetic → confirm → cloud run → createRedraft 202 → accept →
  agent DraftVersion + recheck_required) and **Flow B** (deterministic → safe 503,
  field-scoped, no mutation) pass; the remaining 9 live specs + the seeded demo spec
  (with `DEMO_DATA_ENABLED=true`) pass.

## Known limitations

- Cloud processing is available only for public/synthetic data. Internal cloud remains
  blocked (institutional approval not configured); confidential/NDA always blocked;
  missing classification denies by default.
- The confirmation is one-run; each cloud run needs a fresh confirmation.
- A2 mandatory tests and the e2e cloud flow run against the deterministic fake provider
  (`AGENT_FAKE_PROVIDER=true`); no real provider key is required or used.
- The `createProcessingConfirmation` role guard is intentionally more permissive than
  the finalized OpenAPI `x-required-roles` (authorized deviation, documented above).

## M9E readiness

The gate, the frozen cloud provenance on runs, and the auditable allow/block decisions
provide the runtime substrate M9E (Value Creation) can build on without re-opening the
data-policy boundary. No further contract change is required to reach A2 suggestions
for eligible data.
