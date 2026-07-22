# RUN 3C Phase 2 – Live-LLM-Smoke-Bericht

## Status

- Bericht aktualisiert: `2026-07-22T16:34:09Z`
- LIVE-01 web: `passed`
- LIVE-02A Missing Input Smoke: `passed`
- LIVE-02B Grounded Anchor Smoke: `not_run`
- LIVE-02C Shorten Smoke: `not_run`
- LIVE-03 API/BFF E2E: `not_run`
- Browser E2E: `pending`
- Human quality review: `pending`
- Fake-Fallback beobachtet: `no`
- Finaler Status: `LIVE_RETEST_FAILED_REVIEW_REQUIRED`
- Sicherer Reason-Code: `market_comparison_not_limited_insufficient_external_evidence_no_error`

Gate C wurde fail-closed beendet. Die MarketComparison lieferte trotz zweier
exakt freigegebener öffentlicher Passagen den Status
`insufficient_external_evidence` statt des erwarteten Status `limited`. Nach
diesem Befund wurden keine weiteren externen Requests ausgeführt und kein
automatischer Fix oder Retest begonnen.

## Historische kumulative Basis vor Gate C

| Merkmal | Attempts 1–3 |
|---|---:|
| Tatsächliche LLM-Requests | `4` |
| Tatsächliche Firecrawl-Requests | `1` |
| Konservativ geschätzte LLM-Kosten | CHF `0.179929` |
| Fake-Fallback | `no` |

LIVE-01 ist separat mit drei Firecrawl-Calls bestanden. Der erfolgreiche
Firecrawl-Recovery-Gate-B-Lauf verwendete anschließend drei weitere Calls:
einen Search und zwei explizite Fetch-/Import-Requests. Gate C selbst führte
keinen Firecrawl-Call aus.

## Gate C

| Merkmal | Gemessener Wert |
|---|---:|
| Review-Session-ID | `2c878e9fc80e4a758609f645a95d2549` |
| Execution Mode | `live` |
| Neue LLM-Requests | `3` |
| Neue Firecrawl-Requests | `0` |
| Tatsächliche neue LLM-Kosten | CHF `0.037274` |
| Konservativ reservierte neue LLM-Kosten | CHF `0.151586` |
| Laufzeit des Gate-C-Kommandos | `46.4 s` |
| Fake-Fallback | `no` |
| Secrets oder Rohprompts geloggt | `no` |
| Vollständige Providerantworten geloggt | `no` |

### Redigierter LLM-Request-Ledger

| Sequenz | Zweck | Providerroute | HTTP | Input-Token | Output-Token | Konservativ CHF | Tatsächlich CHF |
|---:|---|---|---|---:|---:|---:|---:|
| 4 | `a2_preflight` | `openai_gpt_56_terra_candidate` | `2xx` | 48 | 17 | 0.049737 | 0.000303 |
| 5 | `live_02a` | `openai_gpt_56_terra_candidate` | `2xx` | 2782 | 2486 | 0.068670 | 0.035706 |
| 6 | `market_preflight` | `anthropic_sonnet_5_candidate` | `2xx` | 619 | 33 | 0.033179 | 0.001265 |

Die Sequenzen 1–3 dieser Recovery-Session waren der bereits abgeschlossene
Firecrawl-Search und die zwei expliziten Imports aus Gate B. Es wurden keine
Rohqueries, URLs, Dokumenttexte, Prompts oder Providerantworten in den Ledger
übernommen.

## Kumulative Abrechnung

| Merkmal | Gesamtstand |
|---|---:|
| Tatsächliche LLM-Requests | `7` |
| Konservativ geschätzte LLM-Kosten | CHF `0.331515` |
| Tatsächliche Gate-C-Kosten | CHF `0.037274` |
| Phase-2-Firecrawl-Requests einschließlich Attempts 1–3 und Recovery | `4` |
| LIVE-01-Firecrawl-Requests separat | `3` |
| Genehmigtes kumulatives Kostenlimit | CHF `3.00` |
| Fake-Fallback beobachtet | `no` |

Die kumulative konservative Kostengrenze wurde eingehalten. Die tatsächlich
berechneten Kosten früherer Attempts sind teilweise `not_available`; deshalb
bleibt für diese Attempts die konservative Schätzung maßgeblich.

## Ausgeführte Schritte

| Schritt | Ergebnis | Nachweis |
|---|---|---|
| Session-/Hash-/Source-/Konfigurationsprüfung | `passed` | zwei signierte Quote-Hashes, aktuelle SourceVersions, unveränderte Fingerprints |
| A2-Preflight | `passed` | ein echter OpenAI-Request, HTTP 2xx |
| LIVE-02A | `passed` | `model_generated`, Market-Missing-Input, keine erfundene Marktzahl |
| Market-Preflight | `passed` | ein echter Anthropic-Request, HTTP 2xx |
| Exakte Content Reviews | `passed` | ausschließlich die zwei freigegebenen Passagen |
| Exakte External Anchors | `passed` | Fragment, Offset und Quote-Hash revalidiert |
| MarketComparison | `failed` | `insufficient_external_evidence` statt `limited` |
| LIVE-02B | `not_run` | nach MarketComparison-Befund gestoppt |
| LIVE-02C | `not_run` | nach MarketComparison-Befund gestoppt |
| LIVE-03 API/BFF | `not_run` | nach MarketComparison-Befund gestoppt |
| Human-Review-Artefakt | `not_created` | technische Smokes nicht vollständig |

Die Content Reviews, Anchors und MarketComparison lagen ausschließlich in der
temporären D0-Datenbank. Der Harness entfernte Session, Datenbank, Sources,
Checkpoints und Exporte nach dem Fehler vollständig.

## Haltepunkt

RUN 4 wurde nicht begonnen. Ein weiterer Live-Retest ist nicht autorisiert.
