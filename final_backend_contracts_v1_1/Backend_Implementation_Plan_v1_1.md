# Backend Implementation Plan v1.1

## Objective

Implement the backend from hardened contracts without reopening architecture decisions. The priority is correctness, user value, evidence quality and a stable end-to-end Evaluation-Beta.

## Phase 1 — Contracts and Startup Validation

**Deliverables**

- `backend/app/contracts/` Pydantic models
- YAML registry models
- Config loader
- Cross-reference validator
- OpenAPI lint/check
- generated TypeScript client types

**Startup must fail when**

- unknown profile/tool/control/schema/requirement/field/model ID,
- profile/tool authorization mismatch,
- non-canonical enum,
- active rule without source,
- A2 field is not agent-writable,
- missing deployment upload limit,
- invalid provider route configuration.

## Phase 2 — Security, Identity and Persistence

- preprovisioned users
- password hashing
- HTTP-only session
- CSRF + Origin checks
- SQLite + Alembic
- repositories
- immutable audit
- source/export storage roots
- hashing and safe filenames

## Phase 3 — Structured Application Data

- Projects and Partners
- ProjectDates
- WorkPackages/PartnerAllocations
- Milestones/Goals
- PlannedHours
- BudgetPlan and line items
- RiskRegister
- optimistic concurrency
- deterministic derived totals

## Phase 4 — Sources and Evidence

- PDF/DOCX/TXT ingestion
- parser registry
- canonical normalization
- fragments, page/section/offsets
- EvidenceCandidate
- exact verification
- fuzzy/semantic human-review path
- EvidenceLinks and stale logic

## Phase 5 — Requirements, Rules and Controls

- Requirement loader
- code-ready deterministic rules
- RuleResult/RequirementAssessment/OpenIssue
- Data Policy environments
- Control executor
- CostGuard
- URL/SSRF/redirect controls
- audit/usage

## Phase 6 — Deterministic Run

```text
Project snapshot
→ sources
→ requirements/rules
→ evidence
→ template drafts
→ review package
→ human edit/decision
→ targeted recheck
→ approval
→ finalize
→ export
```

No LLM is required for this milestone.

## Phase 7 — Agent Activation

Order:

1. A1 Project Fact Extraction
2. A1 Evidence Candidate Mapping
3. A2 Solution & Innovation
4. A2 Value Creation
5. remaining A2 profiles
6. A3 Evidence Consistency
7. A3 Innovation Challenge
8. A3 Fit-Gap/Readiness
9. Public Competence Research
10. optional Final Review

Each profile requires:

- schema contract test,
- source grounding test,
- prompt-injection test,
- policy block test,
- timeout/fallback test,
- cost test,
- goldset score.

## Phase 8 — Frontend Integration

Replace mocks in order:

1. Auth/Capabilities
2. Projects/Partners/Application Structure
3. Sources
4. Run status
5. Requirements/OpenIssues
6. Evidence
7. Drafts
8. Review/Recheck/Approval
9. Export
10. Usage/Controls

## Phase 9 — Reference-Case Evaluation

Use the approved, rejected and synthetic/training sample only after governance clearance.

Create:

- field mapping,
- expected structured data,
- expected rule outcomes,
- gold evidence anchors,
- expected open issues/findings,
- quality rubric per field.

Metrics:

- schema validity,
- rule accuracy,
- fact hallucination rate,
- evidence precision/coverage/citation accuracy,
- seeded-error detection,
- portal fit,
- specificity,
- innovation framing,
- market logic,
- workplan feasibility,
- human review time,
- cost and latency.

## Hard Stop Criteria

- Contract validator not green → no agent call.
- Deterministic E2E not green → no frontend live integration.
- Evidence goldset below threshold → no “verified” badge.
- Internal route not institutionally approved → no real internal cloud data.
- Review/Recheck/Approval tests not green → export always ENTWURF.
