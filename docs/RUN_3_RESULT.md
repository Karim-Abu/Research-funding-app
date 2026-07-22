# RUN 3 RESULT (vorläufig – Live-Retest fehlgeschlagen)

- Offline baseline: `passed`
- LIVE-01 web: `passed`
- LIVE-02A: `passed`
- LIVE-02B: `not_run`
- LIVE-02C: `not_run`
- LIVE-03 API/BFF E2E: `not_run`
- Browser E2E: `pending`
- Human quality review: `pending`
- Fake fallback observed: `no`
- Critical unsupported facts persisted: `no`
- RUN 4: `not_authorized`

Gate C wurde nach dem sicheren Reason-Code
`market_comparison_not_limited_insufficient_external_evidence_no_error`
beendet. Die zwei freigegebenen Quellen führten nicht zum vertraglich
erwarteten Status `limited`. LIVE-02B, LIVE-02C und der Accept-/Replay-Pfad
wurden deshalb nicht ausgeführt.

Kumulativ wurden sieben echte LLM-Requests mit konservativ geschätzten Kosten
von CHF `0.331515` verbraucht. Gate C verursachte drei dieser Requests und
tatsächliche Kosten von CHF `0.037274`. Es gab keinen neuen Firecrawl-Call und
keinen Live-zu-Fake-Fallback.

Technische Live-Akzeptanz und menschliche Qualitätsakzeptanz sind nicht
abgeschlossen. Ein weiterer Retest erfordert eine neue ausdrückliche
Entscheidung.
