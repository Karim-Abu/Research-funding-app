# F1 Synthetic Case

F1 ist ein synthetischer Innosuisse/Innolink-Evaluationsfall fuer R0. Er enthaelt keine echten Partnernamen, keine echten Budgetzahlen, keine NDA-Daten und keine proprietaeren Projektdetails.

## Zweck

- Goldstandard-Skeleton fuer Feldmapping, Findings und spaetere Harness-Auswertung.
- Baseline-Fall fuer Repair-Roadmap und Thesis-Evaluation.
- Kein Produktivbeispiel und kein automatisch einreichbarer Antrag.

## Synthetic Project Outline

| Area | Synthetic placeholder |
|---|---|
| Funding instrument | Innosuisse Innovation Project with implementation partner |
| Project topic | Synthetic circular materials field case |
| Data class | public / synthetic |
| Provider mode | fake/local |
| Websearch | off |
| Confidential data | none |

## Expected Fields Skeleton

| Field ID | Expected status in F1 | Gold note |
|---|---|---|
| `INTRO.APP.NAME` | present | synthetic project title only |
| `INTRO.APP.NAME_EN` | placeholder | no auto-translation expected |
| `INTRO.APP.ABSTRACT` | present | short public/synthetic abstract |
| `INTRO.APP.EXECUTIVE_SUMMARY` | placeholder | later manual completion |
| `ORG.INDEPENDENCE.FINANCIAL.EXPLANATIONS_COMMENTS` | placeholder | no real partner details |
| `VC.BUSINESS_TARGETS_MODEL.EDITOR` | present-or-placeholder | value-creation claims need evidence review |
| `SOL.INNOVATION_SOLUTION.EDITOR` | present-or-placeholder | solution claims need evidence review |
| `PS.PLANNED_HOURS.MANAGEMENT_EXPLANATION` | placeholder | no real work-package or partner-hour data |

## Expected Findings Skeleton

| Gold finding placeholder | Expected severity | Notes |
|---|---|---|
| missing evidence for market/value claim | warning/blocker TBD | Coverage alone is not correctness |
| unsupported strong technical claim | warning/blocker TBD | Requires evidence sufficiency review |
| incomplete manual copy-paste readiness | warning TBD | No automatic Innolink transfer |
| placeholder field still open | info/warning TBD | Human review required |

## Goldstandard Status

This file is a placeholder/goldstandard skeleton only. Concrete expected values must be added in a later ticket after owner-reviewed synthetic fixtures exist.
