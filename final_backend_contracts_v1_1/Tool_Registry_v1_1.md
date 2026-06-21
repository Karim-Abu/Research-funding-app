# Tool Registry v1.1

- **Version:** 1.1.0
- **Datum:** 2026-06-21
- **Status:** ready for implementation
- **Maschinenlesbare Fassung:** `tools_v1_1.yaml`
- **Tools:** 19

## Zweck

Die Registry definiert ausschliesslich kontrollierte Agent-/Orchestrator-Grenzen. Interne Repository-Funktionen ohne Sicherheitsgrenze sind keine Tools.

## Sicherheitsmodell

- Websuche und URL-Fetch sind **orchestrator-only**.
- Agenten erhalten keine Netzwerkcredentials.
- Effektive Berechtigung ist die Schnittmenge aus AgentProfile und ToolDefinition.
- Jeder Call nutzt kanonische Controls, versionierte Schemas, Timeout, Call-Limit und Audit.
- Unbekannte Tools, Schemas oder Controls stoppen den Backend-Start.
- Nicht erfolgreiche Retrieval-/Rechercheaufrufe erzeugen sichtbare OpenIssues statt erfundener Inhalte.

## Toolübersicht

| Tool | Caller | Netzwerk | Side Effect | Status |
|---|---|---|---|---|
| `source_ingest_file` | orchestrator | none | writes_local_storage_and_database | beta_active |
| `source_ingest_text` | orchestrator | none | writes_local_storage_and_database | beta_active |
| `source_normalize` | orchestrator | none | writes_source_version_and_fragments | beta_active |
| `fetch_validated_public_url` | orchestrator | firecrawl_cloud_or_future_approved_fetcher | external_network_and_local_cache_write | beta_active_conditional |
| `search_public_professional_sources` | orchestrator | firecrawl_search_and_allowlisted_fetch | external_network_and_local_cache_write | beta_active_conditional |
| `retrieve_source_fragments` | A1.project_fact_extraction, A1.evidence_candidate_mapping, A1.public_competence_research, A2.*, A3.*, orchestrator | none | read_only | beta_active |
| `lookup_requirement_definition` | A1.project_fact_extraction, A1.evidence_candidate_mapping, A1.public_competence_research, A2.*, A3.*, orchestrator | none | read_only | beta_active |
| `lookup_portal_field_profile` | A1.project_fact_extraction, A1.evidence_candidate_mapping, A1.public_competence_research, A2.*, A3.*, orchestrator | none | read_only | beta_active |
| `retrieve_confirmed_project_facts` | A2.*, A3.*, orchestrator | none | read_only | beta_active |
| `retrieve_verified_evidence` | A2.*, A3.*, orchestrator | none | read_only | beta_active |
| `verify_evidence_quote` | orchestrator | none | writes_evidence_candidate_or_anchor_status | beta_active |
| `run_deterministic_rules` | orchestrator | none | writes_rule_results_and_open_issues | beta_active |
| `retrieve_rule_results` | A3.*, orchestrator | none | read_only | beta_active |
| `retrieve_current_drafts` | A3.*, orchestrator | none | read_only | beta_active |
| `create_export_artifact` | orchestrator | none | writes_export_file_and_database_record | beta_active |
| `retrieve_research_results` | A1.public_competence_research, orchestrator | none | read_only | beta_active |
| `retrieve_structured_project_data` | A1.*, A2.*, A3.*, orchestrator | none | read_only | beta_active |
| `retrieve_open_issues` | A2.*, A3.*, orchestrator | none | read_only | beta_active |
| `run_targeted_rechecks` | orchestrator | provider_only_when_semantic_recheck_requested_and_policy_allows | writes_rule_results_assessments_findings_and_open_issues | beta_active |

## Wichtige Änderungen gegenüber v1

1. `fetch_allowlisted_public_url` wurde zu `fetch_validated_public_url`.
2. Webtools sind nur noch für den Orchestrator zugelassen.
3. A1-Read-Tools sind für alle drei A1-Profile symmetrisch freigegeben.
4. Nicht-kanonische Sensitivität `internal_with_public_confirmed_query` wurde entfernt.
5. Neu:
   - `retrieve_research_results`
   - `retrieve_structured_project_data`
   - `retrieve_open_issues`
   - `run_targeted_rechecks`
6. Technische Uploadgrösse muss als Deployment-Konfiguration existieren; kein fachliches Limit wird erfunden.

## Tool-Call-Lifecycle

```text
Caller
→ Registry Lookup
→ gegenseitige Profil-/Tool-Autorisierung
→ Data Policy
→ Input Schema
→ Security/Cost/Version Controls
→ Execution
→ Output Schema
→ Audit + ControlResult (+ UsageRecord bei extern)
```
