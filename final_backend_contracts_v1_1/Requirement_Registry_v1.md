# Requirement Registry v1

- **Version:** 1.0.0
- **Datum:** 2026-06-21
- **Status:** ready for implementation
- **Maschinenlesbare Fassung:** `requirements.yaml`
- **Instrument:** Innosuisse «Create Innovation Project» mit Umsetzungspartner

## Zweck

Die Registry ist der kanonische Katalog der fachlichen `RequirementDefinition`s. Sie wird ausschliesslich aus den verifizierten Core Rules und den UI-snapshot-basierten Portal Quality Gates abgeleitet. LLMs dürfen keine Requirements erzeugen oder ändern.

## Umfang

- Requirements insgesamt: **76**
- Hard: **42**
- Hybrid: **14**
- Semantic: **20**
- Blocker: **52**
- Warning: **18**
- Info: **6**

## Beziehung zu anderen Registries

```text
RequirementDefinition
├── linked_rule_ids → Rule Registry
├── linked_quality_gate_ids → Portal Quality Gates
├── affected_field_ids → Portal Field Catalog
├── source_refs → Source Catalog
└── assessment_basis → RequirementAssessment
```

## Regeln

1. Requirements sind versioniert.
2. Unverifizierte Quellen dürfen keine aktive blockierende Requirement erzeugen.
3. `hard` wird deterministisch bewertet.
4. `semantic` erzeugt beratende Bewertung/Human Review.
5. `hybrid` kombiniert RuleResult, Evidence und Human/Agent Assessment.
6. Das Frontend zeigt user-facing Requirements; technische Requirements können intern bleiben.
7. Jede RequirementAssessment verweist auf genau eine RequirementDefinition-Version.

## Implementierung

`requirements.yaml` ist die technische Wahrheit. Beim Startup werden alle Rule-, Gate-, Field- und Source-Referenzen geprüft. Fehlende Referenzen sind fatal.
