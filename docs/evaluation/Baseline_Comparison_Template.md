# Baseline Comparison Template

A manual evaluation template for a supervised comparison of **manual** proposal preparation
vs **system-assisted** preparation, with 2–4 participants on the synthetic evaluation dataset.
This is a **template only** — it contains no results. Do not fill in fabricated numbers; only
record real observations from an actual evaluation session.

## Session metadata
| Field | Value |
|-------|-------|
| Date | |
| Participants (2–4, roles) | |
| Dataset | Evaluation dataset (`--reset --evaluation`) |
| Provider mode | deterministic_only / fake |
| Facilitator | |

## Per-participant measures
| Measure | Manual | System-assisted | Notes |
|---------|--------|-----------------|-------|
| Time to first complete draft (min) | | | |
| Number of sources reviewed | | | |
| Requirements identified | | | |
| Missing / incorrect requirements | | | |
| Evidence coverage (subjective) | | | |
| Evidence sufficiency rating (1–5) | | | |
| Usefulness rating (1–5) | | | |
| Trust / traceability rating (1–5) | | | |
| Perceived review effort (low/med/high) | | | |

## Qualitative notes
- **Wrong or weak outputs observed** (claim, why): 
- **Reliability findings — agreed / disagreed**: 
- **Privacy / data-handling observations**: 
- **Usability friction**: 
- **Would you trust the technical-evidence export for an audit? Why/why not**: 

## Facilitator summary
- Net time delta (manual − assisted): 
- Requirement-coverage delta: 
- Key risks surfaced by the reliability layer: 
- Overall readiness impression (1–5) + rationale: 

> Interpret ratings alongside the run's `EvaluationRunSummary`: high evidence_coverage with
> low sufficiency is a **risk signal**, not success.
