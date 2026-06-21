# Frontend API Coverage Matrix — v1

**Contract:** Innosuisse Proposal Assistant API **v1.1.0** (`openapi-v1_1.yaml`, 72 operations, base
`/api/v1/`). **Date:** 2026-06-21. Companion to
[Frontend_Contract_Readiness_Audit_v1.md](./Frontend_Contract_Readiness_Audit_v1.md).

## Legend

**Category (Rule 4):** `user` = user_facing · `admin` = admin_facing (lead_admin) · `infra` =
frontend_infrastructure · `system` = system_internal · `post-beta` = planned_post_beta · `n/a` =
not_applicable_to_ui.

**Beta gap status:**
- `WIRED·MVP` — a client function + BFF handler exist, but target the older `research-funding-mvp`
  shape; needs repath/reshape to v1.1.
- `MISSING` — a user/admin-facing consumer is expected for the beta but nothing is wired → **true gap**.
- `INFRA` — infrastructure/system op; consumed indirectly, no dedicated screen → not a beta gap.
- `POST-BETA` — no beta consumer expected; deferred.

**Async:** ✓ = contract returns `202 AsyncAccepted` (operation_id + poll_url). **Idem** =
`Idempotency-Key` expected. All write ops also expect `X-CSRF-Token`.

---

## Session, identity, capabilities

| operationId | Method · Path | Cat | Beta UI consumer | Current frontend wiring | Gap |
|---|---|---|---|---|---|
| createSession | POST /session | user | Login | **Mock** — `app/login/page.tsx` setTimeout+redirect; no call | MISSING |
| getSession | GET /session | infra | session bootstrap/guard | none | MISSING |
| getCurrentUser | GET /me | infra | topbar identity | `currentUser` mock (`lib/mock-data.ts:4`) | MISSING |
| deleteSession | DELETE /session | user | Logout (user-menu) | **No-op** `DropdownMenuItem` (`user-menu.tsx:50`) | MISSING |
| getCapabilities | GET /capabilities | infra | role/feature gating | none (role hardcoded) | MISSING |

## Projects & partners

| operationId | Method · Path | Cat | Beta UI consumer | Current wiring | Gap |
|---|---|---|---|---|---|
| listProjects | GET /projects | user | Dashboard | `dashboardProjects` mock (`lib/mock-data.ts:46`) | MISSING |
| createProject | POST /projects | user | Intake submit | none (intake stored locally) | MISSING |
| getProject | GET /projects/{id} | user | project context | `projects[0]="p1"` mock | MISSING |
| updateProject | PATCH /projects/{id} | user | Intake/edit | none | MISSING |
| listPartners | GET /projects/{id}/partners | user | Partner screen | free-text in `IntakeFormData.partner` | MISSING |
| createPartner | POST …/partners · Idem | user | Partner screen | none | MISSING |
| updatePartner | PATCH /partners/{id} | user | Partner screen | none | MISSING |
| deletePartner | DELETE /partners/{id} | user | Partner screen | none | MISSING |

## Sources, research, classification

| operationId | Method · Path | Cat | Beta UI consumer | Current wiring | Gap |
|---|---|---|---|---|---|
| listSources | GET /projects/{id}/sources | user | Quellen | `dummySources` static (`quellen/page.tsx:481`) | MISSING |
| uploadSourceFiles | POST …/sources/files · Idem | user | Quellen upload | `uploadSource()`→`POST /api/sources`→`/sources` | WIRED·MVP |
| createTextSource | POST …/sources/text · Idem | user | Quellen (text) | none (file-only, `source-table.tsx:31`) | MISSING |
| importUrlSource | POST …/sources/url · Idem | user | Quellen (URL) | none | MISSING |
| getSource | GET /sources/{id} | user | source status poll | none (fake `setTimeout`) | MISSING |
| deleteSource | DELETE /sources/{id} | user | Quellen remove | **local-only** (`source-table.tsx:217`) | MISSING |
| createResearchTask | POST …/research-tasks ✓ Idem | user (lead_admin) | Public research | none | MISSING |
| getResearchTask | GET /research-tasks/{id} | user | research poll | none | MISSING |
| listResearchResults | GET …/research-results | user | research results | none | MISSING |
| importResearchResult | POST /research-results/{id}/import · Idem | user | import result | none | MISSING |
| createProcessingConfirmation | POST …/processing-confirmations · Idem | user | cloud-processing confirm | none | MISSING |
| createReclassification | POST …/reclassifications · Idem | user | reclassify data | none | MISSING |
| getProjectLimits | GET /projects/{id}/limits | admin | cost limits | `costLimit` client-only (`AnalyseSettings`) | MISSING |
| updateProjectLimits | PATCH …/limits | admin | cost limits | none | MISSING |

## Runs & polling

| operationId | Method · Path | Cat | Beta UI consumer | Current wiring | Gap |
|---|---|---|---|---|---|
| listProjectRuns | GET /projects/{id}/runs | user | dashboard/run history | none | MISSING |
| createRun | POST /projects/{id}/runs ✓ Idem | user | Analyse starten | `startRun()`→`POST /api/runs`→`/runs`, **sync** | WIRED·MVP |
| getRun | GET /runs/{id} | user | progress polling | `getRun()`→`/runs/{id}` (1s poll) | WIRED·MVP |
| cancelRun | POST /runs/{id}/cancel | user | Stop | `stopRun()`→`/runs/{id}/**stop**` | WIRED·MVP |
| resumeRun | POST /runs/{id}/resume | user | Resume | `resumeRun()`→`/runs/{id}/resume` | WIRED·MVP |
| startFinalQualityReview | POST …/final-quality-review ✓ | admin | optional final review | none | POST-BETA |

## Requirements, evidence, fields, drafts

| operationId | Method · Path | Cat | Beta UI consumer | Current wiring | Gap |
|---|---|---|---|---|---|
| listRequirements | GET /runs/{id}/requirements | user | Anforderungen | mock `mapBackendRequirements` (MVP shape, `run-steps.ts:157`) | WIRED·MVP |
| listEvidence | GET /runs/{id}/evidence | user | Evidenz tab | `dummyEvidence` static | MISSING |
| listFields | GET /runs/{id}/fields | user | Review/Editor | `getRunFields()`→`/runs/{id}/fields` | WIRED·MVP |
| getField | GET /runs/{id}/fields/{field_id} | user | field detail | none (list only) | MISSING |
| updateField | PATCH …/fields/{field_id} · Idem | user | save draft | `patchSection()`→`/sections/{fieldId}`, **no base_version/409** | WIRED·MVP |
| createRedraft | POST …/fields/{field_id}/redrafts ✓ Idem | user | Redraft | `redraftField()`→`/runs/{id}/redraft` (run-level, sync) | WIRED·MVP |
| createEvidenceLink | POST …/evidence-links · Idem | user | link evidence | none | MISSING |
| deleteEvidenceLink | DELETE …/evidence-links/{id} | user | unlink evidence | none | MISSING |

## Review, decisions, approval, recheck

| operationId | Method · Path | Cat | Beta UI consumer | Current wiring | Gap |
|---|---|---|---|---|---|
| getReview | GET /runs/{id}/review | user | Review package | folded into `getRunFields` | WIRED·MVP |
| createHumanDecision | POST /runs/{id}/human-decisions · Idem | user | confirm/override issue | folded into `submitReview`→`/review` | WIRED·MVP |
| startTargetedRecheck | POST /runs/{id}/rechecks ✓ Idem | user | "Änderungen prüfen" | folded into `submitReview` (sync) | WIRED·MVP |
| createApproval | POST /runs/{id}/approvals · Idem | user | Freigeben | folded into `submitReview`; no scope/stale model | WIRED·MVP |

## Export

| operationId | Method · Path | Cat | Beta UI consumer | Current wiring | Gap |
|---|---|---|---|---|---|
| createExport | POST /runs/{id}/exports · Idem | user | Export erzeugen | none (GET-binary instead) | WIRED·MVP |
| getExport | GET /exports/{id} | user | export status | none | MISSING |
| downloadExport | GET /exports/{id}/download | user | download | `exportDownloadUrl()`→`/runs/{id}/export?kind=` | WIRED·MVP |

## Usage, services, operations, health, audit, controls

| operationId | Method · Path | Cat | Beta UI consumer | Current wiring | Gap |
|---|---|---|---|---|---|
| getUsage | GET /projects/{id}/usage | user | Kosten | mock cost (`kosten-mock-data`, `api.ts:124`) | MISSING |
| getServiceAvailability | GET /services/availability | infra | KI/web toggles | local scenario flags | MISSING |
| testServiceConnection | POST /services/{service}/test | admin | Admin Dienstetest | none | POST-BETA |
| getOperation | GET /operations/{id} | infra | async poll | none (no async-op model) | MISSING(infra) |
| getHealth | GET /health | system | — | none | INFRA |
| listAuditEvents | GET /runs/{id}/audit | admin | Admin audit | none | POST-BETA |
| listControlResults | GET /runs/{id}/controls | admin | Admin controls | none | POST-BETA |
| getApplicationStructure | GET …/application-structure | infra | field/section defs | hardcoded `portalSections` | INFRA |

## Structured application data (full-contract scope — STEP 6)

All **POST-BETA**; **no UI exists** (zero matches across the frontend). Recommend a separate
**"Projektdaten & Planung"** workspace (progressive disclosure), not Intake overload.

| operationId | Method · Path | Cat | Gap |
|---|---|---|---|
| getProjectDates / updateProjectDates | GET·PATCH /projects/{id}/project-dates | post-beta | POST-BETA |
| listWorkPackages / createWorkPackage / updateWorkPackage / deleteWorkPackage | …/work-packages | post-beta | POST-BETA |
| listMilestones / createMilestone / updateMilestone / deleteMilestone | …/milestones | post-beta | POST-BETA |
| getPlannedHours / updatePlannedHours | …/planned-hours | post-beta | POST-BETA |
| getBudgetPlan / updateBudgetPlan | …/budget-plan | post-beta | POST-BETA |
| getRiskRegister / updateRiskRegister | …/risk-register | post-beta | POST-BETA |

---

## Coverage statistics (72 operations)

| Bucket | Count | Notes |
|---|---|---|
| **WIRED·MVP** (repath/reshape needed) | 13 | createRun, getRun, cancel(stop), resume, listRequirements, listFields, updateField, createRedraft, getReview, createHumanDecision, startTargetedRecheck, createApproval, createExport/downloadExport, uploadSourceFiles — *all behind `USE_MOCKS=true`* |
| **MISSING** (expected beta consumer, unwired) | ~22 | session×4, capabilities, projects×4, partners×4, sources (list/text/url/get/delete), listEvidence, evidence-links×2, getField, getExport, getUsage, serviceAvailability, processing-confirmation, reclassification, research×4, limits×2 |
| **POST-BETA** (no beta consumer) | ~21 | project-dates, work-packages×4, milestones×4, planned-hours×2, budget-plan×2, risk-register×2, audit, controls, final-quality-review, testServiceConnection |
| **INFRA / system** | ~4 | getHealth, getOperation, getApplicationStructure, (serviceAvailability infra) |

> Counts are approximate where one screen maps to several ops; the authoritative per-op rows are
> above. The decisive facts: **every wired operation targets the MVP shape, not v1.1**, and **all are
> gated behind `USE_MOCKS=true`**, so no operation is live today.
