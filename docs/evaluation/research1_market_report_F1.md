# RESEARCH.1 — Market Research Report (F1 synthetic)

*Generiert:* 2026-07-09 · *Case:* `F1` · *data_mode:* `fake_test` · *Provider:* `fake`

## Pflichthinweise

- Nur **D0/public** (F1 synthetic). Keine echten D2-Daten, keine Partnernamen, keine Budgetzahlen, keine personenbezogene Suche.
- **MarketCandidates sind Kandidaten, keine Fakten.** Ein Snippet ist **kein Beleg** und wird nicht automatisch zu einer Fundstelle (EvidenceAnchor). Keine automatische TAM/SAM/SOM-Aussage, keine automatische Value-Creation-Änderung.
- **Human Review erforderlich** für jeden Kandidaten vor jeder Weiterverwendung.
- Alle Queries liefen über die bestehende Search Query Firewall + ResearchExecutor (kein zweiter Webpfad). Firecrawl-Kosten werden als Credits/ToolInvocation gezählt (keine CHF/USD-Umrechnung).
- Keine Roh-HTML-Inhalte, keine Secrets, keine vertraulichen Rohqueries im Report.

## Kennzahlen

- Geplante Queries: 5 (blockiert/übersprungen: 0)
- ResearchResults: 15
- ToolInvocations: 10 · Credits: 0.0
- Importierte Quellen (SourceDocuments): 0

## Geplante Queries (public-safe)

| purpose | query_text | public_safe | approval_required |
| --- | --- | --- | --- |
| market_size | manufacturing quality assurance industrial AI anomaly detection market size Switzerland | True | False |
| competitors_alternatives | industrial AI anomaly detection manufacturing quality assurance competitors alternatives | True | False |
| customer_pain | manufacturing quality assurance manufacturing SMEs quality challenges pain points | True | False |
| go_to_market_channels | manufacturing quality assurance industrial AI anomaly detection go to market sales channels Switzerland | True | False |
| pricing_willingness_to_pay | industrial AI anomaly detection manufacturing quality assurance pricing willingness to pay | True | False |

## MarketCandidates

| candidate_type | purpose | status | confidence | rank | title | source_url | snippet | review |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| competitor_or_alternative | competitors_alternatives | candidate | medium | 1 | Öffentliche Quelle 1 zu industrial AI anomaly detection manufacturing quality assurance competitors alternatives | https://research.example.org/result/0 | Öffentlich zugänglicher Auszug 1 (Snippet ist kein Beleg). | ja |
| competitor_or_alternative | competitors_alternatives | candidate | low | 2 | Öffentliche Quelle 2 zu industrial AI anomaly detection manufacturing quality assurance competitors alternatives | https://publications.example.org/result/1 | Öffentlich zugänglicher Auszug 2 (Snippet ist kein Beleg). | ja |
| competitor_or_alternative | competitors_alternatives | candidate | low | 3 | Öffentliche Quelle 3 zu industrial AI anomaly detection manufacturing quality assurance competitors alternatives | https://profiles.example.org/result/2 | Öffentlich zugänglicher Auszug 3 (Snippet ist kein Beleg). | ja |
| pricing_signal | pricing_willingness_to_pay | candidate | medium | 1 | Öffentliche Quelle 1 zu industrial AI anomaly detection manufacturing quality assurance pricing willingness to pay | https://research.example.org/result/0 | Öffentlich zugänglicher Auszug 1 (Snippet ist kein Beleg). | ja |
| pricing_signal | pricing_willingness_to_pay | candidate | low | 2 | Öffentliche Quelle 2 zu industrial AI anomaly detection manufacturing quality assurance pricing willingness to pay | https://publications.example.org/result/1 | Öffentlich zugänglicher Auszug 2 (Snippet ist kein Beleg). | ja |
| pricing_signal | pricing_willingness_to_pay | candidate | low | 3 | Öffentliche Quelle 3 zu industrial AI anomaly detection manufacturing quality assurance pricing willingness to pay | https://profiles.example.org/result/2 | Öffentlich zugänglicher Auszug 3 (Snippet ist kein Beleg). | ja |
| customer_segment | customer_pain | candidate | medium | 1 | Öffentliche Quelle 1 zu manufacturing quality assurance manufacturing SMEs quality challenges pain points | https://research.example.org/result/0 | Öffentlich zugänglicher Auszug 1 (Snippet ist kein Beleg). | ja |
| customer_segment | customer_pain | candidate | low | 2 | Öffentliche Quelle 2 zu manufacturing quality assurance manufacturing SMEs quality challenges pain points | https://publications.example.org/result/1 | Öffentlich zugänglicher Auszug 2 (Snippet ist kein Beleg). | ja |
| customer_segment | customer_pain | candidate | low | 3 | Öffentliche Quelle 3 zu manufacturing quality assurance manufacturing SMEs quality challenges pain points | https://profiles.example.org/result/2 | Öffentlich zugänglicher Auszug 3 (Snippet ist kein Beleg). | ja |
| go_to_market_signal | go_to_market_channels | candidate | medium | 1 | Öffentliche Quelle 1 zu manufacturing quality assurance industrial AI anomaly detection go to market sales channels Switzerland | https://research.example.org/result/0 | Öffentlich zugänglicher Auszug 1 (Snippet ist kein Beleg). | ja |
| go_to_market_signal | go_to_market_channels | candidate | low | 2 | Öffentliche Quelle 2 zu manufacturing quality assurance industrial AI anomaly detection go to market sales channels Switzerland | https://publications.example.org/result/1 | Öffentlich zugänglicher Auszug 2 (Snippet ist kein Beleg). | ja |
| go_to_market_signal | go_to_market_channels | candidate | low | 3 | Öffentliche Quelle 3 zu manufacturing quality assurance industrial AI anomaly detection go to market sales channels Switzerland | https://profiles.example.org/result/2 | Öffentlich zugänglicher Auszug 3 (Snippet ist kein Beleg). | ja |
| market_size_candidate | market_size | candidate | medium | 1 | Öffentliche Quelle 1 zu manufacturing quality assurance industrial AI anomaly detection market size Switzerland | https://research.example.org/result/0 | Öffentlich zugänglicher Auszug 1 (Snippet ist kein Beleg). | ja |
| market_size_candidate | market_size | candidate | low | 2 | Öffentliche Quelle 2 zu manufacturing quality assurance industrial AI anomaly detection market size Switzerland | https://publications.example.org/result/1 | Öffentlich zugänglicher Auszug 2 (Snippet ist kein Beleg). | ja |
| market_size_candidate | market_size | candidate | low | 3 | Öffentliche Quelle 3 zu manufacturing quality assurance industrial AI anomaly detection market size Switzerland | https://profiles.example.org/result/2 | Öffentlich zugänglicher Auszug 3 (Snippet ist kein Beleg). | ja |

## Offene Risiken

- Kandidaten sind unbestätigt; Marktzahlen/Wettbewerber sind Signale, keine Fakten.
- Ein Import als D0-Quelle erfolgt nur über den bestehenden Import-/Review-Prozess (nicht in diesem Slice).
- Realer Firecrawl-Lauf ist manuell/env-gated; dieser Report kann im Fake-Modus erzeugt worden sein (siehe Provider oben).

---

Erzeugt mit `python scripts/run_market_research_f1.py` (Fake default; realer Firecrawl nur env-gated, nie in CI). MarketCandidates brauchen Human Review.
