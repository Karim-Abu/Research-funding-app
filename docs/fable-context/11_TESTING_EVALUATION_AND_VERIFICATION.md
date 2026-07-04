# Testing, Evaluation And Verification

## Teststruktur

| Bereich | Pfad | Status | Codebeleg |
|---|---|---|---|
| Frontend Unit/Component | `test/*.test.ts(x)` | Implementiert | `test/exports.test.ts:33`, `test/evidence.test.ts:36` |
| Backend Pytest | `backend/tests/test_*.py` | Implementiert | `backend/tests/test_sources.py:66`, `backend/tests/test_runs.py:101` |
| E2E/API Smoke | `e2e/*.spec.ts` | Implementiert | `e2e/a2-solution-innovation.spec.ts:45`, `e2e/market-comparison.spec.ts:73` |
| Scripts | `scripts/verify_all.ps1`, `scripts/smoke_api.py` | Implementiert | `scripts/verify_all.ps1:1`, `scripts/smoke_api.py:1` |

## Unit Tests

Frontend-Tests decken u. a. Exports Client, Evidence Client, Data Classification, Clipboard, Portal Transfer, Review Views, Live Editor, Requirements und Dashboard ab (`test/exports.test.ts:33`, `test/evidence.test.ts:36`, `test/data-classification.test.ts:4`, `test/clipboard.test.ts:1`, `test/portal-transfer.test.tsx:1`).

Backend-Tests decken Auth, Sources, Runs, Requirements, Evidence, Review, Export, Agents, Privacy Firewall, Public Web Research, Market Comparison und Reliability ab (`backend/tests/test_auth.py:1`, `backend/tests/test_sources.py:66`, `backend/tests/test_runs.py:101`, `backend/tests/test_requirements_flow.py:64`, `backend/tests/test_review_approval.py:21`, `backend/tests/test_export_eligibility.py:1`, `backend/tests/test_agent_gateway.py:1`, `backend/tests/test_privacy_firewall.py:1`, `backend/tests/test_public_web_research.py:1`, `backend/tests/test_market_comparison.py:1`, `backend/tests/test_reliability_pass.py:1`).

## API Smoke Tests

`scripts/smoke_api.py` existiert als API-Smoke-Script (`scripts/smoke_api.py:1`). Playwright E2E enthält API-context Smokes für A2, run orchestration, source ingestion, review/recheck/approval, reliability, public web research und privacy firewall (`e2e/a2-solution-innovation.spec.ts:3`, `e2e/run-orchestration.spec.ts:1`, `e2e/source-ingestion.spec.ts:1`, `e2e/review-recheck-approval.spec.ts:1`, `e2e/reliability.spec.ts:1`, `e2e/public-web-research.spec.ts:1`, `e2e/privacy-firewall.spec.ts:1`).

## Export Smoke Tests

Backend Export Tests nutzen Helper und prüfen Export-Erzeugung/Download, Draft-Markierung, Security und Async Flow (`backend/tests/export_helpers.py:1`, `backend/tests/test_export_generators.py:1`, `backend/tests/test_export_eligibility.py:1`, `backend/tests/test_export_security.py:1`, `backend/tests/test_export_async.py:1`). Frontend Export Client Tests prüfen Polling/Errors (`test/exports.test.ts:44`).

## No-Raw-Log Tests / Provider Payload Tests

Privacy/No-Raw-Logging wird in Firewall/Data-Class/Agent-Security/Reliability-Tests abgedeckt (`backend/tests/test_data_class.py:31`, `backend/tests/test_privacy_firewall.py:1`, `backend/tests/test_agent_security.py:1`, `backend/tests/test_reliability_pass.py:269`). Provider Payload/Gateway Tests decken Fake Provider, Gateway, CostGuard, DataPolicy, schema validation und real-provider smoke gating ab (`backend/tests/test_agent_fake_provider.py:10`, `backend/tests/test_agent_gateway.py:1`, `backend/tests/test_agent_cost_guard.py:1`, `backend/tests/test_agent_data_policy.py:1`, `backend/tests/test_agent_schemas.py:1`, `backend/tests/test_agent_real_provider_smoke.py:1`).

## Evaluation Dataset

Evaluation-Dokumente und Dataset-Vorlagen liegen unter `docs/evaluation/*`; ein Backend-Evaluation-Modul existiert (`docs/evaluation/Evaluation_Dataset.md:1`, `backend/app/evaluation/__main__.py:1`, `backend/app/evaluation/summary.py:1`). Demo-Fixtures liegen unter `backend/app/demo/fixtures/*` (`backend/app/demo/fixtures/project_a_overview.txt:1`).

## Verification Scripts

`scripts/verify_all.ps1` und `scripts/verify_all.sh` sind vorhanden (`scripts/verify_all.ps1:1`, `scripts/verify_all.sh:1`). Ohne Ausführung ist nur belegt, dass sie im Repository existieren; diese Dokumentation hat keine Runtime-Tests ausgeführt.

## Kritische Tests, die fehlen oder verstärkt werden sollten

| Testfall | Status | Begründung |
|---|---|---|
| Server-seitige Copy Readiness / Copy Audit | Fehlt | Copy ist UI-only (`components/portal-transfer/portal-transfer.tsx:46`) |
| Vollständige Portal-Field-Abdeckung gegen 161 Registry-Felder | Teilweise | M6 filtert Teilmenge (`backend/app/registry/loader.py:94`) |
| Budgetplan 40-60% und 5%-Barbeitrag end-to-end | Teilweise/fehlend | Keine strukturierte BudgetPlan-Entität gefunden |
| Azure Provider/Institutional Route Integration | Fehlt | Kein Provider-Code vorhanden |
| Production no-raw-log hard enforcement | Teilweise | Redaction Guard ist in Production no-op (`backend/app/security/redaction.py:57`) |
| WorkPackage/Milestone strukturierte CRUD-Flows | Fehlt | Registry hat wiederholte Felder, keine Entities gefunden |

## Empfohlene Testfälle für nächste Refactoring-Slices

- Copy bei Blockern erzeugt serverseitigen AuditEvent oder wird geblockt: erwartete Policy festlegen und testen.
- PortalField Registry Contract Test: alle unterstützten Felder, Copy-Felder und A2-Felder aus einer Quelle ableiten.
- BudgetPlan API Tests: 40-60%-Regel, 5%-Barbeitrag, Own Contribution, Cash Contribution.
- Intake-to-Project Persistence Test: Partner, Budget, DataClassification und Project Details aus Intake vollständig persistieren.
- Azure Provider Smoke mit Fake Azure Adapter und Policy Matrix.

