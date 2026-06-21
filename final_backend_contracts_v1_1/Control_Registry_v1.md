# Control & Guardrail Registry v1

- **Version:** 1.0.0
- **Datum:** 2026-06-21
- **Status:** ready for implementation
- **Maschinenlesbare Fassung:** `controls.yaml`
- **Control-Anzahl:** 29

## Zweck

Die Registry vereinheitlicht alle zuvor uneinheitlich benannten Sicherheits-, Qualitäts-, Kosten-, Evidence- und Freigabekontrollen. Agenten, Tools, API-Aktionen und LangGraph-Nodes dürfen nur kanonische `control_id`s verwenden.

## Lifecycle

```text
Action Request
→ Control Definition Lookup
→ Input/Context Evaluation
→ ControlResult
→ passed / warning / blocked / failed
→ AuditEvent
```

- `blocked` verhindert die abhängige Aktion.
- `failed` verhindert die Aktion und kann bei kritischen Controls den Run stoppen.
- `warning` erlaubt Fortsetzung nur, wenn Definition und Policy dies ausdrücklich zulassen.

## Kategorien

| Kategorie | Beispiele |
|---|---|
| Privacy | Data Policy, Least Context, Internal Query Confirmation |
| Security | Source Trust, Prompt Injection, Tool Authorization |
| Source Security | File Type, File Size, Filename, Path Traversal, Malware, Parser |
| Network Security | Public URL Validation, SSRF, Redirect Revalidation |
| Integrity | Version Lock, Content Hash, Run Snapshot |
| Evidence | Evidence Verification, Evidence Requirement |
| Cost | CostGuard |
| Workflow | Approval Gate, Export Classification |
| Audit | Audit Write |

## Verbindliche Regeln

1. Unbekannte Control-ID ist startup-fatal.
2. Jede Control-Ausführung erzeugt ein unveränderliches `ControlResult`.
3. Controls werden nicht als LLM-Agenten implementiert.
4. Synonyme wie `prompt_injection_controls` oder `prompt_injection_marking` sind entfernt; kanonisch ist `CTRL.PROMPT_INJECTION`.
5. Ein Frontend-Boolean ersetzt niemals serverseitige Policy- oder Providerprüfung.
6. Kritischer Audit-Write-Failure ist fail closed.

## Implementierung

`controls.yaml` enthält für jedes Control:

- Phase,
- Statuswerte,
- Blocking Rule,
- Reason Codes,
- Auditpflicht,
- Testpflicht,
- Version.
