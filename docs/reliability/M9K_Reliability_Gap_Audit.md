# M9K — Reliability Gap Audit (pre-implementation findings)

STEP-1 deliverable. Records what the system can and cannot currently assert about the
*reliability* and *support* of generated proposal text, and the gaps M9K closes. Design
details are in the milestone report and the
[Architecture Assurance Matrix](Architecture_Assurance_Matrix.md).

## Current state (verified in code)

- **Drafts:** `DraftVersion.text` holds the generated field text; `created_by ∈
  agent|user|template` records whether A2 wrote it (via an accepted `DraftSuggestion`).
- **Evidence:** M5 produces `EvidenceAnchor` (exact-verified quote), `EvidenceLink`
  (anchor → requirement_assessment / draft_version), all run-scoped. **`exact_verified` means
  only that the quote exists verbatim in a frozen source — it says nothing about whether that
  quote *supports a specific claim*.**
- **A1 facts:** `ExtractedFact.status ∈ proposed|conflicted|missing|…` — M9B emits
  *proposed* (advisory), never *confirmed*.
- **A3 (M9G):** advisory `ReviewFinding`s (source=`agent`, profile `A3.evidence_consistency`),
  availability-gated, scoped to two editor fields. **A3 silence is not a correctness signal.**
- **Review/approval:** deterministic `ReviewFinding`s + `approval_blockers` gate on empty/
  placeholder/over-limit drafts, stale links, blocker `OpenIssue`s, and `recheck_required`.
  There is **no** check that a *claim* in the draft is actually supported.
- **Market:** `MarketComparisonItem.verified_quote_refs` + `confidence_label` exist, but are
  not connected to draft claims.
- **Export:** `technical-evidence-1` (code-internal snapshot) includes field text, anchors,
  links, findings — but no claim/quality metrics.

## Classified gaps (closed by M9K)

| # | Gap | Description | Closed by |
|---|-----|-------------|-----------|
| 1 | **Unsupported-claim risk** | No representation of the individual claims a draft makes, so nothing detects a claim with no backing. | STEP 2/3 DraftClaim + STEP 5 gate. |
| 2 | **Coverage ≠ correctness** | "An anchor exists on the field" is treated as if the claim is supported. | STEP 4 EvidenceSufficiency (separate from lineage/coverage); `exact_verified` never auto-implies support. |
| 3 | **A1→A2→A3 lineage gap** | No traceable link from a draft claim back to A1 facts / anchors / suggestions / market items. | STEP 3/4 ClaimLineage. |
| 4 | **False-consensus risk** | A2 writes a claim, A3 stays silent → the claim looks validated though nothing supports it. | STEP 6 false-consensus guard (A3 silence ≠ evidence). |
| 5 | **Semantic-drift risk** | Core terms (exact_verified, ReviewApproval, eligibility, public source, Innovation, Value Creation) get reinterpreted incorrectly. | STEP 7 glossary + drift guard. |
| 6 | **Overconfident wording** | Proposed A1 facts stated as certain; superlatives without support. | STEP 3 strength + STEP 5 gate (proposed-as-certain → warning/blocker). |
| 7 | **Uncertainty-marking gap** | Nothing forces a field/run with weak/unsupported claims to needs_review/blocked. | STEP 8 (reuse ReviewFinding/ReviewPackage + scope-bound gate). |
| 8 | **Evaluation-metric gap** | No per-run, reproducible quality metrics for M10. | STEP 10 RunQualitySummary (coverage vs sufficiency kept separate; risky-flag). |

## Scope guardrails (carried into implementation)

- **Code-only beta-internal** — no finalized contract modified. Reliability findings reuse
  `ReviewFinding` (`source="agent"`, `profile_id="M9K.reliability_assurance"`).
- **Deterministic, no provider call** — A3 read only as an already-persisted advisory signal.
- **No mutation** of drafts / Requirements / EvidenceAnchors / Approvals; no auto-approve.
- **Scope-bound gating** — a reliability blocker governs approval only within its current
  `source_scope_hash`; a stale summary surfaces `reliability_stale` and does not block.
- **claim_text** is internal-only (never in audit/logs/export); exports use `claim_hash` +
  status metadata.
- Deterministic checks are framed as an **"evidence sufficiency check"**, never as semantic
  proof or "verified as true".
