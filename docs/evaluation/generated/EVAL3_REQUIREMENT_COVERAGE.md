---
title: "EVAL3 — Requirement Coverage"
date: 2026-07-25
commit: 8416914
status: generated
tags: [eval3, coverage, requirements]
---

# EVAL3 — Requirement Coverage

> Erzeugt von `scripts/evaluation/requirement_coverage.py` (evaluation-only, neu für diesen Lauf). Rohdaten: `requirement_coverage.json`. Siehe [[EVAL3_TECHNICAL_VERIFICATION]] und [[EVALUATION_BASELINE]].

## Kennzahlen

- Requirements gesamt: **76** (alle `status: active`)
- Severity: blocker **52**, warning **18**, info **6**
- Vom Loader ausgewertet (`official_core_rules`): **12**
- Nur im Contract (`QG.*` nicht implementiert): **64**

| Kennzahl | gegen alle Requirements | gegen die auswertbaren |
|---|---|---|
| Implementation Coverage | 12/76 = 15.8 % | 12/12 = 100.0 % |
| Test Coverage | 8/76 = 10.5 % | 8/12 = 66.7 % |

**Nenner ausgewiesen, nichts stillschweigend entfernt.** «Test Coverage» heisst hier: mindestens eine Testdatei nennt die Requirement- oder Regel-ID wörtlich. Das belegt *Vorhandensein*, nicht fachliche Vollständigkeit der Prüfung.

## A. Auswertbare Requirements (12)

Regel wird von `app/registry/loader.py` geladen und über `condition.type` in `app/rules/handlers.py::HANDLERS` dispatcht (`app/rules/engine.py:90`). Die Regel-ID steht bewusst **nicht** im Code — die Engine ist datengetrieben.

| Requirement ID | Titel | Priorität | Verknüpfte Regel | Testreferenz | Coverage-Status |
|---|---|---|---|---|---|
| `REQ.INNO.PARTNER.IMPLEMENTATION.MIN1_CH` | Mindestens ein Umsetzungspartner mit Schweiz-Bezug | blocker | `INNO.PARTNER.IMPLEMENTATION.MIN1_CH` | `backend/tests/a1_helpers.py`, `backend/tests/a1_mapping_helpers.py`, `backend/tests/a2_helpers.py` (+10) | implemented-and-tested |
| `REQ.INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE` | Mindestens ein beitragsberechtigter Schweizer Forschungspartner | blocker | `INNO.PARTNER.RESEARCH.MIN1_CH_ELIGIBLE` | `backend/tests/test_demo_seed.py`, `backend/tests/test_evidence_flow.py`, `backend/tests/test_registry_rules.py` (+6) | implemented-and-tested |
| `REQ.INNO.PARTNER.INDEPENDENCE.PERSONNEL` | Personelle Unabhängigkeit der Projektpartner | blocker | `INNO.PARTNER.INDEPENDENCE.PERSONNEL` | — | implemented-not-tested |
| `REQ.INNO.PARTNER.INDEPENDENCE.FINANCIAL_20` | Finanzielle Unabhängigkeit und 20-Prozent-Schwelle | blocker | `INNO.PARTNER.INDEPENDENCE.FINANCIAL_20` | `backend/tests/test_export_generators.py`, `backend/tests/test_rule_messages.py` | implemented-and-tested |
| `REQ.INNO.BUDGET.IMPLEMENTATION_SHARE_40_60` | Umsetzungspartnerbeitrag 40–60 Prozent | blocker | `INNO.BUDGET.IMPLEMENTATION_SHARE_40_60` | `backend/tests/test_discovery_red_compliance_status.py`, `backend/tests/test_project_budget.py`, `backend/tests/test_run2b_evidence_scope.py` (+5) | implemented-and-tested |
| `REQ.INNO.BUDGET.CASH_MIN5` | Barbeitrag mindestens 5 Prozent | blocker | `INNO.BUDGET.CASH_MIN5` | `backend/tests/test_discovery_red_compliance_status.py`, `backend/tests/test_project_budget.py`, `backend/tests/test_registry_rules.py` (+8) | implemented-and-tested |
| `REQ.INNO.BUDGET.NO_FINANCIAL_CAP` | Keine formale finanzielle Obergrenze | info | `INNO.BUDGET.NO_FINANCIAL_CAP` | `backend/tests/test_z_compliance_review_separation.py`, `test/live-requirements.test.tsx` | implemented-and-tested |
| `REQ.INNO.DURATION.NO_FORMAL_MAX_WITH_IMPLEMENTATION_PARTNER` | Keine formale Höchstdauer mit Umsetzungspartner | info | `INNO.DURATION.NO_FORMAL_MAX_WITH_IMPLEMENTATION_PARTNER` | — | implemented-not-tested |
| `REQ.INNO.DURATION.TYPICAL_6_36` | Übliche Projektdauer 6–36 Monate | warning | `INNO.DURATION.TYPICAL_6_36` | `backend/tests/test_registry_rules.py`, `backend/tests/test_requirements_flow.py`, `backend/tests/test_run2b_evidence_scope.py` (+1) | implemented-and-tested |
| `REQ.INNO.DURATION.MAX18_WITHOUT_IMPLEMENTATION_PARTNER` | Höchstdauer 18 Monate ohne Umsetzungspartner | blocker | `INNO.DURATION.MAX18_WITHOUT_IMPLEMENTATION_PARTNER` | `backend/tests/test_registry_rules.py`, `backend/tests/test_requirements_flow.py` | implemented-and-tested |
| `REQ.INNO.APPLICATION.COMPLETE_AND_TRACEABLE` | Gesuch vollständig und inhaltlich nachvollziehbar | blocker | `INNO.APPLICATION.COMPLETE_AND_TRACEABLE` | — | implemented-not-tested |
| `REQ.INNO.SCIENTIFIC_INTEGRITY.REVIEW` | Scientific-Integrity-Angabe verlangt Human Review | blocker | `INNO.SCIENTIFIC_INTEGRITY.REVIEW` | — | implemented-not-tested |

## B. Contract-only Requirements (64)

Diese verweisen auf die 64 `QG.*`-Portal-Quality-Gates. `loader.py` parst ausschliesslich `official_core_rules`; `QG.` und `XF.` kommen im Code nicht vor. Sie sind **spezifiziert, aber nicht implementiert** — und werden hier namentlich geführt statt aus dem Nenner entfernt.

| Requirement ID | Titel | Priorität | Verknüpfte Regel | Testreferenz | Coverage-Status |
|---|---|---|---|---|---|
| `REQ.PORTAL.INTRO.ARAMIS_PUBLICATION` | Aramis publication review | warning | — | — | contract-only |
| `REQ.PORTAL.INTRO.ABSTRACT.LIMIT` | Abstract character limit | blocker | — | — | contract-only |
| `REQ.PORTAL.INTRO.EXEC_SUMMARY.LIMIT` | Executive summary character limit | blocker | — | — | contract-only |
| `REQ.PORTAL.INTRO.CLUSTER_SINGLE_SELECT` | Cluster single select | blocker | — | — | contract-only |
| `REQ.PORTAL.INTRO.SPECIAL_FUNDING_SINGLE_OPTION` | Special funding measure single option | info | — | — | contract-only |
| `REQ.PORTAL.INTRO.PREV.DOUBLEFUND` | Previous funding double-funding check | blocker | — | — | contract-only |
| `REQ.PORTAL.INTRO.IP.FTO` | IP/FTO review trigger | warning | — | — | contract-only |
| `REQ.PORTAL.INTRO.IPR_UPLOAD` | IPR documents upload rule | blocker | — | — | contract-only |
| `REQ.PORTAL.ORG.ONE_OFFICIAL_REPRESENTATIVE` | One representative per contract party | warning | — | — | contract-only |
| `REQ.PORTAL.ORG.RESEARCH.MIN1` | At least one research partner | blocker | — | — | contract-only |
| `REQ.PORTAL.ORG.PROJECT_MANAGER_PARTNER_REQUIRED` | Project Manager requires partner | blocker | — | — | contract-only |
| `REQ.PORTAL.ORG.PROJECT_MANAGER_FIRST_CONTACT` | Project Manager first contact | warning | — | — | contract-only |
| `REQ.PORTAL.ORG.MAIN_RESEARCH_PARTNER_FUNDS` | Main Research Partner manages funds | warning | — | — | contract-only |
| `REQ.PORTAL.ORG.ADMIN.MAX2` | Max 2 admin users | blocker | — | — | contract-only |
| `REQ.PORTAL.ORG.OTHER_CONTACTS_AUTH_MANAGEMENT` | Other contacts via auth management | info | — | — | contract-only |
| `REQ.PORTAL.ORG.SME_FTE_THRESHOLD` | SME threshold 250 FTE | info | — | — | contract-only |
| `REQ.PORTAL.ORG.INDEPENDENCE.EMPLOYEE_OVERLAP_YES` | Personnel independence — employee overlap follow-up | blocker | — | — | contract-only |
| `REQ.PORTAL.ORG.INDEPENDENCE.BOARD_ROLE_YES` | Personnel independence — board role follow-up | blocker | — | — | contract-only |
| `REQ.PORTAL.ORG.INDEPENDENCE.OTHER_ROLE_YES` | Personnel independence — other role follow-up | blocker | — | — | contract-only |
| `REQ.PORTAL.ORG.FINANCIAL_INDEPENDENCE_20` | 20% financial independence | blocker | — | — | contract-only |
| `REQ.PORTAL.ORG.FINANCIAL_COMMENT_LIMIT` | Financial independence comment limit | blocker | — | — | contract-only |
| `REQ.PORTAL.VC.BTM_CHARACTER_LIMIT` | Business Targets & Business Model character limit | blocker | — | — | contract-only |
| `REQ.PORTAL.VC.ALL_QUESTIONS_ANSWERED` | All mandatory questions answered | blocker | — | — | contract-only |
| `REQ.PORTAL.VC.MAIN_QUESTIONS_NOT_DELETABLE` | Main questions not deletable | blocker | — | — | contract-only |
| `REQ.PORTAL.VC.EVIDENCE.MARKET` | Market evidence anchors | warning | — | — | contract-only |
| `REQ.PORTAL.VC.BUSINESS_PLAN_UPLOAD` | Business Plan upload rule | blocker | — | — | contract-only |
| `REQ.PORTAL.SOL.CHARACTER_LIMIT` | Innovation Solution character limit | blocker | — | — | contract-only |
| `REQ.PORTAL.SOL.ALL_QUESTIONS_ANSWERED` | All mandatory questions answered | blocker | — | — | contract-only |
| `REQ.PORTAL.SOL.MAIN_QUESTIONS_NOT_DELETABLE` | Main questions not deletable | blocker | — | — | contract-only |
| `REQ.PORTAL.SOL.SOTA.EVIDENCE` | SOTA evidence anchors | warning | — | — | contract-only |
| `REQ.PORTAL.SOL.INNOVATION.NOT_BEST_PRACTICE` | Innovation vs. best practice | warning | — | — | contract-only |
| `REQ.PORTAL.SOL.QUANTIFIABLE_GOALS` | Quantifiable goals required | warning | — | — | contract-only |
| `REQ.PORTAL.SOL.PARTNER_SUITABILITY` | Partner suitability required | warning | — | — | contract-only |
| `REQ.PORTAL.SOL.PUBLICATIONS_UPLOAD` | Publications upload rule | blocker | — | — | contract-only |
| `REQ.PORTAL.PS.DATE.DURATION` | Project duration without IP partner | blocker | — | — | contract-only |
| `REQ.PORTAL.PS.WP.MILESTONES` | Work packages & milestones structure | warning | — | — | contract-only |
| `REQ.PORTAL.PS.MILESTONES_SPREAD` | Milestones reasonable spread | warning | — | — | contract-only |
| `REQ.PORTAL.PS.WP_DESCRIPTION_LIMIT` | Work package description limit | blocker | — | — | contract-only |
| `REQ.PORTAL.PS.WP_ACTIVITIES_LIMIT` | Work package activities limit | blocker | — | — | contract-only |
| `REQ.PORTAL.PS.WP_DELIVERABLES_LIMIT` | Work package deliverables limit | blocker | — | — | contract-only |
| `REQ.PORTAL.PS.MILESTONE_DESCRIPTION_LIMIT` | Milestone description limit | blocker | — | — | contract-only |
| `REQ.PORTAL.PS.MILESTONE_GOALS_MEASURABLE` | Milestone goals measurable | warning | — | — | contract-only |
| `REQ.PORTAL.PS.MANAGEMENT_EXPLANATION_LIMIT` | Management hours explanation limit | blocker | — | — | contract-only |
| `REQ.PORTAL.PS.RISK.COVERAGE` | Risk categories coverage | warning | — | — | contract-only |
| `REQ.PORTAL.PS.RISK_UPLOAD` | Risk management upload rule | blocker | — | — | contract-only |
| `REQ.PORTAL.PS.SALARY_NO_CASH_DOUBLE_LISTING` | No double listing of cash-covered salaries | blocker | — | — | contract-only |
| `REQ.PORTAL.PS.RESEARCH_SALARY_NOT_FINANCED` | Research salary not financed elsewhere | blocker | — | — | contract-only |
| `REQ.PORTAL.PS.SALARY_DELTA` | Salary plan vs. budget delta | warning | — | — | contract-only |
| `REQ.PORTAL.PS.MATERIAL_ELIGIBILITY` | Material costs eligibility | warning | — | — | contract-only |
| `REQ.PORTAL.PS.MATERIAL_POSITION_EXPLANATION_LIMIT` | Material position explanation limit | blocker | — | — | contract-only |
| `REQ.PORTAL.PS.MATERIAL_EVIDENCE_UPLOAD` | Material evidence upload rule | blocker | — | — | contract-only |
| `REQ.PORTAL.PS.CASH_WAIVER_EVIDENCE` | Cash waiver evidence required | warning | — | — | contract-only |
| `REQ.PORTAL.PS.CASH_SALARY_TASKS_LIMIT` | Cash-to-salary tasks limit | blocker | — | — | contract-only |
| `REQ.PORTAL.PS.CASH_MATERIAL_EXPLANATION_LIMIT` | Cash-to-material explanation limit | blocker | — | — | contract-only |
| `REQ.PORTAL.PS.CASH_EVIDENCE_UPLOAD` | Cash evidence upload rule | blocker | — | — | contract-only |
| `REQ.PORTAL.PS.IMPL.40_60` | Implementation partner 40–60% | blocker | — | — | contract-only |
| `REQ.PORTAL.PS.CASH.MIN5` | Cash contribution ≥ 5% | blocker | — | — | contract-only |
| `REQ.PORTAL.SUM.SUMMARY_OVERVIEW` | Summary overview shows open issues | info | — | — | contract-only |
| `REQ.PORTAL.SUM.COVER_LETTER_UPLOAD` | Cover letter upload rule | blocker | — | — | contract-only |
| `REQ.PORTAL.SUM.MANDATORY.OPEN` | All mandatory fields complete | blocker | — | — | contract-only |
| `REQ.PORTAL.SUM.ATTACHMENTS` | Attachment validation | blocker | — | — | contract-only |
| `REQ.PORTAL.SUM.SCIINT` | Scientific integrity HITL | blocker | — | — | contract-only |
| `REQ.PORTAL.SUM.ADMIN_RIGHTS_REQUIRED` | Admin rights required to submit | blocker | — | — | contract-only |
| `REQ.PORTAL.SUM.ADMIN.CONFIRM` | Complete & correct confirmation | blocker | — | — | contract-only |
