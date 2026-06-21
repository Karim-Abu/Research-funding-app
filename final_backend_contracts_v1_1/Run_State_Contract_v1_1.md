# Run State Contract v1.1

- **Version:** 1.1.0
- **Datum:** 21.06.2026
- **Status:** ready for implementation
- **Maschinenlesbare Fassung:** `run_state_v1_1.yaml`

## Zweck

Definiert den kanonischen `AnalysisRun`-Status, LangGraph-Stages, Checkpoints, Review-/Recheck-/Approval-Reihenfolge, Idempotenz und Fehlerverhalten.

## Run-Status

```text
created
running
paused_for_review
completed
stopped
failed
cancelled
```

AsyncOperations verwenden separat:

```text
queued | running | succeeded | failed | cancelled
```

## Hauptpfad

```text
initialize
→ validate_source_snapshot
→ extract_facts_and_map_evidence
→ verify_evidence
→ evaluate_requirements_and_rules
→ draft_fields
→ create_template_drafts [nur Fallback]
→ critic_review
→ aggregate_review
→ human_review [interrupt]
```

## Review-Schleife

```text
human_review
├── edit / decision
│     → recheck_required = true
│     → Approval stale
├── explicit recheck
│     → targeted_recheck
│     → aggregate_review
│     → human_review
├── approval
│     nur wenn recheck_required = false
└── resume/finalize
      nur mit aktueller Approval
      → finalize_run
      → completed
```

Diese Reihenfolge verhindert eine Freigabe auf ungeprüften Änderungen.

## Review-Invarianten

- jede relevante Änderung erzeugt neue Draft-/Datenversion,
- betroffene EvidenceLinks und Findings können stale werden,
- deterministische Rechecks sind nach relevanten Edits zwingend,
- semantische Rechecks sind erforderlich, wenn betroffene Blocker/Findings stale sind,
- Approval braucht aktuelle `review_package_version` und `approval_scope_hash`,
- Resume dient nur der Finalisierung, nicht dem nachträglichen Recheck.

## Snapshot

Der Run friert ein:

- Project/ApplicationStructure-Version,
- SourceVersion-IDs,
- Funding Instrument,
- Portal Fields,
- Requirements,
- Rules,
- Data Policy,
- Controls,
- Tools,
- Agents/Profiles/Prompts,
- Modelle,
- Parser/Normalizer,
- RunPolicySnapshot.

## Fehler

- Provider: ein Retry, danach definierter Fallback/OpenIssue.
- Schema: ein strukturierter Retry, danach sichtbarer Fehler.
- Cost/Call: `stopped`, Teilergebnisse bleiben.
- Policy: Aktion blockiert, kein stilles Fortsetzen.
- Audit-Write: fail closed.
- Source/Parsing: sichtbar `failed`/`needs_manual_input`.
- Recheck failure: Run bleibt `paused_for_review`, Approval bleibt gesperrt.

## Idempotenz

Pflicht für:

- Run Start,
- Research Task,
- Recheck,
- Redraft,
- Resume,
- Export.

## Parallelität

- maximal ein Run pro Projekt in `running` oder `paused_for_review`,
- Drafts und strukturierte Ressourcen verwenden `base_version_id`,
- Konflikt ergibt HTTP 409.
