# Evaluation Session Protocol

Facilitator script for **one** supervised beta session (~60 minutes, one evaluator). It keeps
sessions comparable and neutral. Pair it with the
[Supervised_Beta_Demo_Guide.md](Supervised_Beta_Demo_Guide.md) (environment + flow),
the [Evaluation_Execution_Checklist.md](Evaluation_Execution_Checklist.md) (tick boxes),
the [User_Evaluation_Questionnaire.md](User_Evaluation_Questionnaire.md) (evaluator ratings) and
the [Baseline_Comparison_Template.md](Baseline_Comparison_Template.md) (timed measures).

**Golden rules for the facilitator**
- Stay **neutral** — no leading ("Sehen Sie, wie hilfreich das ist?" is forbidden). Ask open
  questions; let the evaluator think aloud.
- Record **only real observations**. Never fill any field with an assumed or "expected" value.
- The system is a **support tool** — never describe an output as an approval, a submission, or
  a funding prediction.

---

## 0. Pre-session — Clean Evaluation Environment (do before the evaluator arrives)

Follow §1 of the [Supervised_Beta_Demo_Guide.md](Supervised_Beta_Demo_Guide.md):

1. Build / restore the dedicated clean DB (`evaluation_beta.db`), run migrations,
   `python -m app.seed`, then `python -m app.demo.seed --reset --evaluation`.
2. Start backend and frontend with the **same** `DATABASE_URL`; provider mode
   **deterministic/fake, no real key**.
3. **Gate:** log in as Anna and confirm the dashboard shows **only the two demo projects**
   (Project A – Verbundwerkstoffe, Project B – Zustandsüberwachung).
   **If any old E2E/test project is visible → STOP and reset the environment** before the
   evaluator arrives. Do not run the session on a polluted database, and do not delete stray
   projects through the UI.
4. `verify_all.ps1` is green on this build; F1/F3 remediated (audit gate met).

---

## 1. Welcome & consent (≈5 min)

- Explain purpose: gather honest feedback on an **evidence-based support** tool for Innosuisse
  innovation-project proposals; there are **no right answers** and the *system*, not the
  evaluator, is under test.
- Collect consent + background in [User_Evaluation_Questionnaire.md](User_Evaluation_Questionnaire.md)
  §A. Confirm the evaluator understands **only synthetic/public demo data** is used and they
  will **not** enter real confidential content.

---

## 2. Limitations disclosure — READ ALOUD before any task (≈3 min)

> "Bevor wir starten, ist wichtig, was dieses System **nicht** tut:
> - Es trifft **keine** Förderentscheidung und schätzt **keine** Förderwahrscheinlichkeit.
> - Es reicht **nichts** automatisch bei Innosuisse/Innolink ein und gibt **nichts**
>   automatisch frei — jede Freigabe ist eine bewusste menschliche Handlung.
> - Es verarbeitet **keine** NDA-/D3-Inhalte; die Demodaten sind rein synthetisch/öffentlich.
> - Es **garantiert keine sachliche Richtigkeit** ohne menschliche Prüfung. Die
>   Beleg-Suffizienzprüfung ist eine **konservative Heuristik** ('scheint unter definierten
>   Kriterien zu stützen'), kein Beweis.
> - Die deterministische Bereinigung von Suchanfragen ist **Risikoreduktion, keine
>   Geheimhaltungsgarantie**; Live-Websuche für vertrauliche Projekte ist standardmäßig **aus**.
> - Der Marktvergleich nutzt nur importierte öffentliche Quellen.
> - Der Azure-Betrieb ist **dokumentiert, aber nicht produktiv ausgerollt** — keine
>   Produktions-Compliance.
> - SNF/Horizon sind nicht implementiert; wiederkehrende strukturierte Portalfelder
>   (Arbeitspakete, Meilensteine, vollständige Budgettabellen) sind noch nicht vollständig
>   abgedeckt."

Full text: [Known_Limitations.md](Known_Limitations.md). Tick the disclosure box in the
checklist.

---

## 3. Optional manual baseline (≈10 min, only if the design includes it)

If this participant is doing the manual-vs-assisted comparison, run the **manual** condition
first (no system): ask them to sketch, on Project A's brief, which requirements and evidence
they would look for. Record timing/coverage in
[Baseline_Comparison_Template.md](Baseline_Comparison_Template.md). Keep it short; the goal is a
reference point, not a full manual proposal.

---

## 4. Guided tasks — system-assisted (≈30 min)

Mirror the flow in the Demo Guide §4. For each task: state the task neutrally, let the evaluator
act and think aloud, observe, then record the per-task ratings (Questionnaire §B).

1. **Login & Dashboard** — evaluator logs in as Anna; confirm the two demo projects.
2. **Project A · Editor** — open the draft; note first reactions to the drafted fields and
   evidence links. *Observe:* do they look for the source behind a statement?
3. **Project A · Review Center** — read the deterministic findings; edit a field to remove a
   placeholder → observe `recheck_required`; run "Erneut prüfen"; approve the cleaned field;
   edit again → approval goes **stale**. *Observe:* do they understand why the run stays
   blocked?
4. **Project A · Reliability Quality Summary** — open it; walk through `quality_flag = risky`
   and **coverage vs sufficiency**. *Observe (key trust probe):* do they agree with the
   **blocker** on the strong unsupported claim? Record agreement/disagreement (Questionnaire
   §F2).
   - **Staleness probe (M10.1):** after a further edit + recheck, the Review Center shows
     "Qualitätsprüfung veraltet — bitte erneut ausführen." and approval is blocked until a
     fresh reliability pass. *Observe:* is the message clear? Do they run a fresh pass?
5. **Project A · Exports** — create DOCX, Markdown and technical_evidence. Ask Questionnaire
   §F3 (would you trust the technical export for an audit?).
6. **Project B · Requirements/Review** — open Project B; the missing eligible research partner
   keeps it **blocked**. *Observe:* do they see the system correctly refusing to present a
   non-eligible application as ready?

*(Optional, if time and capability enabled: the fake-provider public web research / market
comparison — deterministic, no real key. Skip if running behind.)*

---

## 5. Wrap-up (≈10 min)

- Evaluator completes Questionnaire §C–§G.
- Facilitator export + archive the metrics for this run **before re-seeding**:
  `python -m app.evaluation` → copy `EvaluationRunSummary.json` into the participant folder.
- Facilitator fills the summary rows in
  [Baseline_Comparison_Template.md](Baseline_Comparison_Template.md).

---

## 6. Reset for the next participant

- Restore the pristine dataset on the same DB: `python -m app.demo.seed --reset --evaluation`.
- Re-confirm the dashboard shows only the two demo projects.
- Do **not** commit session data or `evaluation_beta.db`.

---

## 7. Observation cues (where the signal is)

| Where | What to watch for |
|-------|-------------------|
| Editor / evidence | Does the evaluator trace a statement back to its source unprompted? |
| Review Center | Do blocker vs. hint and the stale/approval states read clearly (no jargon)? |
| Reliability summary | Agreement/disagreement with the blocker; do they conflate coverage with sufficiency? |
| Export | Trust in the audit export; any expectation it contains raw text (it must not). |
| Project B | Do they recognise the eligibility block as correct, not a bug? |

## 8. Recording rules

- Enter only what actually happened; leave unknowns blank ("k. A.").
- Always interpret ratings **together with** the run's `EvaluationRunSummary`
  ([EvaluationRunSummary.example.md](EvaluationRunSummary.example.md)); high coverage + low
  sufficiency is a **risk signal, not success**.
- Costs are never invented — `estimated_cost` stays a placeholder.
- Mapping of observations to thesis questions:
  [Thesis_Evaluation_Mapping.md](Thesis_Evaluation_Mapping.md).
