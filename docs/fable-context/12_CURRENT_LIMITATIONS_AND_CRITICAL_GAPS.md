# Current Limitations And Critical Gaps

## Priorisierte Gaps

| Prio | Architekturproblem | Warum kritisch | Betroffene Dateien | Beleg im Code | Empfohlener Fix | Minimaler Testnachweis |
|---|---|---|---|---|---|---|
| P0 | Copy trotz Blockern/Platzhaltern/stale Review möglich und nicht auditiert | Hauptausgabe ist Innolink Copy-Paste; Nutzer kann trotz Warnungen kopieren, ohne persistenten Risk-Acceptance-Trail. | `lib/portal-transfer.ts`, `components/portal-transfer/*` | `lib/portal-transfer.ts:80`, `components/portal-transfer/portal-transfer.tsx:46` | Server-seitige Copy Readiness + AuditEvent/Override-Flow oder hartes Blocking definieren. | Test: Copy blocked/override audited bei Blocker, Placeholder, stale review. |
| P0 | Vollständige Innolink-Struktur nicht als Arbeitsmodell implementiert | Ziel ist Innolink-Arbeitsplatz; strukturierte Portalbereiche bleiben außerhalb der App. | `backend/app/registry/loader.py`, `lib/portal-transfer.ts` | `backend/app/registry/loader.py:94`, `lib/portal-transfer.ts:112` | PortalFieldDefinition/Draft/StructuredField splitten; WorkPackages/Milestones/Budget als eigene Entities. | Contract Test gegen Registry + CRUD/E2E für wiederholte Felder. |
| P0 | Budget-/Finanzierungslogik nicht vollständig strukturiert berechenbar | 40-60%- und 5%-Regeln sind für Innosuisse zentral. | `backend/app/db/models.py`, `components/intake/intake-form.tsx`, contracts | Kein `BudgetPlan` Modell; Intake-Budgetfeld bei `components/intake/intake-form.tsx:670` | BudgetPlan API/DB-Modell, Contribution-Entities, Rule Engine Inputs. | Tests für 40-60%, 5%, missing values, partner allocations. |
| P0 | Production Cloud/Azure Route fehlt | Datenschutz-/Institutional-Route ist zentrale Leitplanke für echte Anträge. | `backend/app/agents/providers/*`, `backend/app/agents/gateway.py` | Azure nur Policy (`final_backend_contracts_v1_1/data_policy_v1_1.yaml:89`), Gateway kennt OpenAI/Anthropic (`backend/app/agents/gateway.py:107`) | Azure Provider hinter Data Policy, Managed Identity/Key Vault, regional config. | Provider smoke mit fake Azure + policy denial/allow tests. |
| P1 | Run-State-Machine ist linear, keine echte HITL-Loop | Review/Rework ist Zielworkflow; Graph endet completed, Recheck läuft separat. | `backend/app/runs/graph.py`, `backend/app/review/recheck.py` | `backend/app/runs/graph.py:267`, `backend/app/runs/graph.py:361` | Explizite Review/Rework states oder Workflow-Projection mit Tasks. | E2E: finding -> rework task -> edit -> recheck -> approval. |
| P1 | Rework Tasks fehlen | Findings führen nicht zu persistierten Arbeitsaufgaben. | `backend/app/db/models.py`, `components/review/live-review.tsx` | Keine `ReworkTask`; Next Actions UI-only (`components/review/live-review.tsx:306`) | `ReworkTask` aus Findings ableiten, Status/Owner/Field Link. | Test: blocker creates task; resolved finding closes task. |
| P1 | A2 im Hauptgraph deaktiviert; Feldvorschläge nur gezielt | Erwartete Pipeline Entwurfserzeugung ist nur teilweise aktiv. | `backend/app/runs/graph.py`, `backend/app/fields/redraft_service.py` | `backend/app/runs/graph.py:191`, `backend/app/fields/redraft_service.py:49` | Produktentscheidung: targeted-only beibehalten oder graph-stage aktivieren. | Test: supported field suggestion generated/accepted under policy. |
| P1 | Market Analysis nur teilweise in Value Creation integriert | Market/Competitor ist wichtig für Value Creation. | `backend/app/market/*`, `components/editor/market-competition-panel.tsx` | Live market panel read-only/empty fallback (`components/editor/market-competition-panel.tsx:70`) | MarketComparison als Evidence/Requirement/Input für VC-Draft formal anbinden. | Test: source-backed market item appears in VC context and reliability lineage. |
| P1 | DataClassification auf Feld-/Output-Ebene unvollständig | Leitplanke verlangt Projekt-, Quellen-, Feld-, Payload-, Query-, Output-Ebene. | `backend/app/registry/loader.py`, `backend/app/db/models.py` | PortalFieldDef ohne DataClassification (`backend/app/registry/loader.py:85`) | Field-level classification/effective output classification modellieren. | Test: confidential field blocks provider even in public project. |
| P1 | Production No-Raw-Logging Enforcement nur teilweise | Raw leak prevention darf in Produktion nicht nur Best Effort sein. | `backend/app/security/redaction.py`, `backend/app/reliability/summary.py` | Production no-op (`backend/app/security/redaction.py:57`) | Structured safe logging wrapper mit CI/runtime enforcement. | Test: raw query/project term cannot enter AuditEvent/ControlResult. |
| P2 | Placeholder Detection uneinheitlich | Copy readiness und Editor/Review können abweichen. | `lib/portal-transfer.ts`, `lib/draft-view.ts` | TODO (`lib/portal-transfer.ts:29`) | Gemeinsame Placeholder-Library + Tests. | Test: same text yields same placeholder count everywhere. |
| P2 | Legacy Mock-Routen parallel | Review kann falsche Reife suggerieren. | `lib/api.ts`, `app/api/*` | Legacy mock remains (`lib/api.ts:51`) | Mock/live boundary dokumentieren oder Legacy entfernen. | Test: live mode uses only live clients for supported screens. |

## Spezifische Prüfpunkte aus dem Auftrag

| Prüffrage | Befund |
|---|---|
| Intake-Datenklassifizierung projektweit zu grob? | Teilweise: Projekt/Quelle implementiert; Feld-Level nicht gefunden (`backend/app/contracts/classification.py:9`, `backend/app/registry/loader.py:85`). |
| Quellenklassifikation pro Upload vorhanden? | Ja, mit Effective Merge (`backend/app/api/sources.py:103`, `backend/app/api/sources.py:163`). |
| Effective data class aus Projekt + Quellen + Feldern berechnet? | Projekt+Quelle ja; Feld nicht gefunden (`backend/app/policy/classification.py:28`). |
| Intake-Partner werden persistiert? | Partner API existiert; direkte Intake-Persistenz unklar (`backend/app/api/partners.py:49`, `components/intake/intake-form.tsx:604`). |
| Budgetdaten strukturiert erfasst? | Nur teilweise/grob; kein BudgetPlan-Modell gefunden. |
| File Upload Route funktioniert? | Implementiert mit Tests (`backend/app/api/sources.py:93`, `backend/tests/test_sources.py:66`). |
| Legacy API-Routen parallel? | Ja (`lib/api.ts:51`, `app/api/sections/[fieldId]/route.ts:1`). |
| Override Copy ohne Audit? | Ja/Gap: Copy session-only (`components/portal-transfer/portal-transfer.tsx:46`). |
| Export Control Approval Gate korrekt? | Draft-Markierung ja; kein hartes Export-Blocking (`backend/app/exports/eligibility.py:3`). |
| Search Query Firewall vor Firecrawl/Webresearch? | Ja, Research Service ruft Firewall vor Task-Persistenz/Provider (`backend/app/research/service.py:151`). |
| Provider Vector Stores blockiert? | Ja in Policy/Test (`backend/tests/test_data_class.py:61`). |
| Innolink-PDF-Import vorhanden? | Nicht gefunden. |

