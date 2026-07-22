# Bekannte Live-Limitationen nach RUN-3C-Abschluss

Dieser Stand dokumentiert die aktuell bekannten, real gemessenen Einschränkungen des Live-Pfades. Er ergänzt `docs/RUN_3_CLOSURE.md` und ersetzt keine fachliche Fehleranalyse.

## 1) Externe Blockade (technische)

- Der kombinierten LIVE-3C-Lauf (LIVE-02B/LIVE-02C/LIVE-03) fehlt ein gültiger Ende-zu-Ende-Lauf, da ein externer Firecrawl-`provider_timeout` die letzte bestätigte Live-Phase blockiert hat.
- Es wurde kein produktiver Bug im Anwendungscode verifiziert; der Run ist provider-seitig unterbrochen.
- Status: `COMBINED_LIVE_E2E_BLOCKED_BY_PROVIDER_TIMEOUT`

## 2) Nicht automatisch abgedeckte Qualitätsbewertung

- Die humane Qualitätsbewertung (fachliche Verständlichkeit, Nutzen und Relevanz) ist nicht als vollständige Freigabe erfolgt.
- Alle echten Suggestion-Beurteilungen basieren aktuell nur auf den geprüften technischen Gates + Grounding-/Missing-Input-Mechanik.
- Status: `LIVE_QUALITY_REVIEW` / `HUMAN_QUALITY_REVIEW` bleibt `pending`.

## 3) Browser-E2E und vollständiger End-to-End-UX-Pfad

- Browser-E2E ist bewusst nicht abgeschlossen.
- Der vollständige „Beobachtungsfluss“ über echte Endanwenderoberfläche ist noch ausständig.
- RUN 4 erweitert den UI/UX-Fluss, ohne den Live-Kern neu zu verändern.

## 4) Datenmodell- und Architekturgrenzen

- Kein produktionsreifes, automatisches “NDA-Enterprise” oder vollumfänglicher Approval-Mechanismus über alle Domänen wurde als abgeschlossen behauptet.
- Externe Marktclaims ohne bestätigte Quelle dürfen weiterhin nicht automatisch abgeleitet werden; der Pfad setzt auf Missing Inputs statt Halluzination.

## 5) Prozessgrenzen

- Keine neue Provider- oder Marketarchitektur.
- Keine Vergleichs- oder Registry-Neuentwicklung in diesem Abschlussschritt.
- Kein RUN-4-Umsetzungsinhalt in diesem Dokumentationsschritt.
- Der nächste echte E2E-Abschnitt (inkl. Browser-E2E und finaler Live-Review) ist separater Scope.

## 6) Offene Freigaben / Leitplanken

- Approval bleibt erforderlich für produktiv wirksame Schritte, entsprechend bestehender Regeln.
- Human Review bleibt verpflichtend für Endfreigabe.
- Kein fiktiver Produktionsstatus: nur durch reale, erfolgreiche Gate-Sets belegte Teilfertigkeiten werden als validiert markiert.

## Statuswahrheit

- `LIVE_WEB_CAPABILITY_VALIDATED`
- `LIVE_LLM_CAPABILITY_VALIDATED`
- `MARKET_SCOPE_OFFLINE_VALIDATED`
- `RUN_3_TECHNICALLY_PARTIALLY_ACCEPTED`

### Nicht erfüllt / blockiert

- Kein Nachweis für Lauf mit erfolgreichem `LIVE-02B` + `LIVE-02C` + `LIVE-03` in einem externen Provider-gedrängten Durchlauf.
- Kein Lauf-übergreifender, menschlicher Qualitäts-Finalentscheid für die E2E-Produktion im Sinne einer vollständigen RUN-4-Freigabe vorhanden.
