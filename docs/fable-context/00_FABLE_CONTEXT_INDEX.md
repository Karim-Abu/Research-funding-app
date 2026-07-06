# Fable Context Index

## Analyseübersicht

Diese Dokumentation beschreibt den aktuellen Codezustand der Anwendung `Reasearch-funding-app`. Die App ist eine Next.js/React-Frontend-Anwendung mit serverseitiger BFF-Schicht unter `app/api/*` und einem separaten FastAPI-Backend unter `backend/app/*` (`package.json:6`, `package.json:20`, `backend/requirements.txt:4`, `backend/app/main.py:1`). Die Backend-Persistenz basiert im Code auf SQLAlchemy-Modellen und Alembic-Migrationen (`backend/app/db/models.py:30`, `backend/app/migrations/versions/08e269f5b452_initial_schema.py:1`).

Der Code enthält echte Backend-Entitäten für Projekte, Quellen, Runs, Anforderungen, Evidence, PortalFieldDrafts, Review, Approval, Export, AgentInvocation, Public Web Research, MarketComparison und Reliability (`backend/app/db/models.py:92`, `backend/app/db/models.py:185`, `backend/app/db/models.py:313`, `backend/app/db/models.py:565`, `backend/app/db/models.py:686`, `backend/app/db/models.py:777`, `backend/app/db/models.py:839`, `backend/app/db/models.py:904`, `backend/app/db/models.py:998`, `backend/app/db/models.py:1050`, `backend/app/db/models.py:1271`, `backend/app/db/models.py:1374`, `backend/app/db/models.py:1580`).

Der aktuelle Reifegrad ist `Supervised Beta`, nicht `Production Ready`: Der Run-Graph erzeugt deterministische Analyse-, Evidence-, Template-Draft- und Review-Artefakte, aber kein automatisches Innolink-Submit und keine finale Förderfähigkeitsentscheidung (`backend/app/runs/constants.py:23`, `backend/app/runs/graph.py:267`, `backend/app/exports/generators/common.py:14`). A2/A3-Agenten sind teilweise vorhanden, aber A2-Drafting im Hauptgraphen ist deaktiviert und A3 läuft nur im Recheck unter Policy-/Provider-Bedingungen (`backend/app/runs/graph.py:191`, `backend/app/runs/graph.py:224`, `backend/app/review/recheck.py:145`).

## Was ist die App?

Die Anwendung ist ein assistiver Arbeitsplatz für Innosuisse-/Innolink-Antragsteams. Im Code belegt sind Projektverwaltung, Quellenimport, Analyse-Runs, Requirements/Rules, Evidence Anchors/Links, Feldentwürfe, Review/Approval, Exporte und manuelle Innolink-Copy-Ansicht (`backend/app/main.py:30`, `app/quellen/page.tsx:559`, `components/editor/live-editor.tsx:101`, `components/export/live-export.tsx:91`, `components/portal-transfer/portal-transfer.tsx:32`).

Nicht im Code gefunden ist eine automatische Innolink-Portalübertragung oder ein Submit-Connector. Die Copy-Logik ist rein clientseitig und kopiert in die lokale Zwischenablage (`lib/portal-transfer.ts:80`, `components/portal-transfer/field-transfer-card.tsx:60`).

## Use Case

Der belegte Use Case ist: Projekt anlegen, Quellen erfassen, Analyse-Run starten, Anforderungen und Evidence prüfen, Feldentwürfe bearbeiten, Review/Recheck/Approval durchführen, Exporte erzeugen und unterstützte Feldtexte manuell nach Innolink kopieren (`app/quellen/page.tsx:420`, `backend/app/runs/graph.py:349`, `backend/app/review/service.py:405`, `backend/app/exports/service.py:39`, `components/export/live-export.tsx:433`).

## Aktueller Reifegrad

| Bereich | Status | Codebeleg |
|---|---|---|
| Projekt-/Quellen-/Run-Basis | Aktuell implementiert | `backend/app/api/projects.py:21`, `backend/app/api/sources.py:80`, `backend/app/api/runs.py:43` |
| Deterministische Requirements/Rules | Aktuell implementiert | `backend/app/registry/loader.py:1`, `backend/app/runs/graph.py:153` |
| Evidence Discovery/Verification | Aktuell implementiert | `backend/app/runs/graph.py:109`, `backend/app/runs/graph.py:136` |
| PortalFieldDrafts | Aktuell implementiert für M6-Teilmenge | `backend/app/registry/loader.py:94`, `backend/app/repositories/drafts.py:122` |
| A1/A2/A3 LLM-Agentik | Teilweise implementiert | `backend/app/agents/schemas.py:35`, `backend/app/agents/a2_fields.py:23`, `backend/app/agents/critic_review.py:145` |
| Innolink Copy-Paste | Teilweise implementiert, clientseitig | `lib/portal-transfer.ts:1`, `components/portal-transfer/portal-transfer.tsx:46` |
| Automatisches Innolink-Submit | Nicht implementiert | Keine Route/Provider-Funktion gefunden; Copy-Hinweis in `lib/export-view.ts:21` |
| Production Cloud/Azure | Geplant/Zielarchitektur | `final_backend_contracts_v1_1/data_policy_v1_1.yaml:89`, keine Azure-Provider-Klasse in `backend/app/agents/providers/*` |

## Empfohlene Lesereihenfolge für Fable 5

1. `00_FABLE_CONTEXT_INDEX.md`
2. `13_FABLE_REVIEW_BRIEF.md`
3. `01_SYSTEM_OVERVIEW.md`
4. `02_REPOSITORY_AND_STACK_MAP.md`
5. `05_DOMAIN_MODEL_AND_DATA_FLOW.md`
6. `06_INNOLINK_FIELD_WORKFLOW.md`
7. `07_AGENT_AND_LLM_ARCHITECTURE.md`
8. `08_PRIVACY_SECURITY_AND_GOVERNANCE.md`
9. `09_REVIEW_QUALITY_AND_RELIABILITY.md`
10. `10_EXPORT_AND_INNOLINK_TRANSFER.md`
11. `12_CURRENT_LIMITATIONS_AND_CRITICAL_GAPS.md`
12. Detaildokumente `03`, `04`, `11` nach Bedarf.

## Review-Auftrag an Fable 5

Fable soll beurteilen, ob die implementierte Architektur belastbar genug für den Zielzustand "Innolink-Antragsarbeitsplatz mit manueller Copy-Paste-Übernahme" ist. Schwerpunkt sollten Datenmodell-Lücken, Portal-Field-Abdeckung, Review-/Export-Gates, Datenschutz-Policy, Agent-Provider-Grenzen und Refactoring-Slices sein (`backend/app/review/service.py:364`, `backend/app/exports/eligibility.py:3`, `backend/app/security/data_class.py:1`, `backend/app/agents/gateway.py:1`).

Fable soll nicht vorschlagen, automatisch in Innolink einzureichen oder KI-Ausgaben ohne menschliche Freigabe zu übernehmen. Beides ist im Code nicht als Zielverhalten implementiert (`lib/export-view.ts:21`, `backend/app/review/service.py:405`).

## Wichtigste offene Architekturfragen

| Frage | Status im Code | Codebeleg |
|---|---|---|
| Soll die Portal-Field-Registry vollständig in Draft/Copy unterstützt werden? | Teilweise implementiert: 161 Registry-Felder, aber nur eine gefilterte M6-Draft-Teilmenge wird erzeugt. | `final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml:2038`, `backend/app/registry/loader.py:94` |
| Ist Copy trotz Blockern erlaubt? | Ja, Warnungen sind advisory; Copy wird clientseitig nicht blockiert. | `lib/portal-transfer.ts:80`, `components/portal-transfer/field-transfer-card.tsx:76` |
| Werden Copy-Overrides auditiert? | Nicht gefunden; Copy-Log ist session-only. | `components/portal-transfer/portal-transfer.tsx:46` |
| Werden Intake-Partner und Budget strukturiert vollständig erfasst? | Teilweise; Partner-API existiert, Budget ist nur grob am Project-Modell/Intake erkennbar. | `backend/app/api/partners.py:38`, `backend/app/db/models.py:92`, `components/intake/intake-form.tsx:670` |
| Ist Azure Provider produktiv vorhanden? | Nicht implementiert; nur Policy/Zielarchitektur. | `final_backend_contracts_v1_1/data_policy_v1_1.yaml:89`, `backend/app/agents/gateway.py:107` |
| Ist die Run-State-Machine echte HITL-Loop? | Teilweise; Graph läuft bis completed, Review/Recheck/Approval laufen danach über APIs. | `backend/app/runs/graph.py:267`, `backend/app/review/recheck.py:1` |

