# Privacy, Security And Governance

## Datenklassifikation

Der Contract `DataClassification` hat fünf Dimensionen: `sensitivity`, `origin`, `processing_mode`, `web_research_mode`, `nda_applies` (`backend/app/contracts/classification.py:1`, `backend/app/contracts/classification.py:9`). Die UI spiegelt diese Struktur teilweise über `lib/data-classification.ts` (`lib/data-classification.ts:19`).

Zusätzlich gibt es code-intern D0-D3/UNKNOWN Labels: `D0_PUBLIC`, `D1_INTERNAL`, `D2_CONFIDENTIAL_IDEA`, `D3_NDA_BLOCKED`, `UNKNOWN` (`backend/app/security/data_class.py:29`, `lib/data-class.ts:10`). `UNKNOWN` und D3 blockieren externe Tools fail-closed (`backend/app/security/data_class.py:74`, `backend/tests/test_data_class.py:31`).

## Projekt-, Quellen-, Feld-, Payload-, Query- und Output-Ebene

| Ebene | Status | Codebeleg |
|---|---|---|
| Projektklassifikation | Implementiert | `backend/app/db/models.py:103`, `backend/app/contracts/project.py:20` |
| Quellenklassifikation | Implementiert mit Effective Merge | `backend/app/api/sources.py:163`, `backend/app/policy/classification.py:28` |
| Feldklassifikation | Teilweise | PortalField hat Evidence/Support Metadata, aber keine eigene DataClassification DB-Spalte gefunden (`backend/app/registry/loader.py:85`) |
| Provider Payload | Implementiert als Policy/Gateway-Gate | `backend/app/agents/data_policy.py:34`, `backend/app/agents/gateway.py:241` |
| Search Query | Implementiert mit D0-D3/UNKNOWN und Firewall | `backend/app/security/search_query_firewall.py:182`, `backend/app/security/approval_service.py:92` |
| Output/Export | Teilweise; Export snapshot hat effective classification | `backend/app/db/models.py:1026`, `backend/app/exports/snapshot.py:276` |

## Effective Data Classification

Projekt- und Source-Klassifikation werden nach "most restrictive input wins" zusammengeführt; ein Downgrade-Versuch wird markiert (`backend/app/policy/classification.py:1`, `backend/app/policy/classification.py:28`, `backend/app/policy/classification.py:36`). Quellen-Upload und Textquelle nutzen diese Funktion (`backend/app/api/sources.py:163`, `backend/app/sources/service.py:68`).

## Cloud/Webresearch Policy

Agent Data Policy blockiert NDA/confidential und internal ohne institutionell genehmigte Route (`backend/app/agents/data_policy.py:49`, `backend/app/agents/data_policy.py:55`, `backend/app/agents/data_policy.py:62`). Web Research Policy ist beta-scope public/synthetic; internal/confidential/NDA/missing werden im Policy-Modul blockiert, außer der separate sanitized-query Pfad wird im Research-Service genutzt (`backend/app/research/policy.py:5`, `backend/app/research/service.py:134`).

## Search Query Firewall

Die Firewall baut ein Projekt-/Partner-/Budget-Lexikon für D1/D2, entfernt vertrauliche Begriffe, blockiert D3/UNKNOWN und verlangt für D1/D2 sanitized approval (`backend/app/security/search_query_firewall.py:100`, `backend/app/security/search_query_firewall.py:221`, `backend/app/security/search_query_firewall.py:267`, `backend/app/security/search_query_firewall.py:280`). Raw Query wird gehasht und nicht persistiert (`backend/app/security/approval_service.py:3`, `backend/app/security/approval_service.py:128`).

## Firecrawl/Websearch-Schutz

Firecrawl ist env-gated und ohne Key unavailable (`backend/app/research/providers/firecrawl.py:29`, `backend/app/research/providers/firecrawl.py:32`). URL-Safety blockiert nicht öffentliche/private Hosts und DNS-Unsicherheit (`backend/app/research/url_safety.py:54`, `backend/app/research/url_safety.py:97`). D1/D2 Live-Web-Provider ist zusätzlich über `d2_web_research_enabled` gesperrt, wenn kein Fake Provider genutzt wird (`backend/app/research/executor.py:145`).

## No-Raw-Logging Guard

Redaction-Helper prüfen im Dev/Test, dass Raw Query nicht in Audit/Control Details landet; in Production ist der Guard absichtlich no-op, damit Logging-Guard Live-Requests nicht bricht (`backend/app/security/redaction.py:3`, `backend/app/security/redaction.py:50`). Das bedeutet: Schutz ist implementiert, aber Production-Enforcement ist teilweise.

## Audit Logging

`AuditEvent` existiert als DB-Modell (`backend/app/db/models.py:118`). Viele Aktionen schreiben Audit Events: Upload, Run, Review, Approval, Export, Agent Invocation, Firewall (`backend/app/api/sources.py:183`, `backend/app/runs/graph.py:182`, `backend/app/review/package.py:161`, `backend/app/review/service.py:415`, `backend/app/exports/service.py:136`, `backend/app/agents/gateway.py:170`, `backend/app/security/approval_service.py:83`).

## Auth / Permissions / Capabilities

Server-side Sessions verwenden random Session IDs und CSRF Token (`backend/app/security/sessions.py:1`, `backend/app/security/sessions.py:16`). Cookies sind `HttpOnly` und verwenden Settings für `SameSite`/`secure` (`backend/app/api/auth.py:19`, `backend/app/api/auth.py:26`). Unsafe Methods prüfen Origin und CSRF (`backend/app/security/deps.py:65`). Rollen-Guard existiert (`backend/app/security/deps.py:89`). Capabilities werden über `/capabilities` geliefert (`backend/app/api/capabilities.py:13`).

## File Upload Security

Upload prüft Dateianzahl, Größe, Gesamtsumme und Typ-Signatur (`backend/app/api/sources.py:114`, `backend/app/api/sources.py:120`, `backend/app/ingestion/signatures.py:98`). PDF/DOCX/TXT werden deterministisch geparst; ausführbare Inhalte werden abgelehnt (`backend/app/ingestion/signatures.py:31`, `backend/app/ingestion/signatures.py:101`). Local Storage nutzt generierte traversal-safe Keys (`backend/app/storage/local.py:1`).

## Secrets Handling

API Keys sind Settings-Felder ohne echte Defaultwerte (`backend/app/config/settings.py:83`, `backend/app/config/settings.py:84`, `backend/app/config/settings.py:104`). Provider-Adapter importieren Clients lazy und loggen keine Keys (`backend/app/agents/providers/openai.py:1`, `backend/app/research/providers/firecrawl.py:46`). Seed-Password-Defaults sind im Settings-Code vorhanden, werden hier nicht ausgegeben (`backend/app/config/settings.py:125`).

## Production Gaps

| Thema | Status | Codebeleg |
|---|---|---|
| Key Vault | Nicht gefunden | Keine Key-Vault-Integration gefunden |
| Managed Identity | Nicht gefunden | Keine Managed-Identity-Integration gefunden |
| Private Endpoint | Nicht gefunden | Keine Azure-Netzwerk-Integration gefunden |
| Azure Regional Deployment | Geplant, nicht implementiert | `final_backend_contracts_v1_1/data_policy_v1_1.yaml:89` |
| Modified Abuse Monitoring / ContentLogging=false | Nicht implementiert im Provider-Code | OpenAI/Anthropic direct adapters ohne solche Einstellungen (`backend/app/agents/providers/openai.py:27`) |
| RLS/Mandantentrennung | Teilweise über `workspace_id`, keine DB-RLS | Workspace-scoped queries (`backend/app/security/approval_service.py:146`) |
| Backups/Restore | Nicht gefunden | Keine Backup-Komponente gefunden |
| Observability | Teilweise Logging/Audit, kein Monitoring Stack | `backend/app/config/logging.py:1`, `backend/app/db/models.py:118` |

