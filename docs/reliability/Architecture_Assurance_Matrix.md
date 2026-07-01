# Architecture Assurance Matrix (Milestone 9K)

Each system-level risk mapped to the component that owns it, the control that mitigates it,
the test that proves the control, and the evidence artifact a reviewer can inspect. All M9K
additions are deterministic and beta-internal; no finalized contract is modified.

| # | Risk | Component | Control | Test | Evidence artifact |
|---|------|-----------|---------|------|-------------------|
| 1 | **Prompt Injection** | ModelGateway / agent profiles (`app/agents/`) | `CTRL.PROMPT_INJECTION` + `CTRL.SOURCE_TRUST`; untrusted source text marked; tools allow-listed | agent gateway tests | `ControlResult(CTRL.PROMPT_INJECTION)`, `AgentInvocation` |
| 2 | **Idea Leakage** | Search Query Firewall (`app/security/`) | D0–D3 classes + firewall sanitize/approve; raw D1/D2 never sent/stored (M9J) | `test_privacy_firewall.py`, `e2e/privacy-firewall.spec.ts` | `SearchQueryApproval` (hash-only), `CTRL.QUERY_FIREWALL` |
| 3 | **False Citation** | Deterministic evidence (M5) + M9K sufficiency | Exact-quote anchor verification; **sufficiency ≠ presence**; `exact_verified` never auto-implies support | `test_reliability_pass.py::test_wrong_evidence_quote_does_not_support` | `ClaimLineage.sufficiency_status`, `EvidenceAnchor` |
| 4 | **Unsupported Claim** | M9K gate (`app/reliability/gate.py`) | Strong+no_evidence → scope-bound blocker; weak → needs_review | `test_strong_unsupported_claim_blocks_approval`, `test_unsupported_market_claim` | `ReviewFinding(reliability:unsupported:*)`, `RunQualitySummary.unsupported_claims` |
| 5 | **Evidence Incorrectness** | M9K sufficiency (`app/reliability/sufficiency.py`) | Key-term + type-term + number-match checks under defined criteria | `test_generic_evidence_weakly_supports`, `test_quantified_claim_missing_number` | `ClaimLineage`, `RunQualitySummary.evidence_correctness_sample_pass_rate` |
| 6 | **Semantic Drift** | M9K drift guard (`app/reliability/{glossary,drift}.py`) | Versioned glossary + co-occurrence patterns (exact_verified=approved, eligibility=decision, …) | `test_semantic_drift_detected` | `ReviewFinding(reliability:drift:*)`, `RunQualitySummary.semantic_drift_count` |
| 7 | **False Consensus** | M9K false-consensus guard (`app/reliability/false_consensus.py`) | A2 claim + A3 silent + insufficient evidence → risk finding; A3 silence ≠ evidence | `test_false_consensus_when_a3_silent`, `test_a3_finding_prevents_false_consensus_but_not_missing_evidence` | `ReviewFinding(reliability:false_consensus:*)` |
| 8 | **Raw Log Leakage** | No-raw-logging guard (`app/security/redaction.py`) + M9K | Hashes/metadata only; `claim_text` never audited/logged/exported; leakage scan | `test_no_claim_text_in_audit`, `RunQualitySummary.raw_logging_detected` | `AuditEvent.detail` (metadata), `RunQualitySummary` |
| 9 | **Overreliance** | Review layer + M9K uncertainty marking | Everything advisory + human-review-required; risky-flag; no auto-approve/rewrite | `test_idempotent_and_no_draft_mutation` | `RunQualitySummary.quality_flag`, `ReviewFinding` (advisory) |
| 10 | **Cost Explosion** | CostGuard (`app/agents/cost_guard.py`) | Per-run/task budget caps; M9K makes **no** provider call | agent cost-guard tests | `UsageRecord`, `ControlResult(CTRL.COST_GUARD)` |
| 11 | **Portal Mismatch** | Portal field profile + review checks (M6/M7) | Field-id/char-limit/placeholder checks; export copy-only | `review` + `export` tests | `ReviewFinding(draft_*)`, technical export `fields` |
| 12 | **Stale Rules** | Registry snapshot (`RunProjectSnapshot`, `snapshot_versions`) | Frozen registry versions per run; staleness on drift | recheck/staleness tests | `config_versions` in export, `RunQualitySummary.source_scope_hash` |
| 13 | **Provider Unavailability** | ModelGateway + M9K design | Fail-closed; A3 skipped when unavailable; **M9K is deterministic (no provider)** | `deterministic recheck does not run A3` (e2e), `test_reliability_pass` (no provider) | `AgentInvocation` (absent for M9K), `RunQualitySummary` |
| 14 | **Workspace Isolation** | Repositories (workspace-scoped) | Every read/write scoped to `workspace_id`; cross-workspace → 403/404 | `test_reliability_endpoint_and_isolation` | 404 response, run/claim `workspace_id` |
| 15 | **Export Data Leakage** | Technical-evidence export (`app/exports/`) | No raw prompts/provider payloads/D1-D2 queries/secrets; M9K uses `claim_hash` + status only | `test_export_block_has_summary_without_claim_text`, `e2e/reliability.spec.ts` | technical-evidence JSON `reliability` block |

## Notes
- Reliability findings are persisted as `ReviewFinding(source="agent",
  profile_id="M9K.reliability_assurance")` — the M9J/M9I code-only pattern (no new source
  enum, no migration for findings, no finalized-contract change).
- Reliability blockers govern approval only within their current `source_scope_hash`; a
  stale summary surfaces `reliability_stale` and does not block (see the report).
