# Agent Profile Registry v1.1

- **Version:** 1.1.0
- **Datum:** 2026-06-21
- **Status:** ready for implementation
- **Maschinenlesbare Fassung:** `agents_v1_1.yaml`
- **Agententypen:** A1, A2, A3
- **Profile:** 13

## Prinzipien

1. Agenten sind interne LangGraph-Komponenten und nicht über die API aufrufbar.
2. A1 liefert Vorschläge/Faktenkandidaten, A2 Draftkandidaten und A3 beratende Findings.
3. Kein Agent setzt Regeln, Freigaben, Datenklassifikationen, Beträge, Termine oder Identitäten.
4. Tools benötigen gegenseitige Profile/Tool-Autorisierung.
5. A2 bearbeitet nur explizite Field-ID-Allowlists.
6. Webrecherche wird durch den Orchestrator ausgeführt; A1 strukturiert nur importierte Resultate.
7. Mehrere A3-Rubriken können in einem Call gebündelt werden, Findings bleiben über `origin_profile_id` trennbar.
8. Modelle bleiben bis zum Rollenbenchmark vorläufig.

## Agentenautorität

| Agent | Autorität |
|---|---|
| A1 | `proposal_requires_validation` |
| A2 | `draft_requires_human_review` |
| A3 | `advisory_finding` |
| Rules/Controls | `authoritative_within_rule_scope` |
| Human | finale fachliche Entscheidung |

## Ausführungsgruppen

- `A1.core_extraction_bundle`
- `A1.public_research_separate`
- `A2.field_drafting_sequence`
- `A3.core_review_bundle`
- `A3.final_review_separate`

A2 erlaubt Teilerfolg: nur das fehlgeschlagene Feldprofil fällt auf Template zurück.

## Profile

| Profil | Gruppe | Output Authority | Scope | Primärroute |
|---|---|---|---|---|
| `A1.project_fact_extraction` | `A1.core_extraction_bundle` | `proposal_requires_validation` | INTRO., ORG., VC., SOL., PS. | `anthropic_haiku_45` |
| `A1.evidence_candidate_mapping` | `A1.core_extraction_bundle` | `proposal_requires_validation` | INTRO., ORG., VC., SOL., PS. | `anthropic_haiku_45` |
| `A1.public_competence_research` | `A1.public_research_separate` | `proposal_requires_validation` | profile-specific | `anthropic_haiku_45` |
| `A2.introduction_public_summary` | `A2.field_drafting_sequence` | `draft_requires_human_review` | 4 explicit fields | `anthropic_sonnet_46` |
| `A2.organisations_governance` | `A2.field_drafting_sequence` | `draft_requires_human_review` | 1 explicit fields | `anthropic_sonnet_46` |
| `A2.value_creation_market_logic` | `A2.field_drafting_sequence` | `draft_requires_human_review` | 1 explicit fields | `anthropic_sonnet_46` |
| `A2.solution_innovation` | `A2.field_drafting_sequence` | `draft_requires_human_review` | 1 explicit fields | `anthropic_sonnet_46` |
| `A2.project_setup_workplan` | `A2.field_drafting_sequence` | `draft_requires_human_review` | 11 explicit fields | `anthropic_sonnet_46` |
| `A3.evidence_consistency` | `A3.core_review_bundle` | `advisory_finding` | INTRO., ORG., VC., SOL., PS. | `openai_gpt_54` |
| `A3.fit_gap_partner_plausibility` | `A3.core_review_bundle` | `advisory_finding` | ORG., VC., SOL. | `openai_gpt_54` |
| `A3.risk_review_readiness` | `A3.core_review_bundle` | `advisory_finding` | INTRO., ORG., VC., SOL., PS. | `openai_gpt_54` |
| `A3.innovation_challenge` | `A3.core_review_bundle` | `advisory_finding` | VC., SOL. | `openai_gpt_54` |
| `A3.final_quality_review` | `A3.final_review_separate` | `advisory_finding` | INTRO., ORG., VC., SOL., PS. | `anthropic_opus_48` |

## A2-Feldlogik

- Introduction: Application Names, Abstract, Executive Summary.
- Organisations/Governance: nur explizite Erklärungstexte; keine Partner-/UID-/FTE-Werte.
- Value Creation: Composite Editor 3.1–3.3.
- Solution & Innovation: Composite Editor 4.1–4.5.
- Project Setup: narrative Beschreibungs-/Begründungsfelder; keine Zahlen, Termine, Stunden oder Beträge.

## Final Quality Review

- optional und manuell,
- public/synthetic only,
- primär Opus 4.8, Fallback GPT-5.5,
- Fable 5 nur bedingter Kandidat mit Runtime- und Retentionprüfung,
- erzeugt Findings, ändert keine Approval automatisch.

## Promptabgrenzung

Diese Registry enthält Instruktionsverträge, Rubriken, Grenzen, Schemas, Controls und Akzeptanzkriterien. Vollständige Prompts sind getrennte, versionierte Artefakte.
