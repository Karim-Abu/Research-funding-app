# Innolink Field Workflow

## Modellierung von Innolink im Code

Innolink-Felder sind primär als Contract-Registry in `final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml` modelliert. Der Backend-Loader liest daraus `portal_fields` in `PortalFieldDef` und validiert sie fail-closed (`backend/app/registry/loader.py:85`, `backend/app/registry/loader.py:235`). Feldentwürfe werden nicht für alle Registry-Felder erzeugt, sondern für `m6_draft_fields()` (`backend/app/registry/loader.py:131`).

Die fünf erkannten Hauptbereiche sind in Registry/Copy-Code erkennbar: Introduction, Organisations & People, Value Creation, Solution, Project Setup; Summary & Submit ist in der Registry vorhanden, aber nicht als Draft-/Copy-Section im UI-Mapping (`final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml:500`, `final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml:5817`, `lib/portal-transfer.ts:11`).

## Field Registry Umfang

| Kennzahl | Wert | Codebeleg |
|---|---:|---|
| Portal Field Registry Einträge | 161 | `final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml`, Pattern `- field_id:` |
| Raw `support_mode: draft_text` + `agent_writable: true` | 18 | `final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml:2038`, `final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml:5440` |
| Backend M6 Draft Teilmenge | 8 abgeleitet aus Loader-Filtern | `backend/app/registry/loader.py:94`, `backend/app/registry/loader.py:105` |
| A2-enabled Felder | 2 | `backend/app/agents/a2_fields.py:23` |

Die M6-Teilmenge filtert `agent_writable`, `support_mode == draft_text`, `narrative_text|composite_editor`, keine `[]`-Pfade und keine Prefixe `PS.MATERIAL_POSITION.*`/`PS.CASH_CONTRIBUTION.*` (`backend/app/registry/loader.py:94`, `backend/app/registry/loader.py:105`).

## Unterstützte Draft-/Copy-Felder

| field_id | Section | Status | Bemerkung |
|---|---|---|---|
| `INTRO.APP.NAME` | Introduction | Unterstützt | Singleton narrative text; Registry raw draft_text (`final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml:2038`) |
| `INTRO.APP.NAME_EN` | Introduction | Unterstützt | Singleton narrative text (`final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml:2042`) |
| `INTRO.APP.ABSTRACT` | Introduction | Unterstützt | 300 Zeichen-Regel in Registry/Review (`final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml:2134`) |
| `INTRO.APP.EXECUTIVE_SUMMARY` | Introduction | Unterstützt | 2000 Zeichen-Regel (`final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml:2159`) |
| `ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS` | Organisations & People | Unterstützt | Singleton, Partner/Independence-Kontext (`final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml:3420`) |
| `VC.BUSINESS_TARGETS_MODEL.EDITOR` | Value Creation | Unterstützt, A2-enabled | Composite editor (`backend/app/agents/a2_fields.py:25`) |
| `SOL.INNOVATION_SOLUTION.EDITOR` | Solution | Unterstützt, A2-enabled | Composite editor (`backend/app/agents/a2_fields.py:24`) |
| `PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION` | Project Setup | Unterstützt | Singleton, management explanation (`final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml:4546`) |

Raw draft_text-Felder mit `structured_data_path` über `[]` oder Budget-/Cash-Prefix werden in der M6-Draft-Logik nicht unterstützt (`backend/app/registry/loader.py:94`, `backend/app/registry/loader.py:105`).

## Nicht unterstützte Innolink-Bereiche

Die UI nennt strukturelle/repeated Bereiche explizit als nicht abgedeckt: Work Packages, Meilensteine, Partner-Stundentabellen, Budget-/Finanzierungsplan, Lohnkosten, Materialkosten, Eigenleistungs-/Barbeiträge, Datei-Uploads, Checkbox-/Dropdown-Auswahlen ohne Entwurfstext (`lib/portal-transfer.ts:112`).

Summary & Submit ist in der Registry enthalten, aber nicht in `SECTION_LABELS` der Copy-Ansicht (`final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml:5817`, `lib/portal-transfer.ts:11`). Automatisches Submit ist nicht implementiert.

## Copy-Paste aktuell

Die Copy-Ansicht gruppiert Felder nach Prefix und verwendet die Reihenfolge aus `listFields`/Registry (`lib/portal-transfer.ts:53`). `FieldTransferCard` kopiert Plain Text oder optional formatiert in die Zwischenablage (`components/portal-transfer/field-transfer-card.tsx:60`, `components/portal-transfer/field-transfer-card.tsx:202`). Die Copy-Historie ist nur Session-State und nicht persistiert (`components/portal-transfer/portal-transfer.tsx:46`).

## Copy Readiness Regeln

`fieldWarnings` erzeugt Warnungen für Platzhalter/offene Angaben, Zeichenlimitüberschreitung und nicht aktuelle Review-Freigabe/Blocker (`lib/portal-transfer.ts:81`, `lib/portal-transfer.ts:98`). `fieldReadinessRows` priorisiert Platzhalter, fehlende Belege, stale/blocker und kopierbereit (`lib/export-view.ts:140`, `lib/export-view.ts:142`).

Wichtig: Copy wird nicht technisch blockiert. Der Code sagt ausdrücklich, Warnungen seien advisory (`lib/portal-transfer.ts:80`). Bei Warnungen öffnet die Karte eine Bestätigung und erlaubt danach Copy (`components/portal-transfer/field-transfer-card.tsx:76`, `components/portal-transfer/field-transfer-card.tsx:136`).

## Export aktuell

Backend-Exporte sind DOCX, Markdown und Technical Evidence (`backend/app/exports/__init__.py:15`). Sie verwenden einen eingefrorenen Snapshot und markieren nicht freigegebene Stände als Draft (`backend/app/exports/snapshot.py:182`, `backend/app/exports/eligibility.py:27`, `backend/app/exports/generators/common.py:14`). Der UI-Export zeigt zusätzlich die Innolink-Kopieransicht als Tab/Abschnitt (`components/export/live-export.tsx:97`, `components/export/live-export.tsx:433`).

## Blocker/Platzhalter/Stale Verhalten

| Verhalten | Status | Codebeleg |
|---|---|---|
| Approval wird durch Platzhalter blockiert | Implementiert | `backend/app/review/service.py:345` |
| Approval wird durch Zeichenlimit blockiert | Implementiert | `backend/app/review/service.py:347` |
| Approval wird durch stale Evidence Link blockiert | Implementiert | `backend/app/review/service.py:351` |
| Approval wird durch Recheck-Pflicht blockiert | Implementiert | `backend/app/review/service.py:369` |
| Export als Draft trotz Blockern möglich | Implementiert | `backend/app/exports/eligibility.py:6` |
| Copy trotz Warnungen möglich | Implementiert | `lib/portal-transfer.ts:80` |
| Copy/Override auditiert | Nicht gefunden | Copy-State nur session-only (`components/portal-transfer/portal-transfer.tsx:46`) |

## Gaps gegenüber echtem Innolink-Arbeitsplatz

- Strukturierte Work Packages, Milestones, Budget- und Partner-Stunden werden nicht als vollständige DB-Workflows unterstützt (`lib/portal-transfer.ts:112`, `final_backend_contracts_v1_1/Frontend_API_Mapping_v1_1.md:9`).
- Summary & Submit ist nicht als App-Submit-Schritt implementiert (`final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml:5841`).
- Copy readiness ist UI-advisory, nicht serverseitig/auditierbar (`lib/portal-transfer.ts:80`).
- Innolink-PDF-Import oder automatisches Portal-Mapping wurde nicht gefunden.

