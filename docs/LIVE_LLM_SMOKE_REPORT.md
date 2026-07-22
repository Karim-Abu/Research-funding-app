# RUN 3C Phase 2 – Live-LLM-Smoke-Bericht

## Status

- Bericht erstellt: 22. Juli 2026
- LIVE-01 web: `passed`
- LIVE-02A Missing Input Smoke: `passed` in Attempt 3
- LIVE-02B Grounded Anchor Smoke: `not_run`
- LIVE-02C Shorten Smoke: `not_run`
- LIVE-03 API/BFF E2E: `not_run`
- Browser E2E: `pending`
- Human quality review: `pending`
- Finaler Reteststatus: `THIRD_LIVE_RETEST_FAILED_REVIEW_REQUIRED`

Attempt 3 wurde vor dem Anchor-Review-Gate beendet. Es wurde keine Review-Session
gespeichert und es wurden keine Quote-Hashes zur Freigabe vorgelegt. Nach dem
Fehler erfolgte kein weiterer externer Request.

## Attempt 1

| Merkmal | Gemessener Wert |
|---|---|
| Tatsächliche LLM-Requests | `1` |
| Request | A2-Preflight |
| Providerstatus | HTTP `200` |
| Harnessstatus | `preflight_status_mismatch` |
| Ursache | Harness erwartete `passed` statt des kanonischen Status `pass` |
| Live-Smokes | `not_run` |
| Firecrawl-Requests | `0` |
| Token | `not_available` |
| Einzellatenz | `not_available` |
| Konservativ geschätzte Kosten | CHF `0.007134` |
| Fake-Fallback | `no` |

Der Harnessfehler wurde mit Commit `28bbfce` und einem Offline-Regressionstest
behoben. Es wurde kein Provider-Retest ohne neue Freigabe ausgeführt.

## Attempt 2

| Merkmal | Gemessener Wert |
|---|---|
| Tatsächliche LLM-Requests | `1` |
| Request | A2-Preflight |
| Providerstatus | HTTP `200` |
| Harnessstatus | `section_marker_missing` |
| Ursache | Synthetischer Feld-Seed enthielt nicht alle Registry-Sektionen |
| Live-Smokes | `not_run` |
| Firecrawl-Requests | `0` |
| Token | `not_available` |
| Einzellatenz | `not_available` |
| Konservativ geschätzte Kosten | CHF `0.007134` |
| Fake-Fallback | `no` |

Der Harnessfehler wurde mit Commit `9aa65d7` behoben. Die vollständige
Offline-Generalprobe des danach gültigen `prepare`-/`resume`-Pfads ist in
`docs/RUN_3C_PHASE2_DRY_RUN_RESULT.md` dokumentiert.

## Attempt 3

| Merkmal | Gemessener Wert |
|---|---|
| Attempt-ID | `7804e94a11da4764b6836a71ec965fc5` |
| Execution Mode | `live` |
| A2-Route | `openai_gpt_56_terra_candidate` |
| Tatsächliche LLM-Requests | `2` |
| Tatsächliche Firecrawl-Requests | `1` |
| Aktive Harness-Laufzeit bis Abbruch | ca. `30.0 s` |
| Exakte Provider-Call-Latenzen | `not_available` |
| Tatsächliche Token | `not_available` |
| Konservativ geschätzte Kosten | CHF `0.165661` |
| Fake-Fallback | `no` |
| Secrets/Rohprompts geloggt | `no` |
| Vollständige Providerantworten geloggt | `no` |

Die fehlenden Token- und Einzellatenzwerte wurden nach dem frühen Abbruch nicht
persistiert. Sie werden nicht aus Providerantworten rekonstruiert oder geschätzt.
Für die Kostenabrechnung werden deshalb die vor jedem Call reservierten
konservativen Maximalwerte verwendet.

### Ausgeführte Pflichtschritte

| Schritt | Ergebnis | Externe Requests | Sicherer Nachweis |
|---|---|---:|---|
| A2-Preflight | `passed` | 1 LLM | HTTP `200`, kanonischer Status `pass`, frischer passender Fingerprint |
| LIVE-02A Missing Input | `passed` | 1 LLM | strukturierte Ausgabe, `missing_inputs`, keine erfundene Marktzahl |
| Public-safe Research Brief, Planner, Firewall und Approval | `passed` | 0 | produktiver HTTP-/BFF-Pfad, freigegebene Query |
| Firecrawl Search | `failed` | 1 Firecrawl | Provider HTTP `502` |
| Anchor-Vorbereitung und Human Gate | `not_run` | 0 | keine geeigneten Resultate und keine Review-Session |
| Market-Preflight | `not_run` | 0 | nach Firecrawl-Fehler gestoppt |
| MarketComparison | `not_run` | 0 | nach Firecrawl-Fehler gestoppt |
| LIVE-02B | `not_run` | 0 | nach Firecrawl-Fehler gestoppt |
| LIVE-02C | `not_run` | 0 | nach Firecrawl-Fehler gestoppt |
| LIVE-03 API/BFF E2E | `not_run` | 0 | nach Firecrawl-Fehler gestoppt |

Der öffentliche Suchtext, vollständige URLs, Dokumentinhalte, API-Schlüssel,
Authorization-Header, Rohprompts und vollständige Providerantworten sind in
diesem Bericht nicht enthalten.

## Root Cause und Sicherheitsverhalten

Der erste Firecrawl-Search in Attempt 3 antwortete mit HTTP `502`. Dadurch
standen keine zwei geeigneten öffentlichen Quellen für Anchor-Review und
LIVE-03 zur Verfügung. Der Harness beendete `prepare` fail-closed mit
`live_e2e_blocked_insufficient_external_evidence`. Es gab keinen Fake-Fallback,
keinen Quellenimport, keine Search-Snippet-Evidenz und keine erfundene
MarketComparison. Das ist kein bestätigter Fehler der Produktlogik.

Beim Fehler-Cleanup blieb auf Windows zunächst die lokale Datei
`checkpoints.db` gesperrt. Ursache war die prozessglobale SQLite-Verbindung des
LangGraph-Checkpointers, die nach dem Engine-Dispose noch offen war. Der
minimale Harness-Fix `6c1d476` schließt Checkpointer und Graph vor Engine und
Session-Entfernung. Der Regressionstest öffnet den echten Checkpointer und
weist anschließend die vollständige Verzeichnislöschung nach. Ein einmaliger
Recovery-Cleanup entfernte die verbliebene Attempt-3-Datei; der Session-Root
war danach leer.

## Kumulative Abrechnung

| Merkmal | Attempts 1–3 |
|---|---:|
| Tatsächliche LLM-Requests | `4` |
| Tatsächliche Firecrawl-Requests | `1` |
| Konservativ geschätzte LLM-Kosten | CHF `0.179929` |
| Genehmigtes kumulatives LLM-Limit | `8` Requests |
| Genehmigtes kumulatives Kostenlimit | CHF `3.00` |
| Fake-Fallback beobachtet | `no` |
| Secrets/Rohprompts geloggt | `no` |

Vor Attempt 3 betrug die vorgegebene kumulative Abrechnung zwei Requests und
CHF `0.014268`. Attempt 3 verbrauchte zwei weitere Requests mit konservativ
CHF `0.165661`. Alle Limits wurden eingehalten.

## Offline-Regressionsgate nach dem Befund

| Gate | Ergebnis |
|---|---|
| Checkpoint-Cleanup-Regression | `1 passed` |
| Alle Harness-Tests | `14 passed` |
| Vollständige zusammenhängende Phase-2-Generalprobe | `1 passed` |
| `scripts/verify_all.ps1` | `passed`, Exit `0`, `654.9 s` |
| Backend, Migration, DOCX | `passed` |
| Vitest, ESLint, TypeScript, Build | `passed` |
| Playwright-Gesamtsuite | `48 passed` |
| Zweiter Golden Path, Import, Review Truth | jeweils `passed` |
| API-Smoke | `19/19 passed` |

Ein erster isolierter Gate-Versuch konnte Word COM und esbuild nicht öffnen.
Der unveränderte Lauf in der lokalen Host-Sitzung bestand diese Schritte. Ein
weiterer kompletter Lauf hatte einen nicht reproduzierten späteren E2E-Fehler;
der exit-code-treue Abschlusslauf bestand anschließend sämtliche Teilgates.
Es wurden dafür keine Produkt- oder Teständerungen vorgenommen.

## Haltepunkt

Attempt 3 ist beendet. Es gibt keine gültige Anchor-Review-Session und keine
Autorisierung für weitere externe Requests. RUN 4 wurde nicht begonnen.
