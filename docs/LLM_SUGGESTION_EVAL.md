# Offline-Evaluation der LLM-Vorschlagslogik

Stand: 21. Juli 2026
Datensatz: `Run3CSuggestionEval@v1`
Datenklasse: `F1_synthetic`

## Zweck und Grenze

Das versionierte Set
`docs/evaluation/cases/run3c_suggestion_eval_v1.json` prüft die unabhängige,
serverseitige Claim-Extraktion und das Grounding ohne Netzwerk- oder
Providerzugriff. Es bewertet keine sprachliche Qualität eines echten Modells.

Der Test ignoriert eine gegebenenfalls vorhandene providerseitige Claim-Map
bewusst und validiert ausschließlich den vollständigen `suggestion_text` gegen
Originaltext, bestätigte strukturierte Daten und ausgewählte Anchors.

## Fälle

| ID | Schwerpunkt | Erwartung |
|---|---|---|
| AI-Q01 | Reine Umformulierung | keine konkrete neue Claim-Pflicht |
| AI-Q02 | Dauer aus Original | `18 Monate` zulässig |
| AI-Q03 | TRL aus strukturiertem Input | `TRL 5` zulässig |
| AI-Q04 | Prozentwert aus ausgewähltem Anchor | Zahl und Marktclaim zulässig |
| AI-Q05 | nicht deklarierter Marktanteil | unabhängig erkannt und abgelehnt |
| AI-Q06 | Organisation aus Anchor | zulässig |
| AI-Q07 | nicht deklarierte Organisation | unabhängig erkannt und abgelehnt |
| AI-Q08 | benanntes Produkt | nur mit ausgewähltem Anchor zulässig |
| AI-Q09 | konkrete Marktbehauptung | mit exakt erlaubtem Anchor zulässig |
| AI-Q10 | unbelegte Rechtsbehauptung | abgelehnt |
| AI-Q11 | Datum aus Original | zulässig |
| AI-Q12 | Währung aus Anchor | zulässig |
| AI-Q13 | Gliederungsnummern | nicht als Fakten fehlklassifiziert |
| AI-Q14 | unbelegtes Jahr | abgelehnt |
| AI-Q15 | Akronymorganisation | mit Anchor zulässig |
| AI-Q16 | Unicode-Produktname | NFC-sicher erkannt und belegt |

Weitere fokussierte Regressionen prüfen fremde, unbekannte, alte, generierte,
ungeprüfte und quarantänisierte Anchors, Snippet-Ausschluss, maximal fünf
Market-Findings, Registry-Zuordnung, OpenIssue-Lebenszyklus, Generate-/Accept-
Idempotenz, parallele Accepts und die zentralen Staleness-Gründe.

## Gemessenes Offline-Ergebnis

- Datensatz- und Groundingtests: 21 bestanden.
- Gesamter fokussierter A2-/RUN-3C-Block: 161 bestanden.
- Kein echter Provider- oder LLM-Aufruf.
- Kein Fake-Fallback in einem Live-Vorschlagspfad geprüft, da LIVE-LLM bewusst
  noch nicht ausgeführt wurde; der Offline-Test beweist lediglich, dass der
  implementierte Pfad keinen automatischen Providerwechsel enthält.

## Noch nicht nachgewiesen

- LIVE-02, echter strukturierter LLM-Smoke: `not_run`.
- LIVE-03, beaufsichtigter Live-Happy-Path: `not_run`.
- Menschliche Bewertung von fachlichem Nutzwert, Klarheit und Vollständigkeit:
  `not_run`.

Die Phase-1-Ergebnisse belegen deterministische Offline-Korrektheit und
Sicherheitsgates, nicht die Qualität echter KI-Vorschläge.
