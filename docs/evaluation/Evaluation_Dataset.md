# Evaluation Dataset

Deterministic, synthetic/public evaluation dataset for a supervised beta evaluation. Seeded
with:

    cd backend
    DEMO_DATA_ENABLED=true python -m app.demo.seed --reset --evaluation

Plain `python -m app.demo.seed --reset` produces the standard two-project demo **without** any
of the M10 evaluation-only artifacts (proven by `tests/test_m10_eval_seed.py`). All ids are
deterministic (UUIDv5 via `app/demo/dataset.py::stable_id`); reset is scoped to
`DemoSeedManifest`-owned + demo-project-scoped rows.

## Project
**KI-gestützte Entwicklung kreislauffähiger Verbundwerkstoffe (Demo)** —
`circular-composites`, funding instrument
`innosuisse_innovation_project_with_implementation_partner`, budget CHF 620 000. Two partners
(one implementation, one eligible research). Data classification: `public / synthetic`. No
confidential or NDA content.

## Sources
Four synthetic demo sources (Projektüberblick, Arbeitsplan, Markt & Verwertung, Lösung &
Innovation) processed into `SourceFragment`s, plus one **synthetic public market source**
(`type=url`, `origin=public_source`) added by the evaluation enrichment.

## Expected evidence anchors
The deterministic run produces exact-match `EvidenceAnchor`s (all `exact_verified`) linking
source spans to requirements. The evaluation enrichment links one existing verified anchor to
the Solution draft to back a supported claim. (Representative run: **9** verified anchors.)

## Expected draft fields
Template drafts for all portal fields (representative: **8**), including:
- `SOL.INNOVATION_SOLUTION.EDITOR` — a single **supported** technical claim built from a
  verified anchor's content terms (evidence-linked).
- `VC.BUSINESS_TARGETS_MODEL.EDITOR` — a **strong unsupported** market claim (reliability
  blocker) + a hedged/weak claim (warning). No evidence link.
- `INTRO.APP.NAME` / `INTRO.APP.ABSTRACT` — user-edited demo drafts (with evidence links).

## Expected review findings
Deterministic review findings + M9K reliability findings
(`source="agent"`, `profile_id="M9K.reliability_assurance"`), including **≥1 blocker**
(`reliability:unsupported:*` on the strong VC claim) and warnings.

## Expected reliability summary
A `RunQualitySummary` with `quality_flag = risky` (unsupported claims + blocker present).
Representative values: claim_count 10, supported 1, weakly_supported 1, unsupported 2,
blocker_count 2, warning_count 5, evidence_coverage 0.5, evidence_sufficiency_pass_rate 0.5.
Coverage is kept **separate** from sufficiency (high coverage + low sufficiency ⇒ risky).

## Expected export artifacts
All three export types work on the run: **DOCX** (Arbeitsdokument, ENTWURF-marked when not
approval-eligible), **Markdown** (Zusammenfassung), **technical_evidence** (JSON audit export
including the `reliability` block with `claim_hash` metadata only — never `claim_text`).

## Metrics
`python -m app.evaluation` (from `backend/`) writes a deterministic
`var/evaluation/EvaluationRunSummary.{json,md}`. A documented example is
[EvaluationRunSummary.example.md](EvaluationRunSummary.example.md).
