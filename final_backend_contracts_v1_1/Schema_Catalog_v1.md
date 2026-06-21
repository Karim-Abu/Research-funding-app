# Internal Schema Catalog v1

- **Version:** 1.0.0
- **Datum:** 2026-06-21
- **Status:** ready for implementation
- **Maschinenlesbare Fassung:** `schema_catalog.yaml`
- **Schema-Verträge:** 49

## Zweck

Der Katalog löst alle in Agent- und Tool-Registries verwendeten Input-/Output-Schemanamen auf. Er ist die Brücke zu den Pydantic-Modellen unter `backend/app/contracts`.

## Regeln

1. Jede Schema-ID ist eindeutig und versioniert.
2. Unbekannte Schema-Referenzen stoppen den Backend-Start.
3. `additional_properties=false` ist Standard.
4. Required Fields werden vor Invocation geprüft.
5. Model-/Tooloutput wird vor Persistenz validiert.
6. Domain Record Types werden aus Domain Model v4 als Pydantic-Views implementiert.
7. API-DTOs und interne Agent-/Tool-Verträge bleiben getrennt, nutzen aber dieselben kanonischen Enums/Domainbegriffe.

## Empfohlene Pydantic-Struktur

```text
backend/app/contracts/
├── enums.py
├── common.py
├── project.py
├── application_structure.py
├── source.py
├── research.py
├── evidence.py
├── requirements.py
├── agents.py
├── tools.py
├── controls.py
├── review.py
└── api.py
```

## Startup-Validierung

Der Loader prüft:

- jede Registry-Schema-ID,
- versionierte Domain-Record-Referenzen,
- Required Fields,
- Enum-Konsistenz,
- keine unbekannten Felder bei Input/Output,
- Serialisierbarkeit und Hashbildung.
