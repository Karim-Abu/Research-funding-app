# Final Cross-Registry & Backend Readiness Audit v1.1

- **Datum:** 2026-06-21
- **Ergebnis:** `PASS_WITH_NON_BLOCKING_OPEN_POINTS`
- **Code Readiness:** Backend-Grundgerüst, Pydantic-Verträge, deterministische Module und Endpoint-Stubs können beginnen.
- **Agent Readiness:** Agentenaufrufe erst nach Implementierung des Startup-Validators und Rollenbenchmarks aktivieren.

## 1. Geprüfte Artefakte

- ADR v4
- Domain Model v4
- Data Policy v1.1
- Requirement Registry v1
- Rule Registry v1.1
- Control Registry v1
- Tool Registry v1.1
- Agent Profile Registry v1.1
- Internal Schema Catalog v1
- Run State Contract v1.1
- API/OpenAPI v1.1
- Frontend–API Mapping v1.1

## 2. Automatische Prüfungen

| Prüfung | Ergebnis |
|---|---|
| YAML parsebar | PASS |
| OpenAPI parsebar | PASS |
| OpenAPI interne `$ref`s | PASS |
| eindeutige `operationId`s | PASS |
| Path-Parameter | PASS |
| Profile → Execution Group | PASS |
| Profile → Tool IDs | PASS |
| gegenseitige Tool/Profile-Berechtigung | PASS |
| Agent/Tool → Control IDs | PASS |
| Agent/Tool → Schema IDs | PASS |
| Rule/Gate → Requirement IDs | PASS |
| A2 → explizite agent-writable Field IDs | PASS |
| Tool-Sensitivitäten kanonisch | PASS |
| Netzwerktools orchestrator-only | PASS |
| Run Nodes → Profile/Tool IDs | PASS |
| Recheck vor Approval | PASS |
| nicht-kanonischer Wert `internal_with_public_confirmed_query` | entfernt |

## 3. Behobene P0/P1-Befunde

1. A2-Execution-Group ergänzt und Teilfehlersemantik definiert.
2. A1-/Toolberechtigungen symmetrisch und least-privilege.
3. Webtools orchestrator-only.
4. RequirementDefinition-Katalog erstellt.
5. Control-/Guardrail-Katalog erstellt.
6. 49 interne Input-/Output-Schemaverträge definiert.
7. Strukturierte Partner-, Workplan-, Milestone-, Hours-, Budget- und Risk-Domain/API ergänzt.
8. Recheck-before-Approval korrigiert.
9. Data Policy in `evaluation_beta` und `institutional_pilot` getrennt.
10. Public Research offiziell als explizite Beta-Funktion modelliert.
11. Web Research Mode zu `validated_public` vereinheitlicht.
12. A2 auf explizite Field-ID-Allowlists begrenzt.
13. Feldspezifische A2-/A3-Rubriken ergänzt.
14. LLM-Autorität explizit modelliert.
15. HumanDecision typisiert; Reklassifizierung separat.
16. OpenIssue/EvidenceLink/ControlResult in API ergänzt.
17. Research Result um ProfessionalEvidence und PartnerRoleSuggestion erweitert.
18. Modellroute für optionalen Final Review robust gemacht.

## 4. Nicht blockierende offene Punkte

### O1 – Institutionelle Providerfreigabe

Direkte OpenAI-/Anthropic-Routen sind für public/synthetic Beta-Daten nutzbar. Reale interne Projektdaten bleiben operational blockiert, bis eine institutionelle Route freigegeben ist.

### O2 – Retention und Purge

FHNW-Fristen fehlen. Keine Frist wurde erfunden. Produktive Purge-Endpunkte bleiben geplant, nicht aktiv.

### O3 – Technisches Uploadlimit

Kein fachliches Limit. Vor Deployment muss `MAX_UPLOAD_BYTES` konfiguriert und über `/capabilities` publiziert werden.

### O4 – Modellbenchmark

Modelle sind aktuelle, plausible Kandidaten, aber Rollenbelegung bleibt provisional. A1/A2/A3 müssen am Goldset verglichen werden.

### O5 – Portal `needs_verification`

Nicht vollständig erfasste Pflicht-/Optionswerte bleiben nicht-blockierend, bis sie verifiziert sind.

### O6 – Referenzanträge

Bewilligter, abgelehnter und Training-Sample-Antrag wurden in diesem Contract-Härtungsschritt nicht inhaltlich verarbeitet. Vor Nutzung sind Rechte, Datenklasse, Instrument-/Portalversion und zulässiger Evaluationszweck zu klären. Sie sind kein Fine-Tuning-Datensatz.

## 5. Go/No-Go

### GO

- Backend-Paketstruktur
- Pydantic Domain-/Registry-/API-Modelle
- Config Loader und Startup-Validator
- Auth/Session/CSRF
- SQLite/Alembic
- Source Storage/Hashing/Normalisierung
- strukturierte Application Data
- deterministische Rules/Controls
- Endpoint-Stubs und Contract Tests

### CONDITIONAL GO

- LangGraph-Nodes nach grünen deterministischen Contract Tests
- A1/A2/A3 erst nach Schema-, Policy-, Prompt-Injection- und Goldset-Tests
- Public Research erst nach URL-/SSRF-/Purpose-/Identity-Matching-Tests

### NO-GO

- echte internal/confidential Projektinhalte an nicht freigegebene Cloudrouten
- automatische Trainings-/Fine-Tuning-Nutzung der Referenzanträge
- Bewilligungswahrscheinlichkeitsclaim
- Agent-/Toolaufrufe ohne Startup-Validator und Control Layer

## 6. Empfohlene Implementierungsreihenfolge

1. `contracts/` und gemeinsame Enums.
2. Registry Loader + Startup Validator.
3. Auth/Session/CSRF.
4. Persistenz und Source Storage.
5. Structured Application Data.
6. Data Policy + Controls.
7. Rule Engine + Requirements.
8. Evidence Candidate/Verification/Links.
9. Deterministischer Run + Review/Recheck/Approval/Export.
10. A1.
11. A2 nach Feldprofilen.
12. A3.
13. Public Research.
14. Evaluation und Modellbenchmark.

## 7. Qualitätsziel

Die Lösung darf nicht behaupten, eine Bewilligung zu reproduzieren. Das verteidigbare Ziel lautet:

> Erzeugung eines strukturell vollständigen, portalspezifischen, evidenzbasierten und review-reifen Erstentwurfs, dessen Qualität anhand genehmigter, abgelehnter und synthetischer Referenzfälle bewertet wird.
