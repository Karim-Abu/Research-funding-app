# Supervised Beta Demo Guide

Operator guide for running a **supervised beta evaluation** of the evidence-based
proposal-support system on the deterministic evaluation dataset. It tells the facilitator how
to prepare a clean environment, which user flow to demonstrate, and what NOT to do. It is the
setup companion to the [Evaluation_Session_Protocol.md](Evaluation_Session_Protocol.md)
(facilitator script), the [User_Evaluation_Questionnaire.md](User_Evaluation_Questionnaire.md)
(evaluator instrument) and the [Evaluation_Execution_Checklist.md](Evaluation_Execution_Checklist.md).

**Scope reminder.** This is a **supervised beta**. The system *supports* proposal preparation;
it never decides, submits or guarantees anything. Every generated claim requires human review.
See [Known_Limitations.md](Known_Limitations.md) and the readiness verdict in
[Milestone_10_1_Audit_Remediation_Report.md](../milestones/Milestone_10_1_Audit_Remediation_Report.md).

---

## 0. Readiness gate (do this once before a campaign)

1. Confirm the code is on the evaluated build and the full suite is green:
   ```powershell
   .\scripts\verify_all.ps1   # must end "ALL GREEN"
   ```
2. Confirm the two evaluation-gating audit findings are closed (F1, F3) — see the
   [Post_M10_Code_Risk_Audit.md](../audits/Post_M10_Code_Risk_Audit.md) "M10.1 remediation
   status" section. Only start evaluations on a build where these are remediated.
3. Provider mode for the whole evaluation is **deterministic / fake — no real provider key**.
   Do not set `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `FIRECRAWL_API_KEY`; do not enable
   `D2_WEB_RESEARCH_ENABLED`. See [Provider_Mode_Matrix.md](Provider_Mode_Matrix.md).

---

## 1. Clean Evaluation Environment (required)

**Never run the supervised evaluation on a polluted development database.** A shared dev DB
usually contains hundreds of throwaway E2E/test projects; a participant who sees them cannot
find the intended demo projects and the session data is contaminated.

- **Do not** delete those projects one by one through the UI.
- `python -m app.demo.seed --reset` only removes **manifest-owned demo rows** (see
  [Demo_Walkthrough.md](../demo/Demo_Walkthrough.md), proven by
  `backend/tests/test_m10_eval_seed.py`). It will **not** clean stray E2E/test projects.
  Therefore the correct approach is a **dedicated, clean evaluation database**
  (`evaluation_beta.db`) — not deletion.

Build the clean environment on Windows PowerShell:

```powershell
# 1) One-time / per-campaign: build a dedicated, clean evaluation DB
cd backend
$env:APP_ENV = "development"
$env:DEMO_DATA_ENABLED = "true"
$env:DATABASE_URL = "sqlite:///./var/evaluation_beta.db"
New-Item -ItemType Directory -Force .\var | Out-Null                 # ensure backend/var/ exists (SQLite fails otherwise)
Remove-Item .\var\evaluation_beta.db -ErrorAction SilentlyContinue   # start from a clean file
python -m alembic -c alembic.ini upgrade head                        # migrations on THIS db
python -m app.seed                                                   # workspace + funding profile + the 2 users
python -m app.demo.seed --reset --evaluation                        # deterministic evaluation dataset

# 2) Start backend (terminal 1, from backend/) with the SAME DATABASE_URL
$env:DATABASE_URL = "sqlite:///./var/evaluation_beta.db"; $env:APP_ENV = "development"; $env:DEMO_DATA_ENABLED = "true"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3) Start frontend (terminal 2, from repo root) in live mode
$env:APP_BACKEND_MODE = "live"; $env:FASTAPI_BRIDGE_URL = "http://127.0.0.1:8000/api/v1"
corepack pnpm build; node node_modules/next/dist/bin/next start --port 3000   # or: corepack pnpm dev

# 4) Verify at http://localhost:3000 — the dashboard shows ONLY the two demo projects.
```

**Backend and frontend must use the SAME `DATABASE_URL`.** If they diverge, the UI shows a
different database than the one you seeded.

**Verification gate:** after login the dashboard must show **only the two intended demo
projects** (below). **If any old E2E/test project is visible, STOP the session** — the server
is on a different or polluted DB. Re-do step 1 with the dedicated `evaluation_beta.db` and
restart both processes.

**Between participants:** restore the pristine dataset on the same DB with
`python -m app.demo.seed --reset --evaluation`, then continue. Export and archive the metrics
first (see §5).

---

## 2. Login accounts (dev seed)

From `backend/app/config/settings.py` / `app/seed.py`, workspace `ws-demo`:

| Role | Name | E-Mail | Password |
|------|------|--------|----------|
| Lead / Admin | Anna Keller | `anna.keller@example.test` | `changeme-dev-lead` |
| Member | Tobias Frei | `tobias.frei@example.test` | `changeme-dev-member` |

These are the only login identities (no self-sign-up). Use **Anna** for the guided walkthrough;
Tobias is available if the session needs a second (member-role) perspective.

---

## 3. The two evaluation projects

After `--reset --evaluation` the dashboard shows exactly two demo projects (both badged
`Demo`, both `public / synthetic` — no confidential or NDA content):

- **Project A — "KI-gestützte Entwicklung kreislauffähiger Verbundwerkstoffe (Demo)"**
  (`circular-composites`, budget CHF 620 000, one implementation + one eligible research
  partner). Carries the evaluation reliability surface: a **strong unsupported** market claim
  in the Value-Creation draft (reliability blocker) plus a supported technical claim in the
  Solution draft. Expected `quality_flag = risky`.
- **Project B — "Zustandsüberwachung für Produktionsanlagen (Demo)"** — deliberately missing an
  eligible research partner, so it stays **blocked** in requirements and review.

Details: [Evaluation_Dataset.md](Evaluation_Dataset.md).

---

## 4. The user flow to demonstrate

Keep the facilitator neutral (no leading). The ordered task list and timing live in
[Evaluation_Session_Protocol.md](Evaluation_Session_Protocol.md); this is the operator's
reference for *what each screen should show*.

### Project A — evidence, review, reliability, export
1. **Login → Dashboard.** Confirm only the two demo projects appear.
2. **Open Project A → Editor.** Persisted template drafts load; several draft versions come
   from real user edits; active evidence links point to current draft versions.
3. **Review Center (Qualitätsprüfung).** Show the deterministic findings. Edit a supported
   field to be placeholder-free → `recheck_required = true`; run "Erneut prüfen" → it clears;
   approve the cleaned field (field scope succeeds); a further edit invalidates the approval
   (**stale**). The full **run** approval stays **blocked** while placeholders / the
   Value-Creation blocker remain.
4. **Reliability Quality Summary.** Open it and read the numbers with the evaluator:
   `quality_flag = risky`, and **evidence_coverage vs evidence_sufficiency_pass_rate** — high
   coverage with low sufficiency is a **risk signal, not success**. Show that the strong
   unsupported claim produced a **blocker** reliability finding.
   - **Staleness demo (M10.1, F3):** after a draft edit + recheck, the Review Center shows
     "Qualitätsprüfung veraltet — bitte erneut ausführen." and approval is blocked until a
     fresh reliability pass runs. This is the reliability gate working as intended.
5. **Exports.** Create all three: **DOCX** (Arbeitsdokument, ENTWURF-marked when not
   approval-eligible), **Markdown** (Zusammenfassung), **technical_evidence** (JSON audit
   export — carries the reliability summary with `claim_hash` metadata only, **never**
   `claim_text` / prompts / raw queries / secrets).
6. **Innolink copy** (optional): the copy-only assistant — see
   [Innolink_Copy_Paste_Guide.md](../demo/Innolink_Copy_Paste_Guide.md). It never writes to the
   Innosuisse portal.

### Project B — the blocked path
7. **Open Project B → Requirements.** The missing eligible research partner produces a
   blocking OpenIssue from the rule engine; the Review Center stays **blocked**. This shows the
   system refusing to present a non-eligible application as ready.

---

## 5. Per-participant metrics

For each participant's run, export the deterministic metrics and archive them **before**
re-seeding:

```powershell
cd backend
$env:DATABASE_URL = "sqlite:///./var/evaluation_beta.db"; $env:APP_ENV = "development"
python -m app.evaluation   # writes var/evaluation/EvaluationRunSummary.{json,md}
```

Copy `backend/var/evaluation/EvaluationRunSummary.json` into the participant's result folder.
The metric schema and an example are in
[EvaluationRunSummary.example.md](EvaluationRunSummary.example.md). Interpret it honestly:
**coverage ≠ sufficiency**, and `estimated_cost` is an explicit placeholder — never invent CHF.
Record the manual-vs-assisted measures in
[Baseline_Comparison_Template.md](Baseline_Comparison_Template.md) and the evaluator's ratings
in [User_Evaluation_Questionnaire.md](User_Evaluation_Questionnaire.md).

---

## 6. Limitations to disclose before the session

Read the disclosure block in
[Evaluation_Session_Protocol.md](Evaluation_Session_Protocol.md) **before any task**. Summary
(full text in [Known_Limitations.md](Known_Limitations.md)):

- No automatic funding decision or funding-probability; no automatic Innolink / portal
  submission; no automatic approval (human-gated).
- No NDA (D3) processing — the evaluation dataset is public/synthetic only.
- No guarantee of factual correctness without human review; deterministic evidence sufficiency
  is a **conservative heuristic** ("appears to support under defined criteria"), not proof.
- Deterministic query sanitization is **risk reduction, not a secrecy guarantee**; D2
  live-provider research stays **default-off** and needs governance approval
  ([Search_Query_Firewall.md](../security/Search_Query_Firewall.md)).
- Market comparison uses only imported public sources.
- Azure is **documented target architecture, not deployed** — no production compliance claimed.
- SNF / Horizon instruments not implemented; structured repeated portal fields (work packages,
  milestones, full budget tables) not fully covered.

---

## 7. What NOT to do

- Do **not** use real provider keys or enable live web research (`D2_WEB_RESEARCH_ENABLED`).
- Do **not** enter real confidential or NDA content — the dataset and session are
  public/synthetic only.
- Do **not** run on a shared/polluted dev DB (see §1).
- Do **not** present any output as an approval, submission, or funding prediction.
- Do **not** commit session data or the `evaluation_beta.db` to the repository.
