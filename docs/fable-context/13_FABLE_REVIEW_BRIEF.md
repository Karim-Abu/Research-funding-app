# Fable Review Brief

## App-Ziel

Die App unterstützt Innosuisse-Antragsteams bei Quellenverarbeitung, Requirements/Evidence, Feldentwürfen, Review, Export und manueller Innolink-Copy-Paste-Übernahme. Kein automatisches Innolink-Submit und keine finale Förderfähigkeitsentscheidung sind implementiert (`backend/app/runs/graph.py:267`, `lib/export-view.ts:21`, `lib/portal-transfer.ts:1`).

## Aktueller Stack

Next.js 16, React 19, TypeScript, Tailwind, TipTap, Vitest, Playwright im Frontend; FastAPI, Pydantic v2, SQLAlchemy, Alembic, SQLite, LangGraph, PyYAML, httpx und pytest im Backend (`package.json:20`, `package.json:24`, `backend/requirements.txt:4`, `backend/requirements.txt:18`).

## Reifegrad

Supervised Beta. Viele Backend-Artefakte sind echt implementiert, aber mehrere Produktbereiche bleiben teilweise, mock-basiert oder Zielarchitektur: vollständige Innolink-Struktur, Copy-Audit, Budgetplan, Azure/Production Cloud, persistente Rework Tasks (`backend/app/db/models.py:92`, `lib/api.ts:51`, `lib/portal-transfer.ts:112`, `final_backend_contracts_v1_1/data_policy_v1_1.yaml:89`).

## Hauptworkflow

Quelle -> Analyse-Run -> Evidence Discovery/Verification -> Requirements/Rules -> Template Drafts/A2 Suggestion -> Review/Recheck/Approval -> Export/Copy. Der Graph ist linear und endet completed; HITL läuft über separate APIs (`backend/app/runs/graph.py:349`, `backend/app/review/service.py:405`, `backend/app/review/recheck.py:37`, `backend/app/exports/service.py:39`).

## Zentrale Entitäten

`Project`, `Partner`, `SourceDocument`, `SourceVersion`, `SourceFragment`, `AnalysisRun`, `RequirementAssessment`, `OpenIssue`, `EvidenceAnchor`, `EvidenceLink`, `PortalFieldDraft`, `DraftVersion`, `ReviewFinding`, `ReviewApproval`, `ExportArtifact`, `AgentInvocation`, `ResearchTask`, `MarketComparison`, `DraftClaim`, `ClaimLineage`, `RunQualitySummary` sind implementiert (`backend/app/db/models.py:92`, `backend/app/db/models.py:471`, `backend/app/db/models.py:185`, `backend/app/db/models.py:313`, `backend/app/db/models.py:565`, `backend/app/db/models.py:686`, `backend/app/db/models.py:777`, `backend/app/db/models.py:839`, `backend/app/db/models.py:904`, `backend/app/db/models.py:998`, `backend/app/db/models.py:1050`, `backend/app/db/models.py:1271`, `backend/app/db/models.py:1374`, `backend/app/db/models.py:1510`, `backend/app/db/models.py:1580`).

## LLM-/Provider-Architektur

ModelGateway ist zentrale Providergrenze mit Data Policy, CostGuard, Schema Validation und Audit (`backend/app/agents/gateway.py:1`). Fake Provider ist implementiert, OpenAI/Anthropic Direct sind dormant/env-gated, Firecrawl ist für Web Research vorhanden, Azure ist nicht implementiert (`backend/app/agents/providers/fake.py:1`, `backend/app/agents/providers/openai.py:1`, `backend/app/agents/providers/anthropic.py:1`, `backend/app/research/providers/firecrawl.py:1`, `final_backend_contracts_v1_1/data_policy_v1_1.yaml:89`).

## Datenschutz-/Datenklassenmodell

DataClassification hat fünf Dimensionen; D0-D3/UNKNOWN sind code-interne Labels. UNKNOWN und D3 blockieren externe Tools fail-closed. D1/D2 Web Research muss sanitized approved Query nutzen; D2 Live Provider ist zusätzlich gated (`backend/app/contracts/classification.py:9`, `backend/app/security/data_class.py:29`, `backend/app/security/search_query_firewall.py:267`, `backend/app/research/executor.py:145`).

## Innolink-Feld-/Copy-Paste-Logik

Die Registry enthält 161 Portal Field Einträge; 18 sind raw draft_text/agent_writable; 8 werden nach Backend-M6-Filter als Singleton-Draft-Felder unterstützt. A2 ist nur für `SOL.INNOVATION_SOLUTION.EDITOR` und `VC.BUSINESS_TARGETS_MODEL.EDITOR` enabled (`backend/app/registry/loader.py:94`, `backend/app/registry/loader.py:131`, `backend/app/agents/a2_fields.py:23`). Copy ist UI-only, advisory und nicht auditiert (`lib/portal-transfer.ts:80`, `components/portal-transfer/portal-transfer.tsx:46`).

## Implementierte Stärken

- Solides Backend-Domänenmodell mit Alembic-Migrationen (`backend/app/db/models.py:30`).
- Fail-closed Registry Loading für Requirements/Rules/Agents (`backend/app/main.py:43`, `backend/app/main.py:48`).
- Deterministische Evidence/Review/Export-Pipeline (`backend/app/runs/graph.py:109`, `backend/app/review/checks.py:1`, `backend/app/exports/snapshot.py:1`).
- Gute Privacy-Firewall für Web Research (`backend/app/security/search_query_firewall.py:182`, `backend/app/security/approval_service.py:181`).
- Reliability-Schicht trennt Evidence Coverage und Sufficiency (`backend/app/reliability/summary.py:4`, `backend/app/reliability/sufficiency.py:1`).

## Kritische P0/P1-Gaps

| Prio | Gap | Codebeleg |
|---|---|---|
| P0 | Copy trotz Blockern/Platzhaltern/stale Review möglich und nicht auditierbar | `lib/portal-transfer.ts:80`, `components/portal-transfer/portal-transfer.tsx:46` |
| P0 | Vollständige Innolink-Struktur/Budget/WorkPackages fehlen als strukturierte Workflows | `lib/portal-transfer.ts:112`, `backend/app/registry/loader.py:94` |
| P0 | Azure/Production Cloud Route fehlt | `final_backend_contracts_v1_1/data_policy_v1_1.yaml:89`, `backend/app/agents/gateway.py:107` |
| P1 | Run ist linear, keine echte persisted Rework/HITL Loop | `backend/app/runs/graph.py:267`, `backend/app/review/recheck.py:1` |
| P1 | Rework Tasks fehlen | Keine `ReworkTask` in `backend/app/db/models.py`; UI Next Actions in `components/review/live-review.tsx:306` |
| P1 | Field-Level DataClassification fehlt | `backend/app/registry/loader.py:85` |

## Offene Architekturfragen an Fable 5

1. Soll Copy serverseitig blockiert werden oder über einen auditierbaren Override erlaubt bleiben?
2. Wie soll die 161-Felder-Registry in narrative Drafts vs. strukturierte Innolink-Subflows aufgeteilt werden?
3. Welche minimalen DB-Entitäten braucht Budget/WorkPackages/Milestones für Innosuisse-Regeln?
4. Soll A2 targeted-only bleiben oder als Run-Stage aktiviert werden?
5. Wie wird Azure/Institutional Route produktionsfähig integriert, ohne Direct Provider Policies zu verwässern?
6. Sollen Review Findings zu persistierten Rework Tasks werden?

## Was Fable nicht tun soll

Fable soll kein automatisches Innolink-Submit, keine automatische Übernahme von KI-Vorschlägen und kein finales Förderfähigkeitsurteil empfehlen. Diese Verhaltensweisen sind weder als Ziel im Code belegt noch mit den Produktleitplanken vereinbar (`lib/export-view.ts:21`, `backend/app/review/service.py:405`, `backend/app/repositories/draft_suggestions.py:4`).

## Wichtigste Code-Dateien für spätere Umsetzung

| Bereich | Dateien |
|---|---|
| API/Backend Entry | `backend/app/main.py`, `backend/app/api/*` |
| DB/Domain | `backend/app/db/models.py`, `backend/app/migrations/versions/*` |
| Registry/Contracts | `backend/app/registry/loader.py`, `final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml`, `requirements.yaml`, `agents_v1_1.yaml` |
| Runs/Review/Export | `backend/app/runs/graph.py`, `backend/app/review/service.py`, `backend/app/review/package.py`, `backend/app/exports/*` |
| Agents/Policy | `backend/app/agents/gateway.py`, `backend/app/agents/data_policy.py`, `backend/app/security/*` |
| Frontend Live | `components/editor/live-editor.tsx`, `components/review/live-review.tsx`, `components/export/live-export.tsx`, `components/portal-transfer/*` |
| Frontend Clients | `lib/fields.ts`, `lib/review.ts`, `lib/exports.ts`, `lib/portal-transfer.ts`, `lib/export-view.ts` |

