# Rule Registry v1.1

- **Version:** 1.1.0
- **Datum:** 2026-06-21
- **Status:** ready for implementation
- **Maschinenlesbare Fassung:** `innosuisse_innovation_project_v1_1.yaml`
- **Requirement Registry:** `requirements.yaml`

## Umfang

- Official Core Rules: **12**
- Portal Quality Gates: **64**
- Cross-Field Rules: **17**
- bekannte Portalobjekte: **161**
- agent-writable narrative Felder: **18**

## Quellenprinzip

1. Gesetz/Verordnung/Vollzugsbestimmung
2. offizielle Innosuisse-Seite/FAQ
3. offizielle Checkliste
4. UI-verifizierter Snapshot
5. Legacy nur markiert

Unklare Pflichten bleiben `needs_verification` und werden nicht als aktive Blocker ausgeführt.

## Trennung

- `requirements.yaml`: Was fachlich/portalbezogen erforderlich ist.
- Rule Registry: Wie harte/hybride Prüfungen durchgeführt werden.
- Agent Rubrics: Wie semantische Qualität beratend geprüft wird.
- Human Review: finale fachliche Entscheidung.

## Portalobjekt-Metadaten

Jedes Portalobjekt besitzt jetzt:

- `field_kind`
- `support_mode`
- `agent_writable`
- `structured_data_path`
- optional `draft_profile_id`

A2 nutzt ausschliesslich explizite `agent_writable=true`-Felder. Buttons, Uploads, Tabellen, IDs, Beträge, Termine und Bestätigungen sind nicht frei draftbar.

## Strukturierte Daten

Projekttermine, Partner, Arbeitspakete, Meilensteine, Stunden, Budget und Risiken werden nicht aus einem generischen Textfeld simuliert. Sie sind im Domain Model und API als strukturierte Ressourcen abgebildet.

## Overrides

- Warning: HumanDecision + Kommentar.
- Hybrid: HumanDecision + Kommentar + gegebenenfalls Evidence.
- Hard Blocker: Daten korrigieren oder formal zulässige Ausnahme dokumentieren.
- mathematisch/faktisch falsch: kein Statusklick-Override.

## Implementierung

- Rule Expressions nur für `code_ready` Regeln implementieren.
- Hybrid-/Semantic Gates werden mit Requirement/A3/Human Review verknüpft.
- Jede Rule/Gate referenziert eine kanonische RequirementDefinition.
- Startup-Validator prüft IDs, Quellen, Fields, Requirements, Tests und Status.
