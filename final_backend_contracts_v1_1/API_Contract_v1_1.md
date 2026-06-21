# API Contract v1.1

- **Version:** 1.1.0
- **Datum:** 2026-06-21
- **Status:** ready for implementation
- **Maschinenlesbarer Vertrag:** `openapi-v1_1.yaml`
- **Transport:** HTTPS REST/JSON, Multipart für Uploads, Binärdownload
- **Fortschritt:** Polling; SSE ist Post-Beta

## Grundentscheidungen

1. Das Frontend ruft fachliche Ressourcen auf, nie Agenten oder Tools.
2. FastAPI ist die einzige Backend-Grenze.
3. Vorprovisionierte Nutzer:innen verwenden Secure/HttpOnly/SameSite-Lax Session-Cookies.
4. Mutierende Requests benötigen CSRF/Origin-Prüfung.
5. Lange Aktionen liefern `202` und `AsyncOperation`.
6. Idempotency-Key ist für Run, Research, Recheck, Redraft, Resume und Export Pflicht.
7. Draft- und strukturierte Daten verwenden optimistische Versionskontrolle.
8. Öffentliche Webrecherche ist explizit und orchestrator-controlled.
9. Post-Beta-Endpunkte sind nur Metadaten und nicht für Client-Codegen aktiv.
10. Das Review-/Approval-Protokoll erzwingt Recheck vor Freigabe.

## Rollen

### `member`

- Projektinhalte und strukturierte Antragsdaten bearbeiten,
- Quellen hinzufügen,
- Evidence/Requirements/Drafts prüfen,
- Human Decisions und Review-Freigaben erteilen,
- Exporte erzeugen.

### `lead_admin`

Zusätzlich:

- Cloud-Processing Confirmation,
- Reklassifizierung,
- Limits und Dienste,
- öffentliche Research Tasks,
- optionaler Final Quality Review.

## Strukturierter Antrag

Die API enthält Ressourcen für:

- ProjectDates,
- WorkPackages,
- Milestones,
- PlannedHours,
- BudgetPlan,
- RiskRegister,
- erweiterte Partnerdaten.

Damit können deterministische Regeln die vollständigen strukturierten Eingaben prüfen, statt Zahlen oder Zeitpläne aus Freitext abzuleiten.

## Reviewablauf

```text
PATCH Draft / Structured Data
→ recheck_required
→ POST /runs/{run_id}/rechecks
→ aktualisiertes ReviewPackage
→ POST /runs/{run_id}/approvals
→ POST /runs/{run_id}/resume
```

Approval ist bei veraltetem ReviewPackage, ausstehendem Recheck oder Blockern nicht zulässig.

## Human Decisions

`HumanDecisionCreate` ist eine diskriminierte Union pro Target-Typ. Reklassifizierung ist aus dem generischen Endpoint entfernt und bleibt ein separater Lead-Admin-Policy-Endpunkt.

## Evidence und Open Issues

- RequirementAssessment und PortalFieldDraft liefern `EvidenceLink[]`, nicht nur Anchor-IDs.
- EvidenceAnchor enthält Source-Displaydaten, Offsets, Match-Score, Coverage und Normalizer-Version.
- ReviewPackage enthält OpenIssues, Recheckstatus, ReviewPackage-Version und Approval-Scope-Hash.

## Öffentliche Recherche

- Start nur durch `lead_admin`.
- Results enthalten ProfessionalEvidence, PartnerRoleSuggestions und Identity-Match-Status.
- Ergebnisse werden erst nach explizitem Import zu SourceVersions.
- Keine automatische Partnerauswahl oder Kontaktaufnahme.

## Technische Uploadgrenze

Es gibt kein fachliches unbegrenztes Uploadversprechen. `max_upload_bytes` ist eine verpflichtende Deployment-Konfiguration und wird über `/capabilities` publiziert. Ein fehlender Wert ist vor Deployment ein Konfigurationsfehler.

## Endpunkte

| Bereich | Methode | Pfad | Zweck | Rollen |
|---|---|---|---|---|
| ApplicationData | `DELETE` | `/api/v1/milestones/{milestone_id}` | Delete milestone | member,lead_admin |
| ApplicationData | `PATCH` | `/api/v1/milestones/{milestone_id}` | Update milestone | member,lead_admin |
| ApplicationData | `GET` | `/api/v1/projects/{project_id}/application-structure` | Get structured application data | member,lead_admin |
| ApplicationData | `GET` | `/api/v1/projects/{project_id}/budget-plan` | Get budget plan | member,lead_admin |
| ApplicationData | `PATCH` | `/api/v1/projects/{project_id}/budget-plan` | Update budget plan | member,lead_admin |
| ApplicationData | `GET` | `/api/v1/projects/{project_id}/milestones` | List milestones | member,lead_admin |
| ApplicationData | `POST` | `/api/v1/projects/{project_id}/milestones` | Create milestone | member,lead_admin |
| ApplicationData | `GET` | `/api/v1/projects/{project_id}/planned-hours` | Get planned hours | member,lead_admin |
| ApplicationData | `PATCH` | `/api/v1/projects/{project_id}/planned-hours` | Update planned hours | member,lead_admin |
| ApplicationData | `GET` | `/api/v1/projects/{project_id}/project-dates` | Get project dates | member,lead_admin |
| ApplicationData | `PATCH` | `/api/v1/projects/{project_id}/project-dates` | Update project dates | member,lead_admin |
| ApplicationData | `GET` | `/api/v1/projects/{project_id}/risk-register` | Get risk register | member,lead_admin |
| ApplicationData | `PATCH` | `/api/v1/projects/{project_id}/risk-register` | Update risk register | member,lead_admin |
| ApplicationData | `GET` | `/api/v1/projects/{project_id}/work-packages` | List work packages | member,lead_admin |
| ApplicationData | `POST` | `/api/v1/projects/{project_id}/work-packages` | Create work package | member,lead_admin |
| ApplicationData | `DELETE` | `/api/v1/work-packages/{work_package_id}` | Delete work package | member,lead_admin |
| ApplicationData | `PATCH` | `/api/v1/work-packages/{work_package_id}` | Update work package | member,lead_admin |
| Audit | `GET` | `/api/v1/runs/{run_id}/audit` | List audit events | member,lead_admin |
| Auth | `GET` | `/api/v1/me` | Get current user | member,lead_admin |
| Auth | `DELETE` | `/api/v1/session` | Delete session | member,lead_admin |
| Auth | `GET` | `/api/v1/session` | Get current session and refresh CSRF token | member,lead_admin |
| Auth | `POST` | `/api/v1/session` | Create session |  |
| Controls | `GET` | `/api/v1/runs/{run_id}/controls` | List control results | lead_admin |
| Evidence | `GET` | `/api/v1/runs/{run_id}/evidence` | List evidence anchors | member,lead_admin |
| Evidence | `POST` | `/api/v1/runs/{run_id}/fields/{field_id}/evidence-links` | Link evidence to current field draft | member,lead_admin |
| Evidence | `DELETE` | `/api/v1/runs/{run_id}/fields/{field_id}/evidence-links/{evidence_link_id}` | Remove evidence link | member,lead_admin |
| Exports | `GET` | `/api/v1/exports/{export_id}` | Get export | member,lead_admin |
| Exports | `GET` | `/api/v1/exports/{export_id}/download` | Download export | member,lead_admin |
| Exports | `POST` | `/api/v1/runs/{run_id}/exports` | Create export | member,lead_admin |
| Fields | `GET` | `/api/v1/runs/{run_id}/fields` | List portal field drafts | member,lead_admin |
| Fields | `GET` | `/api/v1/runs/{run_id}/fields/{field_id}` | Get portal field draft | member,lead_admin |
| Fields | `PATCH` | `/api/v1/runs/{run_id}/fields/{field_id}` | Update portal field draft | member,lead_admin |
| Fields | `POST` | `/api/v1/runs/{run_id}/fields/{field_id}/redrafts` | Start targeted redraft | member,lead_admin |
| Infrastructure | `GET` | `/api/v1/capabilities` | Get API capabilities | member,lead_admin |
| Infrastructure | `GET` | `/api/v1/health` | Health check |  |
| Infrastructure | `GET` | `/api/v1/operations/{operation_id}` | Get async operation | member,lead_admin |
| Infrastructure | `GET` | `/api/v1/services/availability` | Get service availability | member,lead_admin |
| Infrastructure | `POST` | `/api/v1/services/{service}/test` | Test configured service connection | lead_admin |
| Partners | `DELETE` | `/api/v1/partners/{partner_id}` | Delete partner | member,lead_admin |
| Partners | `PATCH` | `/api/v1/partners/{partner_id}` | Update partner | member,lead_admin |
| Partners | `GET` | `/api/v1/projects/{project_id}/partners` | List partners | member,lead_admin |
| Partners | `POST` | `/api/v1/projects/{project_id}/partners` | Create partner | member,lead_admin |
| Projects | `GET` | `/api/v1/projects` | List projects | member,lead_admin |
| Projects | `POST` | `/api/v1/projects` | Create project | member,lead_admin |
| Projects | `GET` | `/api/v1/projects/{project_id}` | Get project | member,lead_admin |
| Projects | `PATCH` | `/api/v1/projects/{project_id}` | Update project | member,lead_admin |
| Projects | `POST` | `/api/v1/projects/{project_id}/processing-confirmations` | Create one-run internal cloud processing confirmation | lead_admin |
| Projects | `POST` | `/api/v1/projects/{project_id}/reclassifications` | Create audited data reclassification | lead_admin |
| Requirements | `GET` | `/api/v1/runs/{run_id}/requirements` | List requirement assessments | member,lead_admin |
| Research | `GET` | `/api/v1/projects/{project_id}/research-results` | List public research results | member,lead_admin |
| Research | `POST` | `/api/v1/projects/{project_id}/research-tasks` | Start explicit public research task | lead_admin |
| Research | `POST` | `/api/v1/research-results/{result_id}/import` | Import research result as source | member,lead_admin |
| Research | `GET` | `/api/v1/research-tasks/{task_id}` | Get research task | member,lead_admin |
| Review | `POST` | `/api/v1/runs/{run_id}/approvals` | Create review approval | member,lead_admin |
| Review | `POST` | `/api/v1/runs/{run_id}/final-quality-review` | Start optional final quality review | lead_admin |
| Review | `POST` | `/api/v1/runs/{run_id}/human-decisions` | Create human decision | member,lead_admin |
| Review | `POST` | `/api/v1/runs/{run_id}/rechecks` | Recheck after human edits | member,lead_admin |
| Review | `GET` | `/api/v1/runs/{run_id}/review` | Get review package | member,lead_admin |
| Runs | `GET` | `/api/v1/projects/{project_id}/runs` | List project runs | member,lead_admin |
| Runs | `POST` | `/api/v1/projects/{project_id}/runs` | Start analysis run | member,lead_admin |
| Runs | `GET` | `/api/v1/runs/{run_id}` | Get analysis run | member,lead_admin |
| Runs | `POST` | `/api/v1/runs/{run_id}/cancel` | Cancel analysis run | member,lead_admin |
| Runs | `POST` | `/api/v1/runs/{run_id}/resume` | Finalize run after current review approval | member,lead_admin |
| Sources | `GET` | `/api/v1/projects/{project_id}/sources` | List project sources | member,lead_admin |
| Sources | `POST` | `/api/v1/projects/{project_id}/sources/files` | Upload source files | member,lead_admin |
| Sources | `POST` | `/api/v1/projects/{project_id}/sources/text` | Create text source | member,lead_admin |
| Sources | `POST` | `/api/v1/projects/{project_id}/sources/url` | Import public URL source | member,lead_admin |
| Sources | `DELETE` | `/api/v1/sources/{source_id}` | Delete source | member,lead_admin |
| Sources | `GET` | `/api/v1/sources/{source_id}` | Get source | member,lead_admin |
| Usage | `GET` | `/api/v1/projects/{project_id}/limits` | Get project run limits | member,lead_admin |
| Usage | `PATCH` | `/api/v1/projects/{project_id}/limits` | Update project run limits | lead_admin |
| Usage | `GET` | `/api/v1/projects/{project_id}/usage` | Get project usage | member,lead_admin |

## Fehlervertrag

RFC-7807-artiges `Problem` mit:

- `type`
- `title`
- `status`
- `detail`
- `code`
- `correlation_id`
- optionalen Field Errors

Wichtige Codes:

- 401 Auth,
- 403 Rolle/Policy,
- 409 aktiver Run/Version/Recheck/Scope-Konflikt,
- 413 technische Uploadgrenze,
- 415 Content Type,
- 422 Schema/Blocker,
- 429 Kosten/Rate,
- 503 Provider unavailable.

## Sicherheit

- keine Secrets im Response,
- keine Provider-Rohfehlermeldungen,
- serverseitige Rollenprüfung,
- Data Policy vor externen Aktionen,
- URL/SSRF/Redirect-Kontrollen,
- Audit für alle mutierenden Governance-Aktionen,
- geplante Endpunkte nicht aktiv.
