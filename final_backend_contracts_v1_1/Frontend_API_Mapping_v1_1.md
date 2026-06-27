# Frontend–API Mapping v1.1

| Screen/Bereich | UI-Aktion | Endpoint | Erwartete Reaktion |
|---|---|---|---|
| Login | Anmelden | `POST /api/v1/session` | HTTP-only Session + CSRF; Dashboard |
| Dashboard | Projekte laden | `GET /api/v1/projects` | Karten und nächste Aktion aus Run-/Projektstatus |
| Intake | Projekt anlegen | `POST /api/v1/projects` | Projekt; danach strukturierte Daten/Quellen |
| Intake | Partner pflegen | Partner-Endpunkte | versionierte Partnerdaten; keine LLM-Invention |
| Intake/Project Setup | Termine | `GET/PATCH /projects/{id}/project-dates` | Version/409-Konflikt |
| Project Setup | Work Packages | Work-Package-Endpunkte | strukturierte WPs mit PartnerAllocation |
| Project Setup | Milestones | Milestone-Endpunkte | messbare Ziele und Versionierung |
| Project Setup | Planned Hours | `GET/PATCH /projects/{id}/planned-hours` | Summen/Prozente serverseitig |
| Project Setup | Budget | `GET/PATCH /projects/{id}/budget-plan` | deterministische Quoten/Rules |
| Project Setup | Risks | `GET/PATCH /projects/{id}/risk-register` | strukturierter Risk Register |
| Quellen | Datei/Text/URL hinzufügen | Source-Endpunkte | Status sichtbar pollen |
| Quellen | Public Research starten | `POST /projects/{id}/research-tasks` | nur lead_admin; AsyncOperation |
| Quellen | Research Result importieren | `POST /research-results/{id}/import` | versionierte Source |
| Analyse-Einstellungen | Run starten | `POST /projects/{id}/runs` | 202; Polling |
| Anforderungen | Assessments lesen | `GET /runs/{id}/requirements` | Status, Basis, EvidenceLinks, OpenIssues |
| Evidenz | Anchors/Links lesen | `GET /runs/{id}/evidence` | Detaildaten/Verification/Human Check |
| Editor | Drafts lesen | `GET /runs/{id}/fields` | Current DraftVersion + EvidenceLinks |
| Editor | Speichern | `PATCH /runs/{id}/fields/{field_id}` | neue Version; `recheck_required=true` |
| Editor | Redraft | `POST .../redrafts` | Kandidat, kein stilles Überschreiben |
| Review | Paket laden | `GET /runs/{id}/review` | Blocker, Findings, OpenIssues, Recheckstatus |
| Review | Human Decision | `POST /runs/{id}/human-decisions` | typisierte Aktion/Audit |
| Review | Prüfung aktualisieren | `POST /runs/{id}/rechecks` | AsyncOperation; neues ReviewPackage |
| Review | Freigeben | `POST /runs/{id}/approvals` | nur aktueller recheckter Scope |
| Review | Finalisieren | `POST /runs/{id}/resume` | nur mit aktueller Approval |
| Review | optionaler Final Review | `POST /runs/{id}/final-quality-review` | lead_admin; Findings; evtl. Recheck nötig |
| Export | Export erzeugen | `POST /runs/{id}/exports` | ENTWURF ohne gültige Approval |
| Kosten | Usage laden | `GET /projects/{id}/usage` | Schätz-/Istwerte |
| Admin | Controls prüfen | `GET /runs/{id}/controls` | nur lead_admin |
| Admin | Dienstetest | `POST /services/{service}/test` | boolescher Status, keine Secrets |
