# RUN 3C Phase 2 – Ergebnis der Offline-Generalprobe

## Ergebnis

Die vollständige Offline-Generalprobe ist bestanden. Der einzelne Integrationstest
`test_phase2_prepare_resume_full_offline_dry_run` ruft die produktiven Harness-
Einstiegspunkte `prepare()` und `resume()` auf, trennt beide durch einen echten
`multiprocessing.spawn`-Prozesswechsel, lädt den serialisierten Zustand neu und
verwendet danach exakt die in `prepare` erzeugten Quote-Hashes.

- Ausgangscommit: `9aa65d7862b464cc15ea0f274299737a4043b3f3`
- Harness-/Regression-Commits: `c6989fe`, `8b79b56`, `b343b6d`
- Alembic-Head: `c3e5a7b9d024`
- Ausführung: 22. Juli 2026, vollständig offline
- Externe Netzwerkrequests: `0`
- Echte LLM-Requests: `0`
- Echte Firecrawl-Requests: `0`
- Kosten: CHF `0`
- Simulierte Providerrequests über die produktive Schnittstelle: `6`
- Simulierte Firecrawl-Operationen über den bestehenden Adapter: `3`
- Beobachtete HTTP-/BFF-Aufrufe im zusammenhängenden Lauf: `67`
- Aktive Harness-Ausführung: `8.948 s`
- Simulierte Human-Wartezeit: `0.201 s`, nicht zur aktiven Laufzeit addiert
- Fake-Fallback: nicht verwendet

Die Testadapter ersetzen ausschließlich die externe Transportantwort von OpenAI,
Anthropic und Firecrawl. Provider-Gateway, Provider-Policy, Preflight, Kostenwächter,
Schema-Validierung, Context Builder, unabhängige Claim-/Grounding-Prüfung,
Persistenz und alle nutzerwirksamen HTTP-Routen bleiben produktiv. DNS-Auflösung
und Socket-Verbindungen sind im Testprozess fail-closed blockiert.

## Kanonische Bindung

Der Lauf liest die Bindung aus den echten Registry-/Portalmetadaten und prüft:

- `field_id = VC.BUSINESS_TARGETS_MODEL.EDITOR`
- `requirement_id = VC.BUSINESS_TARGETS_MODEL.MANDATORY_3_1`
- Portalfrage = `3.1 Describe the business targets and the business model`
- Skill = `a2.value_creation_3_1`
- Registry-/Portalmarker = exakt `3.1`, `3.2`, `3.3`

Die Marker werden im Harness nicht als zweite Regelbasis gepflegt. Der Test
vergleicht `registry.mandatory_questions(...)` mit `resolve_field_config(...)`.

## Zusammenhängender Nachweis der 27 Schritte

Alle IDs stammen aus demselben zuletzt dokumentierten Testlauf. Dessen temporäre
Daten wurden nach dem Auslesen der redigierten ID-Metadaten vollständig gelöscht.

| Nr. | Tatsächlich ausgeführte Route/Funktion | Pfadtyp | Zentrale Assertion | Ergebnis | Erzeugte und wieder gelesene Artefakt-ID |
|---:|---|---|---|---|---|
| 1 | `POST /api/v1/projects` | HTTP/BFF | Drei getrennte synthetische D0-Projekte werden angelegt; kein Bootstrap-Providercall. | bestanden | E2E-Projekt `84f7a214-bede-471d-934e-e4549e2abcfe`; weitere Projekte `e6845cdb-5fce-43f3-97fb-00e00fb89939`, `f76f7b5a-16cb-4cc4-a5d8-cf0cdcc24eaf` |
| 2 | `POST /projects/{id}/sources/text`, `PUT /projects/{id}/primary-application` | HTTP/BFF | Je Projekt existiert genau eine aktuelle Primary Application; Zuordnung wird per GET/Run weiterverwendet. | bestanden | Sources `76aa8758-e9cc-43a5-9579-ffffcae58f9f`, `aa730b72-e52f-4f37-8bc7-75512f2eb4f4`, `f0d17af0-abe9-46a8-9461-304398ab8e25` |
| 3 | `POST /projects/{id}/imports`, `POST /imports/{id}/decision` | HTTP/BFF | Importkandidaten werden über die produktive Entscheidung angenommen; kein direkter Draft-Insert. | bestanden | Kandidat `317f3a49-8601-44eb-98e0-d169a933debc`, Revision `655c0e0a-3ed1-4208-9d99-b62c81444cac` (plus zwei weitere D0-Fälle) |
| 4 | `POST /projects/{id}/runs`, `GET /runs/{run_id}` | HTTP/BFF | Drei Runs mit Snapshot werden abgeschlossen und anschließend gelesen. | bestanden | Runs `4cef5e63-0c2f-4fc3-abf0-139709d66a7b`, `620ab9d2-77a1-4446-9ada-5b6d9a75dbd1`, `6466d9f8-6a86-463c-a851-9426b36458b1` |
| 5 | Harness `_run_preflight` → produktives Provider-Gateway | erlaubter Preflight-/Testadapterpfad | A2-Route `openai_gpt_56_terra_candidate` erreicht den Transportadapter mit `PreflightPong@v1`; kein Fallback. | bestanden | Session `c8a554efafdd403da4ee2365f85bdd8c` friert Route und Preflight-Fingerprint ein |
| 6 | `POST /runs/{run}/fields/{field}/redrafts`, `GET /operations/{id}`, `GET .../suggestions` | HTTP/BFF | Smoke 1 erreicht den A2-Adapter, erzeugt keinen `section_marker_missing`, erfindet keine Marktzahl und persistiert `missing_inputs` samt OpenIssue. | bestanden | Suggestion `25b1c18a-bc2d-4b60-8b19-1fd78523a62a`, OpenIssue `783c15ff-18ff-41e6-b1b7-e7f2075b6715` |
| 7 | `PUT /projects/{id}/research-brief`, `POST /research-briefs/{id}/approve` | HTTP/BFF | Nur ein public-safe D0-Brief wird gespeichert und freigegeben. | bestanden | Research Brief `3393405d-d5c8-49e8-8e4f-02fe72c9711b` |
| 8 | `POST /research-briefs/{id}/queries/plan` | HTTP/BFF | Der echte registry-gestützte Planner liefert freigabepflichtige Planzeilen; der begrenzte Smoke wählt deterministisch die erste. | bestanden | geplante Approval-IDs `1d690108-fa24-4ec1-acf9-d1d3d6e3c9b9`, `e9244064-340e-4888-aa79-12b0453babeb` |
| 9 | Firewall innerhalb `POST .../queries/plan` | HTTP/BFF | Die persistierte Session enthält für die ausgeführte Query exakt `firewall_decision=allow`; der Test behauptet dies explizit. | bestanden | ausgeführte Approval-ID `1d690108-fa24-4ec1-acf9-d1d3d6e3c9b9` |
| 10 | `POST /search-query-approvals/{id}/approve` | HTTP/BFF | Nur die projekt-/briefgebundene, vom Planner erzeugte Query wird explizit freigegeben. | bestanden | Approval `1d690108-fa24-4ec1-acf9-d1d3d6e3c9b9` |
| 11 | `POST /research-briefs/{id}/run`, bestehender Firecrawl-Adapter | HTTP/BFF plus Transport-Testadapter | `execution_mode=live` durchläuft den produktiven Executor; Adaptersequenz ist exakt `search, fetch, fetch`; Socket/DNS bleiben gesperrt. | bestanden | Research Task `09d7493f-8fd2-447e-8aad-8ce064420ac8` |
| 12 | `POST /research-results/{id}/import` | HTTP/BFF | Zwei unterschiedliche Kandidaten werden explizit importiert; Search-Snippets bleiben reine Resultatmetadaten. | bestanden | Sources `4583d8e3-ee84-493f-ad3c-a851b6ebac89`, `5c59314d-a110-4d02-a614-dd8bf6dbf3ec`; Versions `2b1709f6-ddf1-4195-930f-ae1fcc3b3d35`, `e8bb1362-682b-4b0a-abec-d0a15a23c6bc` |
| 13 | `GET /research-results/{id}/anchor-passages` | HTTP/BFF | Exakte, höchstens 300 Zeichen lange Passagen werden aus aktuellen sicheren SourceVersions gelesen; kein Snippet-Feld wird projiziert. | bestanden | Fragments `7db312d70f194a8ba53f1b9a53ef1f57`, `da6c2d16b283413e8a34ceb533257e88` |
| 14 | Harness `save_session(ReviewSession)` | erlaubter lokaler Harness-State | `prepare` schreibt genau eine integritätsgeschützte, befristete Session ohne Keys, Rohquery oder Volltextantwort. | bestanden | Session `c8a554efafdd403da4ee2365f85bdd8c`, State Hash `b6a2f553a5f850c828778bcbebdb9e1a13eb51f798ab0d7b11a701ecfa722ffc` |
| 15 | neuer Spawn-Prozess → Harness `load_session(...)` | erlaubter lokaler Harness-State | `resume` lädt nach vollständigem Prozesswechsel dieselbe Session und denselben State Hash. | bestanden | Session `c8a554efafdd403da4ee2365f85bdd8c` |
| 16 | Harness `validate_anchor_approval(...)` | erlaubtes Human-Gate | Nur die zwei exakten Hashes werden akzeptiert; manipulierte Route, Session oder ein unbekannter Hash werden vor `resume` fail-closed abgelehnt. | bestanden | Quote Hashes `3db01a110c2993de9812157bbcb8286d379737bd3ea5c0cdbdc5532835d67bfb`, `dc70bca6b20fd49439ad399a3419549b4fdabd15a64217e5cdcf7dfc4e039440` |
| 17 | `POST /research-results/{id}/review` | HTTP/BFF | Nach erneutem HTTP-Lesen und Re-Hashing werden nur die freigegebenen Resultate inhaltlich geprüft. | bestanden | Resultate `ed29ff77-7913-483b-824d-b17eda490d51`, `f048a904-5c41-4000-b68b-f3f609c293bf` |
| 18 | `POST /research-results/{id}/external-anchors` | HTTP/BFF | Die finale DB-Assertion findet exakt die beiden genehmigten Anchors und keine aus Search-Snippets. | bestanden | Anchors `8d0b2415-69b3-4cf4-80cd-ed1bea6cad6e`, `9ca6d4da-a813-4276-a4e3-6ab8ca3fa60c` |
| 19 | `POST /projects/{id}/market-comparisons`, `GET /market-comparisons/{id}` | HTTP/BFF plus Transport-Testadapter | Produktives Market-Gateway und `MarketComparisonResult@v1`; zwei aktuelle Quellen ergeben `limited` plus `limited_external_evidence`; alle Item-Anker sind Teil der Freigabe. | bestanden | Comparison `2b210b0d-7cd2-49b4-9273-c7f7affed261`, Item `d497f761-a975-4c57-9a75-b0b481728e25` |
| 20 | `POST .../redrafts` mit `selected_anchor_ids`, anschließend Operation-/Suggestion-Read | HTTP/BFF | Smoke 2 verwendet ausschließlich die beiden ausgewählten Anchors; Manifest enthält dieselbe MarketComparison und aktuelle SourceVersions. | bestanden | Suggestion `c5015662-86b7-4519-8a22-8f8e712033fe`, MarketComparison `2b210b0d-7cd2-49b4-9273-c7f7affed261` |
| 21 | `POST .../redrafts` mit `improvement_mode=shorten` | HTTP/BFF | Smoke 3 durchläuft Schema und unabhängiges Grounding; Ausgabe ist kürzer und enthält keine neue konkrete Zahl oder Organisation. | bestanden | Redraft-Operation `009fc471-f62a-49c3-97a2-3826a1242c71` (drei Redraft-Operationen im Lauf insgesamt) |
| 22 | `GET /runs/{run}/fields/{field}/suggestions` | HTTP/BFF | Persistierte Smoke-2- und Smoke-1-Suggestions werden über die öffentliche Read-Route gelesen. | bestanden | Suggestions `c5015662-86b7-4519-8a22-8f8e712033fe`, `25b1c18a-bc2d-4b60-8b19-1fd78523a62a` |
| 23 | `POST /runs/{run}/fields/{field}/suggestions/{id}/accept` | HTTP/BFF | Scoped Accept prüft Base-Version/Manifest erneut und verwendet den bestehenden Draft-Update-Pfad. | bestanden | Suggestion `c5015662-86b7-4519-8a22-8f8e712033fe` → DraftVersion `e71cc331-a009-438e-9c9d-82b7c5b89110` |
| 24 | identischer scoped Accept mit gleichem `Idempotency-Key` | HTTP/BFF | Replay liefert `idempotent_replay=true` und exakt dieselbe DraftVersion; paralleler Replay-Test bestand zusätzlich 10/10 Läufe. | bestanden | erneut DraftVersion `e71cc331-a009-438e-9c9d-82b7c5b89110` |
| 25 | `GET /runs/{run}/fields/{field}` und finale DB-Zählung | HTTP/BFF; DB nur Abschlussassertion | Versionszahl steigt exakt um eins; die neue Version ist aktuell. | bestanden | neue DraftVersion `e71cc331-a009-438e-9c9d-82b7c5b89110` |
| 26 | `GET /runs/{run}/fields/{field}/versions/{version_id}` | HTTP/BFF | Sowohl neue als auch ursprüngliche immutable Version sind projekt-/run-gescoped lesbar. | bestanden | Originalversion `31748b80-cdae-4e23-8787-95eaeac0e52c` |
| 27 | Harness-Finalizer `_remove_session_root(...)` plus Test-Artefaktscan | erlaubter Cleanup | Sessionverzeichnis, `phase2.db`, Sources, Checkpoints, Exporte, Reviewartefakt und Trace existieren nach dem Lauf nicht mehr; Engine wird vor Windows-Delete disposed. | bestanden | entfernte Session `c8a554efafdd403da4ee2365f85bdd8c`; keine verbleibende lokale Artefakt-ID |

## Behobene, durch den vollständigen Lauf belegte Lücken

1. Der echte Registry-Planner liefert für ein Modul mehrere gültige Zwecke. Das
   Harness verlangte fälschlich genau eine Zeile. Es führt nun begrenzt die erste
   freigegebene Planzeile aus, ohne den Planner zu umgehen.
2. Exakte Human-Review-Passagen waren nur per direktem DB-Zugriff verfügbar.
   `GET /research-results/{id}/anchor-passages` liefert nun eine gebundene,
   sichere und snippet-freie HTTP-Projektion.
3. Historische DraftVersions waren im API-E2E nicht einzeln lesbar.
   `GET /runs/{run}/fields/{field}/versions/{version}` ist additiv und streng
   auf Run, Workspace, Draft und Feld begrenzt.
4. Der Provider-Gateway-Real-Eval-Guard verlangte für eine projektgebundene
   `MC.market_comparison` fälschlich eine nicht existierende AnalysisRun-
   Confirmation. Die Ausnahme gilt nun ausschließlich für `run_id=None`,
   `origin=public_source`, `sensitivity=public` und dieses Profil; alle anderen
   Real-Eval-Gates bleiben unverändert.
5. SQLite-Verbindungen verhinderten unter Windows den Session-Cleanup. Das
   Harness disposed den Engine-Pool vor dem rekursiven Entfernen.
6. Ein gleichzeitiger Accept-Replay konnte zwischen initialer Idempotenzabfrage
   und Status-Read `409` liefern. Nach beendetem Snapshot wird nun zuerst der
   bereits committed Idempotenzdatensatz wiedergegeben.
7. Tief verschachtelte Pytest-Pfade überschritten unter Windows das Pfadlimit.
   Jeder Lauf verwendet jetzt ein neues kurzes, zufälliges Temp-Verzeichnis.

## Ausgeführte Gates

| Gate | Befehl | Gemessenes Ergebnis |
|---|---|---|
| Vollständige Dry-Run-Integration | `.venv\Scripts\python.exe -m pytest tests\test_live_llm_phase2_full_dry_run.py::test_phase2_prepare_resume_full_offline_dry_run -q -p no:warnings` | bestanden, letzter dokumentierter Lauf `19.9 s`; zusätzlicher finaler Firewall-Assertionslauf bestanden |
| Alle Phase-2-Harness-Tests | `pytest tests\test_live_llm_phase2_harness.py tests\test_live_llm_phase2_full_dry_run.py` | `14 passed`, `20.3 s` |
| Accept-Race-Regression | derselbe parallele Accept-Test zehnmal | `10/10 passed`, `67.9 s` |
| Vollständiges Pytest | `pytest -q -p no:warnings` | bestanden, `304.3 s`, vier bestehende Skips |
| Vollständiges Vitest | `corepack pnpm test` | bestanden, `42.9 s` |
| ESLint | `corepack pnpm lint` | bestanden, `8.0 s` |
| TypeScript | `corepack pnpm exec tsc --noEmit` | bestanden, `6.8 s` |
| Production Build | `corepack pnpm build` | bestanden, `27.0 s`, 32 statische Seiten generiert |
| Vertragsvalidator | Agent-Schema-/Role-Skill-Tests plus RUN-3B-/RUN-3C-Runtime-OpenAPI-Tests | `25 passed`, `9.1 s` |
| Migration Fresh/Down/Up | `alembic upgrade head`, `downgrade b2d4f6a8c013`, `upgrade head`, `current` | bestanden, Head wieder `c3e5a7b9d024`, `6.8 s` |
| Playwright | durch `verify_all.ps1`: `playwright test --workers=1` plus Golden Path, Import Functional und Review Truth | bestanden |
| Gesamtgate | `powershell -File scripts\verify_all.ps1` | Exit `0`, `630.7 s`; Backend, Migration, Vitest, Lint/TS/Build, Playwright, DOCX, API-Smoke, Marker und Legacy-Guard grün |
| Diffprüfung | `git diff --check` und `git diff --cached --check` | bestanden |
| Secret-/Artefaktscan | Signaturscan über staged Diff; Track-Namensscan; finaler Temp-/DB-/Source-/Checkpoint-/Export-Scan | bestanden; nur die vorgesehenen `.env.example`-Dateien sind getrackt |

## Migration, Verträge und Cleanup

Es wurde keine neue Migration benötigt. Die beiden additiven Read-Routen sind
runtime-OpenAPI-fähig und verwenden Pydantic-Verträge. Der vollständige
Fresh/Down/Up-Roundtrip der bestehenden RUN-3C-Migration blieb unverändert grün.

Der letzte Lauf hinterließ weder Sessionzustand noch Testdatenbank, Sources,
Checkpoints, Exporte, Providerantworten oder Reviewtexte. `.env.local`,
`backend/.env` und andere lokale Benutzerkonfigurationen wurden nicht verändert.

## Statuswahrheit und Haltepunkt

- Offline-Harness-/API-E2E: `passed`
- Live-Provider/Netzwerk: `not_run`
- Live-Kosten: CHF `0`
- Human Quality Review: `pending`
- RUN 4: `not_started`

Dieser Nachweis autorisiert selbst keinen Provideraufruf. Er erfüllt den
angeforderten Offline-Haltepunkt vor einem separat freizugebenden dritten
Live-Retest.
