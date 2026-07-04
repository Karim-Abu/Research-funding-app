# Evaluation Execution Checklist

Tick-box checklist for running a supervised beta session end to end. Print or copy one per
participant. Companion to the [Supervised_Beta_Demo_Guide.md](Supervised_Beta_Demo_Guide.md),
[Evaluation_Session_Protocol.md](Evaluation_Session_Protocol.md) and
[User_Evaluation_Questionnaire.md](User_Evaluation_Questionnaire.md).

**Participant-ID (pseudonym):** ____________  **Date:** ____________  **Facilitator:** ____________

---

## A. Readiness gate (once per campaign)

- [ ] `.\scripts\verify_all.ps1` ends **ALL GREEN** on the evaluated build.
- [ ] Audit findings **F1 and F3 remediated** (see the "M10.1 remediation status" note in
      [Post_M10_Code_Risk_Audit.md](../audits/Post_M10_Code_Risk_Audit.md)).
- [ ] Provider mode is **deterministic / fake** — no `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` /
      `FIRECRAWL_API_KEY`, and `D2_WEB_RESEARCH_ENABLED` is **not** set.

## B. Clean Evaluation Environment (before each participant)

> Do **not** run on a polluted development database. Do **not** delete test projects one by one
> through the UI. `app.demo.seed --reset` only clears manifest-owned demo rows, so it will not
> remove stray E2E/test projects — use a **dedicated clean DB** instead.

- [ ] Dedicated DB set: `DATABASE_URL = "sqlite:///./var/evaluation_beta.db"`.
- [ ] `backend/var/` ensured to exist (`New-Item -ItemType Directory -Force .\var`).
- [ ] Fresh file (`Remove-Item .\var\evaluation_beta.db -ErrorAction SilentlyContinue`) — or a
      clean re-seed on the existing dedicated DB.
- [ ] Migrations applied: `python -m alembic -c alembic.ini upgrade head`.
- [ ] Identities seeded: `python -m app.seed`.
- [ ] Evaluation dataset seeded: `python -m app.demo.seed --reset --evaluation`.
- [ ] Backend started with the dedicated `DATABASE_URL`; frontend started in live mode with the
      **same** `DATABASE_URL`.
- [ ] **Dashboard shows ONLY the two demo projects** (A – Verbundwerkstoffe, B –
      Zustandsüberwachung).
- [ ] **If any old E2E/test project is visible → STOP, reset the environment, re-verify.**

Exact commands: §1 of the [Supervised_Beta_Demo_Guide.md](Supervised_Beta_Demo_Guide.md).

## C. Consent & disclosure (start of session)

- [ ] Consent + background recorded (Questionnaire §A).
- [ ] Evaluator confirmed: synthetic/public data only, **no real confidential content**.
- [ ] **Limitations disclosure read aloud** (Session Protocol §2) — before any task.
- [ ] Credentials verified working: Anna `anna.keller@example.test` / `changeme-dev-lead`
      (and Tobias `tobias.frei@example.test` / `changeme-dev-member` if a second role is used).

## D. During the session

- [ ] (Optional) Manual baseline captured first in
      [Baseline_Comparison_Template.md](Baseline_Comparison_Template.md).
- [ ] Project A: Editor → Review Center (recheck / field approval / stale) demonstrated.
- [ ] Project A: Reliability Quality Summary opened — `quality_flag = risky`,
      **coverage vs sufficiency** discussed; blocker agreement/disagreement recorded.
- [ ] Project A: staleness gate (M10.1) shown — "Qualitätsprüfung veraltet" + approval blocked
      until a fresh pass.
- [ ] Project A: DOCX + Markdown + technical_evidence exports created.
- [ ] Project B: eligibility-blocked path shown.
- [ ] Per-task ratings recorded (Questionnaire §B); facilitator stayed neutral (no leading).

## E. Metrics & findings capture (before re-seeding)

- [ ] `python -m app.evaluation` run; `EvaluationRunSummary.{json,md}` **archived** to the
      participant folder (interpret honestly: coverage ≠ sufficiency; cost is a placeholder).
- [ ] Questionnaire §C–§G completed by the evaluator.
- [ ] Baseline template summary rows filled by the facilitator.
- [ ] Free-text findings logged (wrong/weak outputs, reliability agreement, usability friction,
      privacy observations).

## F. Reset & close

- [ ] Dataset restored for the next participant: `python -m app.demo.seed --reset --evaluation`
      (same DB); dashboard re-verified to show only the two demo projects.
- [ ] No real keys or confidential data were used at any point.
- [ ] **Nothing committed automatically** — session data and `evaluation_beta.db` stay out of
      the repository; any doc/data commit is reviewed manually first.

---

> After the campaign, consolidate results per the
> [Thesis_Evaluation_Mapping.md](Thesis_Evaluation_Mapping.md). Report only real, observed
> data — no fabricated numbers.
