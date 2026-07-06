# Review, Quality And Reliability

## Review Center / Quality Gates

Review aggregiert Requirements, OpenIssues, Drafts, EvidenceLinks, ReviewFindings und Approval-Status in einem `ReviewPackage` (`backend/app/review/service.py:102`, `backend/app/review/package.py:374`). Findings werden deterministisch berechnet und persistent gehalten (`backend/app/review/checks.py:53`, `backend/app/review/package.py:115`).

## Implementierte Quality Gates

| Gate | Status | Codebeleg |
|---|---|---|
| Character limits | Implementiert | `backend/app/review/checks.py:204`, `backend/app/review/service.py:347` |
| Placeholder detection | Implementiert | `backend/app/review/checks.py:185`, `backend/app/review/service.py:345` |
| Required fields completeness | Teilweise über leere Drafts/Requirements | `backend/app/review/checks.py:169`, `backend/app/rules/aggregation.py:1` |
| Evidence coverage | Implementiert als Links/Review und Reliability Coverage | `backend/app/review/checks.py:265`, `backend/app/reliability/summary.py:84` |
| Evidence sufficiency | Implementiert in Reliability | `backend/app/reliability/sufficiency.py:1` |
| Unsupported claims | Implementiert in Reliability | `backend/app/reliability/gate.py:45` |
| Quantified claims without evidence | Implementiert in Reliability | `backend/app/reliability/gate.py:73` |
| Market claims without market evidence | Implementiert in Reliability | `backend/app/reliability/gate.py:81` |
| False consensus | Implementiert in Reliability | `backend/app/reliability/false_consensus.py:1` |
| Semantic drift | Implementiert in Reliability | `backend/app/reliability/drift.py:1` |
| Stale reliability | Implementiert | `backend/app/reliability/approval.py:42`, `backend/app/reliability/approval.py:88` |
| Human review required | Implementiert als Approval Gate | `backend/app/review/service.py:405` |
| Export readiness | Teilweise; Export markiert Draft statt hart zu blockieren | `backend/app/exports/eligibility.py:3` |
| Copy readiness | UI-only/advisory | `lib/export-view.ts:140`, `lib/portal-transfer.ts:80` |

## Claim Extraction und Claim Lineage

Reliability extrahiert deterministisch Claims aus DraftVersion-Texten (`backend/app/reliability/extract.py:1`, `backend/app/reliability/executor.py:107`). ClaimLineage verknüpft Claims mit EvidenceAnchors, A1 Facts, AgentEvidenceProposals, MarketComparison Items und A3 Findings (`backend/app/reliability/lineage.py:1`, `backend/app/reliability/lineage.py:60`, `backend/app/reliability/lineage.py:130`, `backend/app/reliability/lineage.py:146`).

## Evidence Coverage vs. Sufficiency

Coverage und Sufficiency werden ausdrücklich getrennt: Coverage fragt, ob Evidence vorhanden ist; Sufficiency fragt, ob die Evidence den konkreten Claim stützt (`backend/app/reliability/summary.py:4`, `backend/app/reliability/sufficiency.py:3`). Ein Anchor allein impliziert nicht automatisch Claim-Support (`backend/app/reliability/sufficiency.py:7`).

## RunQualitySummary

`RunQualitySummary` wird aus Claims, Lineage, Drift, Findings und Leakage Scan gebaut (`backend/app/reliability/summary.py:60`). Kennzahlen umfassen Claim Counts, supported/weak/unsupported/conflicting Claims, Evidence Coverage, blocker/warning counts, false consensus, semantic drift, raw logging detected und cost placeholder (`backend/app/reliability/summary.py:111`, `backend/app/reliability/summary.py:126`, `backend/app/reliability/service.py:117`).

## Recheck / Approval

Recheck ist async, validiert erwartete ReviewPackage-Version, recomputed Review, kann A3 advisory ausführen und cleared `recheck_required` (`backend/app/review/recheck.py:37`, `backend/app/review/recheck.py:121`, `backend/app/review/recheck.py:145`). Approval prüft Scope Hash, ReviewPackage-Version und harte Blocker (`backend/app/review/service.py:419`, `backend/app/review/service.py:433`).

## Was wird blockiert?

Approval wird blockiert durch: Run nicht reviewable, stale Review Hash/Version, `recheck_required`, leere Drafts, Placeholder, Zeichenlimit, stale Evidence Links, blocker OpenIssues und Reliability blockers/staleness (`backend/app/review/service.py:410`, `backend/app/review/service.py:422`, `backend/app/review/service.py:364`, `backend/app/reliability/approval.py:47`).

Export wird nicht hart durch Blocker blockiert; stattdessen `draft_marked` (`backend/app/exports/eligibility.py:3`). Copy wird nicht blockiert; Warnungen bleiben advisory (`lib/portal-transfer.ts:80`).

## Findings speichern / erledigen

Findings werden in `ReviewFinding` gespeichert (`backend/app/db/models.py:839`). Deterministische Findings werden idempotent resolved, wenn sie nicht erneut auftreten (`backend/app/review/package.py:183`). Human Decisions können Finding-Status ändern, aber harte Gates werden neu abgeleitet (`backend/app/review/service.py:237`).

## Rework Tasks

Eine eigenständige `ReworkTask`-Entität wurde nicht gefunden. `ReviewFinding.recommended_next_action` und UI-Next-Actions sind vorhanden, aber kein persistenter Task-Workflow (`backend/app/db/models.py:839`, `components/review/live-review.tsx:306`).

## Tests

Relevante Tests: Review Findings, Review Decisions, Approval, Recheck, Reliability Pass, Export Eligibility, Portal Transfer (`backend/tests/test_review_findings.py:12`, `backend/tests/test_review_decisions.py:23`, `backend/tests/test_review_approval.py:21`, `backend/tests/test_review_recheck.py:31`, `backend/tests/test_reliability_pass.py:1`, `backend/tests/test_export_eligibility.py:1`, `e2e/portal-transfer.spec.ts:1`).

