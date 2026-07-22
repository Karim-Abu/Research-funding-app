# RUN 3C Attempt 3 – Forensische Fehleranalyse

## 1. Executive Summary

Attempt 3 ist als `PROVIDER_OR_CONFIGURATION` klassifiziert; der zulässige
Statuswert lautet:

```text
ATTEMPT3_FAILURE_CLASSIFIED_PROVIDER
```

Die direkte Ursache an der kontrollierten Systemgrenze war ein echter
Firecrawl-Search mit HTTP `502`. Der produktive Adapter wandelte dies in
`ProviderError` um. Der Research Executor persistierte ResearchTask,
AsyncOperation und ToolInvocation als fehlgeschlagen und erzeugte keine
ResearchResults. Die HTTP-Route antwortete anschließend vertragsgemäß mit dem
Research-Run und `result_count=0`. Das Harness stellte danach weniger als zwei
geeignete Kandidaten fest und stoppte fail-closed mit
`live_e2e_blocked_insufficient_external_evidence`.

Der interne Grund für das HTTP 502 – Firecrawl selbst oder eine vorgelagerte
Provider-Infrastruktur – ist mit den erhaltenen redigierten Metadaten nicht
bestimmbar. Er wird nicht als Fakt behauptet. Ein Authentifizierungs- oder
Konfigurationsfehler ist weniger wahrscheinlich und nicht belegt: Der Request
erreichte den Provider und erhielt HTTP 502 statt 401/403; die konfigurierte
Live-Route erzeugte keinen Fake-Fallback.

Ein zweiter, nachgelagerter `HARNESS_DEFECT` betraf ausschließlich den
Fehler-Cleanup unter Windows: Die prozessglobale Checkpoint-SQLite-Verbindung
blieb geöffnet. Dieser Defekt verursachte weder HTTP 502 noch den fachlichen
Stopp. Er wurde nach Attempt 3 bereits separat mit Commit `6c1d476` und einem
Offline-Regressionstest behoben. In diesem Forensik-Review wurden weder Code
noch Tests geändert oder ausgeführt.

## 2. Belegbasis und Git-Stand

- Forensisch geprüfter HEAD vor diesem Dokument: `3e9e250952290599acc29b49baf2c554ec82291b`.
- Basis `0b03d82` ist Vorfahr des aktuellen Stands.
- Attempt 3 lief auf `a4295cc`; dessen Historie enthält:
  - `28bbfce`: kanonisches Preflight-Statusliteral `pass`;
  - `9aa65d7`: vollständige Registry-Sektionsmarker im D0-Feld-Seed;
  - `c6989fe`, `8b79b56`, `b343b6d`, `a4295cc`: vollständige
    Offline-Generalprobe, Artefaktnachweis, Firewall-Assertion und Ergebnisdokument.
- Nach Attempt 3 folgten:
  - `6c1d476`: Checkpointer vor Session-Cleanup schließen;
  - `3e9e250`: redigierter kumulativer Live-Smoke-Bericht.
- Verwendete Dokumente:
  - `docs/RUN_3C_OFFLINE_RESULT.md`;
  - `docs/LIVE_WEB_SMOKE_REPORT.md`;
  - `docs/RUN_3C_PHASE2_DRY_RUN_RESULT.md`;
  - `docs/LIVE_LLM_SMOKE_REPORT.md`.
- Es existiert kein zusätzlicher sicherer Attempt-3-Rohlog. Die fünf lokalen
  `.log`-Dateien sind ignoriert, ungetrackt und wurden zuletzt vor dem 22. Juli
  2026 verändert; sie sind daher kein Attempt-3-Nachweis und wurden nicht
  inhaltlich verwendet.

## 3. Chronologische Attempt-3-Timeline

Der exakte UTC-Startzeitpunkt wurde vor dem frühen Abbruch nicht persistiert.
Belegt sind das Datum 22. Juli 2026, die Reihenfolge, die externe Requestzahl
und eine aktive Gesamtlaufzeit von ungefähr 30 Sekunden. Wo keine belastbare
Zeit vorhanden ist, steht ausdrücklich `not_available`.

| Zeitpunkt | Schritt | HTTP/API-Route oder Harness-Funktion | Extern | Provider | Route-ID / Model-Ref | Sicherer Status / Reason-Code | Artefakt-/Session-ID | Ergebnis |
|---|---|---|---|---|---|---|---|---|
| 2026-07-22, genaue Zeit `not_available` | Attempt initialisieren | `prepare()`, `_configure_environment()`, `_seed_infrastructure()` | nein | – | – | neue UUID und neues Temp-Verzeichnis | Attempt `7804e94a11da4764b6836a71ec965fc5` | bestanden |
| danach | D0-Bootstrap | `POST /projects`, `/sources/text`, `/imports`, `/decision`, `/primary-application`, `/runs` | nein | – | – | kein unlabelled Provideraufruf | Projekt-/Run-IDs nach Cleanup `not_available` | bestanden und in Temp-DB persistiert |
| danach | A2-Preflight | `_run_preflight()` → produktives Provider-Gateway | ja | OpenAI | `openai_gpt_56_terra_candidate` / Model-Ref `not_available` | HTTP 200; `pass` | Preflight-ID/Fingerprintwert `not_available` | bestanden und persistiert |
| danach | LIVE-02A Missing Input | `POST /runs/{run}/fields/VC.BUSINESS_TARGETS_MODEL.EDITOR/redrafts`, Operation-/Suggestion-Read | ja | OpenAI | `openai_gpt_56_terra_candidate` / Model-Ref `not_available` | `model_generated`; `missing_inputs`; keine erfundene Marktzahl | Suggestion-/Manifest-ID `not_available` | bestanden und persistiert |
| danach | Public-safe Research vorbereiten | `PUT /research-brief`, Brief-Approval, `POST /queries/plan`, Query-Approval | nein | – | deterministischer Planner / Firecrawl als Zieltool | Firewall `allow`; Approval `approved` | Brief-/Approval-ID `not_available` | bestanden und persistiert |
| danach | Research ausführen | `POST /research-briefs/{id}/run` → `brief_service.run()` → `research_executor()` → `FirecrawlProvider.search()` | ja | Firecrawl | `firecrawl` / kein Modell | HTTP 502 → `ProviderError` → persistiert `provider_error` | ResearchTask-/Operation-/ToolInvocation-ID `not_available` | fehlgeschlagen; API-Antwort 200 mit `execution_mode=live`, null Resultaten |
| danach | Kandidaten lesen/selektieren | `GET /projects/{id}/research-results`; Harness-Auswahl | nein | – | – | `live_e2e_blocked_insufficient_external_evidence` | keine Result-/Source-ID | erster sichtbarer Harness-Stopp |
| – | Source Import | `POST /research-results/{id}/import` | nein | Firecrawl | – | `not_run` | – | nicht ausgeführt |
| – | Anchor-Vorbereitung | `GET /research-results/{id}/anchor-passages` | nein | – | – | `not_run` | – | nicht ausgeführt |
| – | Human Gate | `save_session(ReviewSession)` und Quote-Hash-Ausgabe | nein | – | – | `not_run` | keine Review-Session, kein State Hash | nicht erreicht |
| – | Market-Preflight | `_run_preflight()` | nein | Anthropic | geplant `anthropic_sonnet_5_candidate` / Model-Ref `not_available` | `not_run` | – | nicht ausgeführt |
| – | MarketComparison | `POST /market-comparisons`, `GET /market-comparisons/{id}` | nein | Anthropic | geplant `anthropic_sonnet_5_candidate` / Model-Ref `not_available` | `not_run` | – | nicht ausgeführt |
| – | LIVE-02B | Redraft mit exakt freigegebenen External Anchors | nein | OpenAI | geplant `openai_gpt_56_terra_candidate` | `not_run` | – | nicht ausgeführt |
| – | LIVE-02C | Redraft `shorten` | nein | OpenAI | geplant `openai_gpt_56_terra_candidate` | `not_run` | – | nicht ausgeführt |
| – | LIVE-03 Read/Accept/Replay | Suggestion Read, scoped Accept, Replay, DraftVersion Reads | nein | – | – | `not_run` | – | nicht ausgeführt |
| nach Stopp | Cleanup | Attempt-Stand `engine.dispose()` und `_remove_session_root()` | nein | – | – | Checkpoint-Dateilock; später Recovery-Cleanup | Attempt-Verzeichnis `7804…` | Temp-DB/Sources/Exports entfernt; zunächst `checkpoints.db` übrig, danach vollständig entfernt |

## 4. Exakte Fehlerstelle

Es gibt zwei Ebenen, die getrennt werden müssen.

### 4.1 Kausaler externer Fehler

| Merkmal | Befund |
|---|---|
| `first_failing_step` | Firecrawl Search innerhalb des Research Executors |
| sichere Fehlerklasse | `provider_error`; zentraler HTTP-Klassifikator würde HTTP 502 als `provider_outage` einordnen |
| Exception-Typ | `app.research.providers.base.ProviderError` |
| HTTP-Status | `502` |
| Provider erreicht | `yes` |
| Persistenz | nach Anlage/Commit von ResearchTask und AsyncOperation; Task, Operation, ToolInvocation und ControlResult wurden anschließend als fehlgeschlagen persistiert |
| Ergebnis-/Source-Persistenz | vor ResearchResult, SourceDocument, SourceVersion, Fragment und EvidenceAnchor |
| Kosten-/Callzählung | Firecrawl-Call wurde vor Transport als ein Call gezählt; Credits/Kosten nach Fehler `not_available`; beide vorherigen LLM-Aufrufe waren bereits ausgeführt |
| Retryable | HTTP-Readiness-Semantik: `yes` (`provider_outage`); konkrete Research-Exception trägt generisch `retryable=False` und der Executor persistiert nur `provider_error` |

Relevante Stellen:

- `backend/app/research/providers/firecrawl.py`,
  `FirecrawlProvider._raise_for_status()` und `search()`, Zeilen 54–59 und 71–98:
  HTTP-Status ab 400 wird zu `ProviderError`; nach HTTP 502 entsteht kein
  `SearchOutcome`.
- `backend/app/research/executor.py`, `research_executor()`, Zeilen 120–247:
  Task/Operation werden vor dem Provideraufruf persistiert; typisierte
  Providerfehler setzen Task und Operation fail-closed auf fehlgeschlagen.
- `backend/app/research/brief_service.py`, `run()`, Zeilen 602–662:
  Task wird committed, der Executor synchron aufgerufen und die Route liefert
  anschließend Task-ID, Ergebniszahl und Execution Mode.
- `backend/app/evaluation/preflight.py`, `classify_provider_error()` und
  `_retryable_reason()`, Zeilen 118–151: HTTP 5xx wird als retryable
  `provider_outage` klassifiziert. Diese feinere Information wird im Research
  Executor aktuell nicht übernommen.

### 4.2 Sichtbarer Harness-Stopp

| Merkmal | Befund |
|---|---|
| `first_failing_step` auf Harness-Ebene | Kandidatenauswahl nach Research-Run |
| `safe_reason_code` | `live_e2e_blocked_insufficient_external_evidence` |
| Exception-Typ | `HarnessFailure` |
| HTTP-Status an dieser Stelle | keiner; die Research-Run-Route hatte 200 geliefert |
| Provider erreicht | bereits zuvor `yes` |
| Persistenz | nach persistiertem Research-Fehler und vor Source Import/Review-Session |
| Kosten-/Callzählung | nach zwei LLM-Calls und einem Firecrawl-Call |
| Retryable | Harness selbst führt keinen Retry aus; neue Live-Ausführung ist nicht autorisiert |

Die ausgeführte Attempt-Version `a4295cc` enthält diese Prüfung in
`scripts/run_live_llm_phase2.py`, `prepare()`, damalige Zeilen 1064–1087.
Der aktuelle Stand enthält dieselbe fachliche Prüfung in Zeilen 1077–1100.

## 5. Root Cause und Klassifikation

### Hauptklasse: `PROVIDER_OR_CONFIGURATION`

Direkte Evidenz:

1. Der Firecrawl-Request wurde tatsächlich gesendet und mit HTTP 502 beantwortet.
2. Der Adapter erzeugte deshalb kein `SearchOutcome` und keine Kandidaten.
3. Der produktive Executor persistierte den typisierten Fehler, ohne auf Fake
   zurückzufallen.
4. Die vorherigen A2-Schritte und der public-safe Planner-/Firewall-/Approval-
   Pfad bestanden.
5. Der frühere LIVE-01-Smoke hatte denselben Firecrawl-Adapter mit drei Calls
   erfolgreich gegen eine reale öffentliche Domain ausgeführt. Dies beweist
   keine Verfügbarkeit während Attempt 3, widerspricht aber einer dauerhaft
   grundsätzlich fehlenden Adapterintegration.

Der genauere Provider-interne Grund für HTTP 502 bleibt `UNKNOWN`. Deshalb wird
nicht behauptet, Firecrawl selbst, dessen Upstream oder ein Provider-Gateway
habe sicher die Störung verursacht. Die belastbare Grenze ist
`provider/server-side HTTP 502`.

### Verwarfene Hauptklassen

| Klasse | Warum nicht Hauptursache |
|---|---|
| `HARNESS_DEFECT` | Der separate Checkpoint-Cleanup-Defekt trat erst nach dem fachlichen Stopp auf. Die Source-Knappheit wäre auch bei perfektem Cleanup eingetreten. |
| `PRODUCT_CODE_DEFECT` | Adapter und Executor verhielten sich fail-closed wie implementiert: kein Resultat, kein Import, keine Evidenz, kein Fake-Fallback. Es gibt keinen Nachweis, dass Produktcode HTTP 502 erzeugte. Die grobe Diagnose `provider_error` ist eine Observability-Lücke, nicht die Ursache des Ausfalls. |
| `TEST_DATA_OR_REVIEW_GATE` | Der synthetische D0-Brief, Registry-Feld-Seed, Planner, Firewall und Approval bestanden. Der Human Gate wurde nie erreicht. |
| `GROUNDING_OR_SCHEMA` | LIVE-02A bestand strukturierte Ausgabe, Missing-Input- und Halluzinationsprüfung. Der Fehler entstand danach im Webtransport. |
| `QUALITY_ACCEPTANCE` | LIVE-02B/C und Human Review wurden nicht ausgeführt. |
| `BUDGET_OR_TIMEOUT_GUARD` | Das Kostenbudget war ausreichend; kein Guard blockierte. Der dokumentierte Fehler war HTTP 502, nicht ein Client-Timeout. |
| `SECURITY_OR_POLICY_GATE` | Firewall und Approval bestanden, `execution_mode=live` erreichte den Provider. Kein Security-/Policy-Block ist belegt. |
| `UNKNOWN` | Der interne Ursprung des 502 ist unbekannt, die Hauptklasse an der Integrationsgrenze aber durch HTTP 502 und `ProviderError` ausreichend bestimmt. |

### Reichweite

- Betroffen war der echte Firecrawl-Recherchetransport in Attempt 3.
- Produktnutzer hätten während derselben Providerstörung einen fehlgeschlagenen
  ResearchTask mit sicherem `provider_error` und ohne Ergebnisse erhalten.
- LLM-Feldvorschlag, Grounding und Missing-Input-Verhalten waren bis LIVE-02A
  nicht betroffen.
- MarketComparison, Anchor-Auswahl, Accept und Draft-Versionierung wurden nicht
  erreicht; über deren Live-Verhalten erlaubt Attempt 3 keine Aussage.
- Der Cleanup-Defekt war nur Harness-/Windows-Prozesslebenszyklus, nicht der
  öffentliche Produktpfad.

## 6. Live-Request- und Kostenledger

Exakte Start-/Endzeitpunkte, Tokenmengen und tatsächliche CHF-Kosten wurden bei
den frühen Abbrüchen nicht in einen erhaltenen redigierten Ledger geschrieben.
Sie werden nicht rekonstruiert oder erfunden. Die Beträge unten sind
ausdrücklich konservative Vorabreservierungen, keine Actuals.

| Attempt | Attempt-ID | Request | Provider | Route/Model-Alias | Zweck | Start | Ende | HTTP-Ergebnis | Input Tokens | Output Tokens | Geschätzte Kosten CHF | Tatsächliche Kosten CHF |
|---|---|---:|---|---|---|---|---|---|---:|---:|---:|---:|
| 1 | `not_available` | 1 | OpenAI | A2-Primärroute; exakter Model-Ref `not_available` | A2-Preflight | `not_available` | `not_available` | 200 | `not_available` | `not_available` | `0.007134` konservativ | `not_available` |
| 2 | `not_available` | 1 | OpenAI | A2-Primärroute; exakter Model-Ref `not_available` | A2-Preflight | `not_available` | `not_available` | 200 | `not_available` | `not_available` | `0.007134` konservativ | `not_available` |
| 3 | `7804e94a11da4764b6836a71ec965fc5` | 1 | OpenAI | `openai_gpt_56_terra_candidate`; Model-Ref `not_available` | A2-Preflight | `not_available` | `not_available` | 200 | `not_available` | `not_available` | `0.007134` konservativ | `not_available` |
| 3 | `7804e94a11da4764b6836a71ec965fc5` | 2 | OpenAI | `openai_gpt_56_terra_candidate`; Model-Ref `not_available` | LIVE-02A | `not_available` | `not_available` | 200 | `not_available` | `not_available` | `0.158527` konservativ | `not_available` |
| 3 | `7804e94a11da4764b6836a71ec965fc5` | Web 1 | Firecrawl | `firecrawl`, kein Modell | public-safe Search | `not_available` | `not_available` | 502 | n/a | n/a | `not_available` | `not_available` |

Kumuliert:

| Messwert | Wert |
|---|---:|
| Echte LLM-Requests Attempts 1–3 | `4` |
| Echte Firecrawl-Requests Attempts 1–3 | `1` |
| Konservativ geschätzte LLM-Kosten Attempts 1–3 | CHF `0.179929` |
| Tatsächliche LLM-Kosten | `not_available` |
| Tatsächliche Firecrawl-Credits/Kosten | `not_available` |
| Fake-Fallback beobachtet | `no` |

Die vor Attempt 3 vorgegebene Basis von zwei Requests und CHF `0.014268`
wurde beibehalten. Attempt 3 fügte zwei LLM-Requests mit konservativ CHF
`0.165661` hinzu. Alle genehmigten Call- und Kostenobergrenzen wurden
eingehalten.

## 7. Session-, Cleanup- und Security-Nachweis

| Prüfung | Befund |
|---|---|
| Neue Attempt-ID | `yes`: `prepare()` erzeugt `uuid.uuid4().hex`; `mkdir(exist_ok=False)` verhindert Wiederverwendung; Attempt 3 nutzte `7804…` |
| Alte Session wiederverwendet | `no`: `resume()` wurde nicht aufgerufen; vor dem Human Gate existierte kein `session.json` |
| Session-Hash/Ablauf | `not_applicable` für Attempt 3: `ReviewSession` wird erst nach zwei Imports, Market-Preflight und Passageprüfung erzeugt; diese Stelle wurde nicht erreicht |
| Temporäre DB | entfernt |
| Sources/Exports | entfernt; es wurden keine Live-Sources importiert |
| Checkpoint | nach dem ersten Cleanup wegen offenem SQLite-Handle übrig; Recovery-Cleanup nach Prozessende erfolgreich |
| Aktueller Session-Root | vorhanden und leer (`0` Einträge) |
| Attempt-3-Pfad | nicht vorhanden |
| `backend/var/verify_e2e.db` | nicht vorhanden |
| Getrackte lokale DB-/WAL-/SHM-/Logartefakte | keine |
| Ungetrackte Attempt-3-Artefakte im Repository | keine |
| Secrets/Rohprompts/Provider-Body persistiert | kein Nachweis; redigierter Report enthält keine; keine Attempt-Session oder Providerantwort blieb erhalten |

Die fünf vorhandenen lokalen Logs sind gemäß `.gitignore` ignoriert und
datieren vor Attempt 3. Sie wurden weder als Attempt-Beleg verwendet noch
verändert. `.env`-Werte, Schlüssel, Rohqueries, Prompttexte und vollständige
Providerantworten wurden nicht gelesen oder in dieses Dokument übernommen.

Der ausgeführte Attempt-Stand `a4295cc` rief vor dem rekursiven Delete nur
`engine.dispose()` auf und verwendete `shutil.rmtree(..., ignore_errors=True)`.
Der offene LangGraph-SqliteSaver blieb dadurch unter Windows unbemerkt. Commit
`6c1d476` ergänzt `app.runs.graph.close_checkpointer()` sowie
`_close_runtime_resources()` vor dem Delete. Der aktuelle Session-Root ist leer.

## 8. Dry-Run-Paritätsprüfung

Der zusammenhängende Offline-Test
`test_phase2_prepare_resume_full_offline_dry_run` verwendete die produktiven
Harness-Einstiegspunkte in getrennten Prozessen, 67 HTTP-/BFF-Aufrufe, sechs
simulierte LLM-Transportrequests und drei simulierte Firecrawl-Operationen. Er
ersetzte nur den externen Transport. Bis zur fehlerhaften Firecrawl-Antwort ist
die Orchestrierung repräsentativ; die reale Fehlerantwort war im vollständigen
Happy-Path-Dry-Run nicht vertreten.

| Schritt | Offline-Adapterpfad | Live-Pfad | Gleiche Funktion/Route? | Gleiche Registry-/Feldbindung? | Gleiche Session-Serialisierung? | Gleiche Statusliterale? | Gleiche Provider-Antwortform? | Gleiche Policy-/Pricing-Inputs? | Erklärende Differenz |
|---|---|---|---|---|---|---|---|---|---|
| D0-Bootstrap | produktive HTTP-Routen; Transportadapter blockieren unlabelled Calls | dieselben HTTP-Routen | ja | ja | noch nicht relevant | ja | n/a | gleiche D0-Policy | keine relevante Differenz |
| A2-Preflight | `_run_preflight()` + Test-`ProviderResult(PreflightPong@v1)` | `_run_preflight()` + OpenAI | ja | ja | noch nicht relevant | ja, `pass` nach `28bbfce` | gleiches validiertes Schema; konkrete Tokens/Modellantwort verschieden | gleiche Gate-Struktur, andere reale Preis-/Fingerprintwerte | bestand in beiden Läufen |
| LIVE-02A | produktiver Redraft-/Gateway-/Grounding-Pfad, LLM-Transportdouble | derselbe Pfad, echter OpenAI-Transport | ja | ja: `VC.BUSINESS_TARGETS_MODEL.EDITOR`, Requirement 3.1, Skill `a2.value_creation_3_1`, Marker 3.1–3.3 | noch nicht relevant | ja | gleiches strukturiertes Vertragsschema | gleiche Policies; konkrete Preise/Model-Ref anders | bestand in beiden Läufen |
| Brief/Planner/Firewall/Approval | produktive HTTP-/Servicepfade | dieselben Pfade | ja | ja | noch nicht relevant | ja | deterministisch, kein Provider | gleiche D0-/Firewall-Policy | bestand in beiden Läufen |
| Research Search | `FirecrawlProvider.search` wurde durch Testtransport ersetzt und lieferte `SearchOutcome` mit zwei Kandidaten | echte `FirecrawlProvider.search`; HTTP 502 vor `SearchOutcome` | ja bis zur Transportgrenze | ja | noch nicht relevant | Executorstatuspfad gleich | nein: Erfolg mit zwei Kandidaten versus `ProviderError` | gleiche öffentliche D0-Policy; reale Providerkonfiguration statt Testoverride; Firecrawl-Credits unbekannt | **erklärt den Stopp** |
| Source Import und Passagen | zwei erfolgreiche Test-`fetch`-Outcomes; produktive Import-/Passagenrouten | `not_run` | Codepfad gleich, live nicht erreicht | ja | noch nicht relevant | ja | nicht vergleichbar | nicht vergleichbar | Folge des fehlenden SearchOutcome |
| ReviewSession | produktives `save_session()`, State Hash, Ablauf und zwei Quote-Hashes | `not_run` | Implementierung identisch, live nicht erreicht | ja | live nicht prüfbar | ja | n/a | Fingerprints wären real statt Test | keine Session wegen vorgelagertem Providerfehler |
| Resume/Market/LIVE-02B/C/LIVE-03 | produktives `resume()` und alle HTTP-/BFF-Routen mit Testtransport | `not_run` | Implementierung identisch, live nicht erreicht | ja | live nicht prüfbar | ja | nicht vergleichbar | reale Market-Route/Preise wären anders | keine Live-Aussage möglich |
| Cleanup | produktiver Finalizer im Testprozess; Session vollständig gelöscht | gleicher damaliger Finalizer, aber echter Windows-Dateilock | fachlich ja; Ressourcenlebensdauer unterschied sich | n/a | n/a | n/a | n/a | n/a | sekundärer Harness-Cleanup-Defekt |

Wesentliche Paritätsgrenze: Der Dry Run bewies die vollständige Erfolgsstrecke,
nicht eine vollständige `prepare()`-Fehlerstrecke mit einem echten oder
simulierten HTTP-5xx im Firecrawl-Search. Einzelne Provider-Tests belegen zwar
das fail-closed Verhalten, aber nicht die redigierte Phase-2-Fehlerdiagnose als
zusammenhängenden Lauf.

## 9. Betroffene Dateien und Funktionen

Primärer Fehlerpfad:

- `scripts/run_live_llm_phase2.py`
  - `instrument_live_providers()` – zählt externe LLM-/Webcalls;
  - `prepare()` – Research-HTTP-Pfad und Kandidaten-Mindestzahl;
  - `_run_preflight()`, `_generate_suggestion()`, `_assert_smoke_1()` – zuvor
    bestandene A2-Schritte.
- `backend/app/research/providers/firecrawl.py`
  - `FirecrawlProvider.search()`;
  - `FirecrawlProvider._raise_for_status()`.
- `backend/app/research/executor.py`
  - `research_executor()`;
  - `_safe_provider_code()` und `_safe_provider_detail()`.
- `backend/app/research/brief_service.py`
  - `run()`.
- `backend/app/api/research_briefs.py`
  - `run_research_brief()`.
- `backend/app/evaluation/preflight.py`
  - `classify_provider_error()` und `_retryable_reason()` als feinere 5xx-
    Referenzklassifikation.

Sekundärer Cleanup-Pfad:

- Attempt-Stand `a4295cc`, `scripts/run_live_llm_phase2.py`:
  `prepare()`-Finalizer und `_remove_session_root()`.
- Aktueller Stand:
  - `backend/app/runs/graph.py::close_checkpointer()`;
  - `scripts/run_live_llm_phase2.py::_close_runtime_resources()`;
  - `backend/tests/test_live_llm_phase2_harness.py::test_cleanup_closes_checkpoint_before_removing_session()`.

Nicht ausgeführte und daher nicht als fehlerhaft klassifizierbare Pfade:

- MarketComparison-Executor;
- Anchor-Review und External-Anchor-Erstellung;
- LIVE-02B/LIVE-02C;
- Suggestion Read, scoped Accept, Replay und DraftVersion Reads.

## 10. Vorhandene und fehlende Regressionstests

Vorhanden:

- `test_phase2_prepare_resume_full_offline_dry_run` beweist die vollständige
  erfolgreiche `prepare`-/`resume`-/Market-/Suggestion-/Accept-Strecke über
  produktive HTTP-/BFF-Pfade und die echten Orchestrierungsstellen.
- `test_live_preflight_surfaces_provider_failure_without_demo_fallback`
  simuliert Firecrawl HTTP 503, erwartet `fail` und `provider_outage` und
  beweist keinen Demo-Fallback.
- Firecrawl-Adaptertests beweisen typisierte Fehler bei HTTP-Fehlern und keine
  stillen Privacy-/Fallback-Retries.
- Harness-Unit-Tests beweisen Live-Opt-in, Call-/Kostenreservierung,
  Registry-Statusliteral, Registry-Sektionsmarker, Session-Hash, Ablauf,
  Quote-Hash-Scoping und Report-Redaktion.
- Der nach Attempt 3 hinzugefügte Cleanup-Test öffnet den echten Checkpointer,
  schließt ihn und weist die vollständige Session-Verzeichnislöschung nach.

Fehlt:

- Kein zusammenhängender Phase-2-`prepare()`-Dry-Run injiziert einen
  Firecrawl-HTTP-5xx-/`ProviderError` und prüft gleichzeitig:
  persistierten ResearchTask-/Operation-Fehler, null Resultate, exakten
  redigierten Harness-Reason-Code, Ledgererhalt und vollständigen Cleanup.
- Kein vorhandener Attempt-3-Artefaktledger bewahrt exakte Requestzeiten,
  Token und Actual Cost bei einem Fehler vor `save_session()`.
- Der Harness liest nach `POST /research-briefs/{id}/run` nicht den
  ResearchTask-Fehlercode, bevor er den allgemeineren Grund
  `insufficient_external_evidence` meldet. Dadurch geht die feinere
  `provider_outage`-Diagnose verloren. Das ist eine Diagnose-/Observability-
  Lücke, aber kein belegter Auslöser des HTTP 502.

Gemäß Review-Auftrag wurden keine neuen Tests erstellt oder ausgeführt.

## 11. Empfohlene nächste Aktion

1. Den aktuellen Stopp beibehalten. Es besteht keine Autorisierung für einen
   Provider-Preflight, einen Search-Retry, LLM-Aufrufe oder RUN 4.
2. Für die Primärursache ist anhand der vorliegenden Evidenz kein Produktfix
   gerechtfertigt: Das System hat den Providerfehler sicher und ohne erfundene
   Ergebnisse behandelt.
3. Eine menschliche Entscheidung kann später getrennt wählen zwischen:
   - Live-Akzeptanz als `provider blocked/not completed` schließen; oder
   - einen neuen, eng begrenzten Firecrawl-Readiness-/Search-Retest ausdrücklich
     autorisieren, um einen transienten 502 zu prüfen.
4. Vor einem solchen optionalen Retest wäre ein separater Offline-Fix-Slice
   sinnvoll, der nur die Diagnosequalität verbessert: ResearchTask-Fehlercode
   im Harness auswerten, HTTP-5xx als `provider_outage`/retryable erhalten und
   den redigierten Ledger auch bei frühem `prepare()`-Fehler sichern. Dieser
   Review autorisiert diesen Fix nicht.

Ein weiterer Live-Call wäre ausschließlich zur Prüfung einer möglichen
transienten Providerstörung sinnvoll. Er ist weder zur aktuellen
Fehlerklassifikation erforderlich noch durch diesen Bericht autorisiert.

## 12. Eindeutiger Status

```text
ATTEMPT3_FAILURE_CLASSIFIED_PROVIDER
LIVE_RETEST_NOT_AUTHORIZED
RUN_4_NOT_AUTHORIZED
```

