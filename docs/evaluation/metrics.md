# Evaluation Metrics

Dieses Dokument definiert R0-Metriken vor der eigentlichen Bewertung. Ziel ist ein stabiler Rahmen, keine erfundenen Ergebnisse.

| Metric | Definition | R0 Status |
|---|---|---|
| Finding Precision | Anteil korrekter gemeldeter Findings gegen Goldstandard. | Skeleton, noch keine echte Bewertung |
| Finding Recall | Anteil gefundener Gold-Findings gegen Goldstandard. | Skeleton, noch keine echte Bewertung |
| Evidence-Sufficiency-Agreement | Uebereinstimmung zwischen Sufficiency-Status und menschlichem Expertenurteil. | Skeleton, braucht annotierte Stichprobe |
| Import Field Mapping Accuracy | Anteil korrekt gemappter Innolink-Felder gegen Gold-Feldmapping. | Skeleton, keine Import-Implementierung in R0 |
| Copy-Paste-Readiness-Rate | Anteil der Felder, die nach definiertem Review-Skript manuell kopierbereit sind. | Skeleton, keine automatische Uebernahme |
| Manual Effort Reduction | Vergleich von Zeit/Schritten zwischen Baseline und unterstuetztem Workflow. | Skeleton, braucht Evaluationsprotokoll |
| Latency | Laufzeit je Harness-/Analysepfad. | Skeleton, noch keine Messpflicht |
| Cost | Deterministisch erfasste oder explizit als Placeholder markierte Kosten. | Placeholder; keine CHF erfinden |

## Interpretationsregeln

- Keine Zielwerte ohne Baseline erfinden.
- Fake/local-Ergebnisse immer als solche kennzeichnen.
- Coverage misst Verlinkung, nicht faktische Korrektheit.
- Cost darf `None` sein, solange keine deterministische Messung existiert.
- Metriken duerfen keine automatischen Proposal-Submission- oder Portal-Writeback-Claims erzeugen.
