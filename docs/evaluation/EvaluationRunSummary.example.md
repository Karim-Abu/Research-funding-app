# EvaluationRunSummary — Example

Documented **example** of the deterministic evaluation metrics export (schema
`evaluation-run-summary-1`). Generated from the evaluation dataset
(`python -m app.demo.seed --reset --evaluation` then `python -m app.evaluation`). Real
per-run output is written to the git-ignored `backend/var/evaluation/` — this file is a
committed template with a fixed placeholder timestamp so it does not create noisy diffs.

*Generated (placeholder):* `2026-07-02T00:00:00+00:00`

| Metric | Example value |
| --- | --- |
| run_id | `<deterministic run id>` |
| dataset_id | `<demo project id>` |
| provider_mode | deterministic_only |
| fake_provider_used | false |
| web_research_used | false |
| market_comparison_used | true |
| source_count | 5 |
| requirement_count | 11 |
| draft_field_count | 8 |
| evidence_anchor_count | 9 |
| exact_verified_anchor_count | 9 |
| review_finding_count | 22 |
| export_artifacts_created | 0 (before exports) |
| reliability_claim_count | 10 |
| supported_claims | 1 |
| weakly_supported_claims | 1 |
| unsupported_claims | 2 |
| conflicting_claims | 0 |
| **evidence_coverage** | 0.5 |
| **evidence_sufficiency_pass_rate** | 0.5 |
| blocker_count | 2 |
| warning_count | 5 |
| reliability_quality_flag | risky |
| total_runtime_seconds | null |
| estimated_cost | placeholder (no CHF invented) |

> **Coverage ≠ sufficiency.** `evidence_coverage` counts claims with *any* linked evidence;
> `evidence_sufficiency_pass_rate` counts claims the evidence *appears to support under the
> defined criteria*. High coverage with low sufficiency is **risky**, not success. Costs are
> never invented — `estimated_cost` is an explicit placeholder.
