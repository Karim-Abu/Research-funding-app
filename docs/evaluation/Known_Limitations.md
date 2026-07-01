# Known Limitations (Beta)

The system is a supervised, evidence-based **support** tool. It does not decide, submit, or
guarantee anything. Known limitations at the M10 feature freeze:

- **No automatic funding decision.** The system never predicts funding probability or
  eligibility outcomes; it surfaces deterministic checks + human-review findings only.
- **No automatic Innolink / portal submission.** The Innolink assistant is copy-only; no
  automation writes to the Innosuisse portal.
- **No automatic application approval.** Approval is a deliberate human action gated by
  deterministic + reliability blockers.
- **No real NDA (D3) processing.** D3 is blocked from all external tools in the MVP.
- **No guarantee of factual correctness without human review.** Generated drafts are
  advisory; every claim requires human verification.
- **Deterministic evidence sufficiency is conservative and heuristic.** The M9K sufficiency
  check uses lexical/quantitative criteria — it is an "appears to support under defined
  criteria" signal, not semantic proof; it errs toward *needs review* / *block*.
- **Market comparison uses only imported public sources** (no confidential/internal inputs).
- **Azure production path is documented, not deployed.** No production Azure compliance is
  claimed; productive confidential cloud use requires a DPA + FHNW data-protection review.
- **SNF / Horizon are not implemented.** Only the Innosuisse innovation-project instrument is
  supported.
- **Structured repeated portal fields are not fully covered** — work packages, milestones and
  full budget tables are out of scope for the beta drafting/evidence surface.
- **Real Firecrawl is optional and env-gated.** All mandatory tests use the deterministic fake
  provider.
- **Real provider smoke is optional and env-gated** (`RUN_REAL_PROVIDER_SMOKE`); never required
  for verification.
- **No provider vector stores for confidential data.** Stateful provider features are not used
  for D1/D2/D3.

See also [M10_Feature_Freeze_Audit.md](M10_Feature_Freeze_Audit.md) and
[Provider_Mode_Matrix.md](Provider_Mode_Matrix.md).
