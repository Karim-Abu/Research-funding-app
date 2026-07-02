# Thesis Evaluation Mapping

Maps the supervised beta evaluation to the thesis argument: for each research question, which
**subjective** instrument item, which **objective** `EvaluationRunSummary` metric, and which
**timed** baseline measure provide evidence — plus the honesty guardrails that keep the
interpretation defensible. Data sources:
[User_Evaluation_Questionnaire.md](User_Evaluation_Questionnaire.md),
[Baseline_Comparison_Template.md](Baseline_Comparison_Template.md),
[EvaluationRunSummary.example.md](EvaluationRunSummary.example.md).

> This file contains **no results** — it is the analysis scaffold. Fill it only with real,
> observed data from actual sessions. **Do not fabricate numbers.**

---

## Research questions (adjust the wording to the thesis)

- **RQ1 — Value:** Does evidence-based, agent + deterministic support help a user produce a
  *better-grounded* Innosuisse innovation-project proposal than manual preparation?
- **RQ2 — Trust / traceability:** Can users trace outputs to their evidence and calibrate trust
  (agree with correct flags, distrust weak claims)?
- **RQ3 — Reliability safety:** Does the reliability layer surface unsupported/weak claims and
  prevent a run from *appearing* checked when it is not (staleness gate)?
- **RQ4 — Efficiency / review effort:** Does support reduce (not inflate) the effort to reach a
  reviewable draft?
- **RQ5 — Privacy / data handling:** Do users understand the data boundaries, and do the
  controls behave as documented?
- **RQ6 — Usability:** Is the supervised workflow understandable without technical jargon?

---

## Mapping table

| RQ | Subjective (Questionnaire) | Objective (EvaluationRunSummary) | Timed (Baseline template) | Honest interpretation |
|----|----------------------------|----------------------------------|---------------------------|-----------------------|
| RQ1 Value | B1, C1–C4, F4 | `supported_claims`, `evidence_coverage`, `review_finding_count` | Requirements identified; Missing/incorrect requirements | Coverage is *linkage*, not correctness. More findings ≠ better unless they are valid (cross-check F1/F2). |
| RQ2 Trust | B2, B3, D5, F2, F3 | `exact_verified_anchor_count`, `reliability_quality_flag` | Trust/traceability rating; "trust the audit export?" | Agreement with a **correct** blocker is the positive signal; agreeing with a wrong flag is a miscalibration, not success. |
| RQ3 Reliability safety | B3, F1, F2 | `blocker_count`, `unsupported_claims`, `weakly_supported_claims`, **`evidence_sufficiency_pass_rate`**, `reliability_quality_flag` | "Key risks surfaced by the reliability layer" | Expected `quality_flag = risky` on Project A. Demonstrate the **staleness gate** (M10.1 F3): after edit+recheck, approval blocked + "veraltet" banner until a fresh pass. |
| RQ4 Efficiency | B4, C1, C4 | (context: `draft_field_count`, `requirement_count`) | Time to first complete draft (manual vs assisted); Perceived review effort | Time deltas are indicative only (2–4 participants, synthetic dataset) — report as qualitative trend, not a benchmark. |
| RQ5 Privacy | E1, E2 | `web_research_used` (false), `market_comparison_used`, `provider_mode` | Privacy/data-handling observations | Deterministic sanitization is **risk reduction, not a secrecy guarantee**; D2 live stays default-off ([Search_Query_Firewall.md](../security/Search_Query_Firewall.md)). Do not overclaim privacy. |
| RQ6 Usability | B5, D1–D4 | — | Usability friction notes | Short usability set (SUS-style) — indicative, small-n. |

---

## Objective anchors from `EvaluationRunSummary`

The deterministic run on Project A yields a stable metric set (schema
`evaluation-run-summary-1`). Representative reference values (from
[EvaluationRunSummary.example.md](EvaluationRunSummary.example.md) — **example, not a result**):
`source_count 5 · requirement_count 11 · draft_field_count 8 · exact_verified_anchor_count 9 ·
reliability_claim_count 10 · supported 1 · weakly 1 · unsupported 2 · blocker_count 2 ·
warning_count 5 · evidence_coverage 0.5 · evidence_sufficiency_pass_rate 0.5 ·
reliability_quality_flag risky · estimated_cost placeholder`.

Because the dataset is deterministic, these are **comparable across participants** and separate
the *system's* output from the *user's* judgement of it.

---

## Honesty guardrails (must appear in the thesis write-up)

1. **Coverage ≠ sufficiency.** `evidence_coverage` counts claims with *any* linked evidence;
   `evidence_sufficiency_pass_rate` counts claims the evidence *appears to support under defined
   criteria*. High coverage + low sufficiency is a **risk signal, not success**.
2. **Deterministic sufficiency is a conservative heuristic**, not a factual-correctness proof
   ("appears to support under defined criteria"). No claim of guaranteed correctness.
3. **Supervised-beta scope.** Small n (2–4), synthetic/public dataset, deterministic/fake
   providers, no real portal submission. Results are formative, not a production benchmark.
4. **Audit status.** The build carries a **CONDITIONAL PASS**
   ([Post_M10_Code_Risk_Audit.md](../audits/Post_M10_Code_Risk_Audit.md)) with the two High
   findings **F1 (no-raw-log provider-path coverage)** and **F3 (reliability staleness gate)**
   remediated in [Milestone_10_1_Audit_Remediation_Report.md](../milestones/Milestone_10_1_Audit_Remediation_Report.md).
   State this scope honestly; do not present the tool as production-ready.
5. **No fabricated numbers.** Every table cell is either a real observation or left blank.
   `estimated_cost` is always a placeholder — never invent CHF.
6. **Not covered by this evaluation:** NDA/D3 handling, SNF/Horizon, automatic funding
   decisions/submission, production Azure — all out of scope
   ([Known_Limitations.md](Known_Limitations.md)).

---

## From sessions to findings

1. Per participant: archive `EvaluationRunSummary.json`, the completed questionnaire, and the
   baseline sheet.
2. Aggregate subjective items (median/range, not fabricated means over tiny n) and pair each RQ
   with its objective anchor.
3. Report agreements **and** disagreements with reliability findings — disagreement on a *valid*
   flag is itself a finding about calibration/UX.
4. Feed usability/privacy friction into the post-beta backlog (see the M10/M10.1 reports).
