# RUN 3B – Ergebnis

Stand: 21. Juli 2026

Status: Offline-Implementierung abgeschlossen; vor echten Provider-Aufrufen und vor RUN 3C gestoppt.

Ausgangscommit: `6e8815d1c62382039ff61f8fb87f1e164a0429bc`

RUN-3A-Commit: `6e8815d` (`feat: complete run 3a readiness and research input`)

RUN-3B-Commits vor diesem Ergebnisdokument:

- `523a292` – `feat: harden run 3b research provenance`
- `dcbfeab` – `test: cover run 3b research boundaries`
- `cb7a610` – `fix: make run 3b rollback fail safe`

Migrations-Head: `b2d4f6a8c013` auf `a1c3e5f7b902`

Es wurden keine echten Firecrawl-, Web-, LLM- oder sonstigen Provider-Aufrufe
ausgeführt. Alle automatischen Tests verwendeten lokale Fixtures,
Testadapter oder ausdrücklich konfigurierte Fake-Provider. RUN 3C wurde nicht
begonnen.

## 1. Preflight und Baseline

- RUN 3A lag als eigener Commit vor; der Ausgangs-Working-Tree war sauber.
- Der Start-HEAD entsprach exakt `6e8815d1c62382039ff61f8fb87f1e164a0429bc`.
- `git diff --check` war vor der Umsetzung fehlerfrei.
- Die vollständige Offline-Baseline mit `scripts/verify_all.ps1` war vor der
  Produktänderung grün (ca. 681 Sekunden).
- Der Signatur-Scan fand nur zwei bereits vorhandene, synthetische Werte in
  Security-Tests. Beide wurden als Testwerte geprüft. Es wurden keine echten
  Secrets gefunden.
- Keine Datenbank, kein Log, kein `private_inputs`-Inhalt, kein Rohprompt und
  keine Providerantwort war oder wurde getrackt.
- `IMPLEMENTATION_PLAN.md` und `E2E_ACCEPTANCE_MATRIX.md` waren weder im
  Repository noch in den bereitgestellten Anhängen vorhanden. Es wurden keine
  Ersatzanforderungen erfunden.

Verbindliche Quellen waren der Masterprompt, der RUN-3-Plan einschließlich
Execution Override und RUN-3B-Prompt, die Discovery- und bisherigen
Ergebnisdokumente sowie die Verträge unter `final_backend_contracts_v1_1/`.

## 2. Umgesetzter fachlicher Umfang

### 2.1 Zielbasierter Query Planner

Der bestehende Planner erzeugt neue Queries ausschließlich aus
`research_goal`, Region, optionalen `search_tags` und dem ausgewählten
Research-Modul. Die temporäre RUN-3A-Projektion in die alte Ontologie wurde
entfernt. Legacy-Felder werden nur noch für alte Briefversionen verwendet,
denen ein `research_goal` fehlt.

Rohprojekttext, Projekt-/Codenamen, Partner- oder Personennamen, Budgets,
Kontaktangaben, NDA-Inhalte und Review-Kommentare werden nicht in neue
öffentliche Queries übernommen.

### 2.2 Firewall, Approval und Idempotenz

Der bestehende Query-Firewall-/Approval-Pfad wurde erweitert, nicht
dupliziert. Approval und Research Run sind workspace-, projekt-, brief- und
modulgebunden. Änderungen invalidieren die vorherige Freigabe. Direkte API-
Aufrufe können blockierte, abgelaufene, verbrauchte oder fremde Approvals
nicht umgehen.

Neue Clients senden immer einen `Idempotency-Key`. Bestehende Clients bleiben
kompatibel. Identische Approval- und Run-Replays liefern dasselbe Ergebnis;
abweichende Payloads unter demselben Key werden als Konflikt abgelehnt.

### 2.3 Firecrawl-Adapter und sicherer Quellenimport

Es wurde ausschließlich der vorhandene Firecrawl-Adapter verwendet. Es gibt
keinen neuen Crawler, Browser oder zweiten Fetch-Stack.

Der Import prüft fail-closed:

- nur `http`/`https`, keine URL-Credentials;
- Start-, Redirect- und Final-URL gegen Loopback, private, link-local,
  reservierte, interne und Metadata-Ziele;
- Redirectlimit, verifizierbare Redirectkette, Timeout, Content-Type und
  Inhaltsgröße;
- abweichende Final-URL ohne überprüfbare Kette als
  `redirect_chain_unverified`;
- Providerfehler als redigierte Reason-Codes mit `retryable`;
- Fake-/Demo-Ergebnisse als nicht importierbar.

Öffentliche Webseiten bleiben untrusted data. Ein deterministischer
Injection-Scan setzt verdächtige Inhalte auf `quarantined`. Erst eine
ausdrückliche menschliche Bestätigung setzt `human_released` und erlaubt die
Nutzung als Markt- oder Drafting-Kontext.

Gespeichert werden nur normalisierte Provenienzfelder: kanonische und
ursprüngliche URL, Titel/Publisher, Retrievalzeit, Provider, Execution Mode,
Research-Task-/Approval-ID, Content-Type, Hash und Source-Version. Vollständige
Firecrawl-Responses werden nicht persistiert.

Exakte kanonische URL und exakter Content-Hash werden idempotent
dedupliziert. SimHash setzt ausschließlich `possible_duplicate`; verschiedene
Quellen werden damit nie automatisch zusammengeführt, ersetzt oder gelöscht.

### 2.4 External Evidence und Forschungspartner

Search-Snippets werden nie als Evidence verwendet. Ein External Anchor kann
nur aus einer exakt gefundenen Passage der aktuellen, importierten,
menschlich geprüften und sicher freigegebenen Source-Version entstehen. Dafür
werden die bestehenden `EvidenceAnchor`- und `EvidenceLink`-Modelle verwendet.

Webresultate für Partnerrecherche werden ausschließlich als
`research_partner_candidate` klassifiziert. Der getrennte Eligibility-Zustand
lautet `not_checked`, `reference_match`, `human_review_required`,
`verified_against_official_source` oder `stale`.

Ein Registry-/Domain-Treffer erreicht höchstens `reference_match`.
`verified_against_official_source` verlangt Human Review, aktuellen offiziellen
External Anchor, exakte Fundstelle, offizielle URL, aktuelle Source-Version,
`last_checked`, Actor und Zeitpunkt. Eine Bestätigung erzeugt weder einen
Projektpartner noch erfüllt sie automatisch das formale Partner-Gate. Es gibt
keine automatische Kontaktaufnahme.

### 2.5 Quellengebundener Marktvergleich

Die bestehende `MarketComparison`-Domäne bleibt der einzige Erzeugungs- und
Lesepfad. Zulässig sind nur aktuelle, explizit importierte Public Sources mit
Live-Research-Provenienz, positivem Content Review, bestandenem bzw. menschlich
freigegebenem Safety-Status und korrektem Projekt/Workspace.

Jede faktische Vergleichszelle erhält External-Evidence-Referenzen mit Source,
Version, Fragment, Span und Quote-Hash. Nicht belegte Preise oder Eigenschaften
werden als `nicht öffentlich belegt` ausgewiesen. Widersprüche bleiben sichtbar.
Der Vergleich speichert Research-Brief-/Task-/Approval-Provenienz,
Source-Versionen, Provider/Modell, Prompt-Version, Kontext-Hash, Status und
Stale-Grund. Editor und Prüfansicht lesen dieselbe Comparison-ID.

Die Quellenzahl ist fachlich umgesetzt:

- mindestens 3 geeignete Quellen: vollständiger Vergleich;
- 2 geeignete Quellen: `limited` plus `limited_external_evidence`;
- weniger als 2: `insufficient_external_evidence`, keine Matrix.

Auch Fake-Modus endet bei null echten Quellen mit dem maschinenlesbaren
`insufficient_external_evidence`; Fake-Inhalte erzeugen keine Marktbehauptung.
Der bisherige E2E-Gegen-Pin wurde fachlich auf diese Semantik aktualisiert.

Neue Version, Ablehnung oder Löschung einer verwendeten Source markiert
MarketComparison, External-Evidence-Links und bestätigte Partner-Eligibility
stale. RUN-3C-DraftSuggestions existieren noch nicht und werden deshalb erst
im dafür vorgesehenen Slice an diese Staleness-Kette angebunden.

## 3. Versionierter Handoff für RUN 3C

`GET /api/v1/projects/{project_id}/research-handoff` liefert einen projekt-
und workspacegebundenen, maschinenlesbaren Übergabestand mit:

- `project_id` und `workspace_id`;
- aktuellem Research Brief;
- Research-Run-/Task-IDs und Query-Approval-IDs;
- `current_source_version_ids`;
- External-Evidence-Anchor-IDs;
- aktueller `market_comparison_id`;
- Market-Status und `market_comparison_stale_reason`;
- pro Quelle Source-ID, aktuelle Source-Version, Content-Review- und
  Safety-Status sowie Stale-Zustand/-Grund.

Die explizite Passageauswahl erfolgt über
`POST /api/v1/research-results/{result_id}/external-anchors`. Sie prüft Quote,
Offsets, aktuelle Version, Content Review, Safety sowie Projekt-/Workspace-
und Task-Isolation. Search-Snippets sind kein Handoff-Feld und keine Evidence.

Damit kann RUN 3C gezielt ausgewählte und überprüfte External Anchors
versioniert konsumieren. Dieser Handoff bedeutet ausdrücklich nicht, dass
echte KI-Feldvorschläge fertiggestellt sind. RUN 3B enthält keine neuen
LLM-Vorschläge, kein `selected_anchor_ids`-Redrafting, keinen vollständigen
Diff-Editor und keine Änderung der Qualitätsübersicht.

## 4. API- und Vertragsänderungen

Additiv hinzugekommen bzw. erweitert wurden Query-Approval- und Research-Run-
Idempotenz, External-Anchor-Erstellung, Partner-Eligibility-Human-Review,
Research-Handoff, Quarantänefreigabe beim Content Review, Market-Provenienz,
Zell-Evidence, Warnungen, Stale-Grund und `market_comparison_item` als
Evidence-Link-Ziel. BFF-Routen und TypeScript-DTOs verwenden dieselben
bestehenden Backendpfade.

Pydantic-Verträge und das zur Laufzeit erzeugte FastAPI-OpenAPI wurden additiv
aktualisiert und durch einen Runtime-OpenAPI-Test abgesichert. Die eingefrorenen
v1.1-Dateien unter `final_backend_contracts_v1_1/` wurden nicht nachträglich
umdefiniert; die RUN-3B-Endpunkte sind additive beta-interne Pfade.

## 5. Migration und Rollback

Migration: `b2d4f6a8c013_run_3b_research_provenance.py`

Sie ergänzt ausschließlich RUN-3B-Provenienz für Source-Versionen und
Research Results, Review-/Quarantäne-/Duplicate-Metadaten,
Partner-Eligibility-Review, External-Anchor-Scope sowie Market-Provenienz und
Zell-Evidence. Bestehende Quellen erhalten einen deterministischen Backfill.

Geprüft wurden Fresh DB, Upgrade, Downgrade auf RUN-3A-Head, erneutes Upgrade
und Erhalt historischer Kernzeilen. Beim Downgrade werden ausschließlich neue
RUN-3B-External-Anchor/-Link-Zeilen ohne `run_id` entfernt, weil das RUN-3A-
Schema diese fachlich nicht darstellen kann. Historische Source Documents,
Source Versions und ältere run-gebundene Evidence bleiben erhalten. Der
Roundtrip-Test enthält diesen Fall ausdrücklich.

Rollback-Befehl:

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic -c alembic.ini downgrade a1c3e5f7b902
```

## 6. Abnahmematrix

| ID | Ergebnis | Nachweis |
|---|---|---|
| `UX-RES-01` | bestanden | Unicode, Leerzeichen, Satzzeichen, Paste, Mid-Edit und Reload in Backend-/Frontendtests |
| `UX-RES-02` | bestanden | vereinfachtes Rechercheformular ohne Pflicht-Ontologie |
| `RES-01` | vorbereitet, `not_run` | Live-Webpfad implementiert; echter Firecrawl-Smoke wartet auf Human Gate |
| `RES-02` | bestanden | nicht konfiguriert/unverfügbar liefert ehrlichen Fehler; kein Fake-Fallback |
| `RES-03` | bestanden | riskante Query blockiert bzw. reviewpflichtig; Approval nicht umgehbar |
| `MKT-01` | bestanden | geprüfte Public Sources erzeugen Matrix mit External Anchors; 2 Quellen ergeben `limited` |
| `MKT-02` | bestanden | Snippets, Fake, Cross-Project und ungeprüfte/quarantänisierte Sources ausgeschlossen |
| `SEC-01` | bestanden | Injection-Signal führt zu Quarantäne und expliziter Human-Freigabe |
| `SEC-02` | bestanden | Cross-Workspace/-Project/-Run und fremde Anchors fail-closed |
| `LIVE-01` | vorbereitet, `not_run` | keine echte URL und kein echter Provider-Call vor Freigabe |

Korrekte UX-Zuordnung:

- `UX-RES-01` = Leerzeichen, Unicode, Satzzeichen, Paste, Mid-Edit und Reload.
- `UX-RES-02` = vereinfachtes Rechercheformular ohne Pflicht-Ontologie.

## 7. Tatsächliche Offline-Testresultate

| Gate | Ergebnis | Gemessene Laufzeit/Details |
|---|---|---|
| Preflight `scripts/verify_all.ps1` | grün | ca. 681 s, vor Produktänderungen |
| RUN-3B-Fokustests | grün | 10 Fälle einschließlich parameterisierter Security-Varianten |
| Markt-/RUN-3B-Regression | grün | 29/29 |
| Migration Fresh/Up-Down-Up | grün | 4/4, zuletzt 22,3 s |
| vollständiges Pytest ohne separaten DOCX-Smoke | grün | 1.393 gesammelt, 4 opt-in Skips; ca. 275,7 s |
| DOCX-Render-Smoke | grün | 1/1; isoliert und im finalen Gesamtlauf |
| vollständiges Vitest | grün | Exit 0 |
| ESLint | grün | Exit 0 |
| TypeScript `--noEmit` | grün | Exit 0 |
| Production Build | grün | 32 Seiten; ca. 27,8 s |
| Playwright, 1 Worker | grün | 48/48; ca. 2,7 min |
| API-Smoke | grün | 19/19 |
| finales `scripts/verify_all.ps1` | grün | Exit 0; 618,9 s |
| `git diff --check` | grün | keine Whitespace-Fehler |
| Secret-/Artefaktscan | grün | keine echten Secret-Signaturen, keine getrackten DB-/Log-/Providerartefakte |

Der Word-COM-Test benötigte für den kombinierten Lauf Zugriff auf die aktive
Windows-Anmeldesitzung. Zwei sandboxgebundene Gesamtläufe scheiterten nur beim
COM-Start; der Test war isoliert zweimal grün und im finalen, weiterhin
vollständig offline ausgeführten Gesamtlauf ebenfalls grün.

## 8. Geänderte Dateien

```text
app/api/projects/[id]/research-handoff/route.ts
app/api/research-results/[id]/external-anchors/route.ts
app/api/research-results/[id]/partner-eligibility-review/route.ts
app/api/research-results/[id]/review/route.ts
backend/app/agents/schemas.py
backend/app/api/firewall.py
backend/app/api/research.py
backend/app/api/research_briefs.py
backend/app/api/sources.py
backend/app/contracts/evidence.py
backend/app/contracts/market.py
backend/app/contracts/research.py
backend/app/contracts/research_brief.py
backend/app/db/models.py
backend/app/market/executor.py
backend/app/market/service.py
backend/app/market/source_scope.py
backend/app/market/verify.py
backend/app/migrations/versions/b2d4f6a8c013_run_3b_research_provenance.py
backend/app/partner_research/eligibility.py
backend/app/repositories/evidence.py
backend/app/repositories/sources.py
backend/app/research/brief_service.py
backend/app/research/content_safety.py
backend/app/research/executor.py
backend/app/research/import_service.py
backend/app/research/providers/base.py
backend/app/research/providers/fake.py
backend/app/research/providers/firecrawl.py
backend/app/research/staleness.py
backend/app/research/url_safety.py
backend/tests/test_m10_migrations.py
backend/tests/test_market_comparison.py
backend/tests/test_partner_eligibility.py
backend/tests/test_research_briefs.py
backend/tests/test_run3b_research_market.py
components/quellen/market-comparison-section.tsx
components/quellen/public-research-panel.tsx
docs/RUN_3A_RESULT.md
docs/RUN_3B_RESULT.md
e2e/market-comparison.spec.ts
lib/firewall.ts
lib/market-comparison.ts
lib/research-brief.ts
test/firewall-panel.test.tsx
```

Kumulativer finaler Diff gegen den Ausgangscommit einschließlich
Ergebnisdokumenten: 45 Dateien, 2.370 Einfügungen, 143 Löschungen.

## 9. Offene Risiken und bewusste Grenzen

- Realer Firecrawl-Preflight, echte URL, expliziter Live-Import und LIVE-01
  wurden wegen des Human Gates nicht ausgeführt.
- Die technische Providerintegration ist offline vollständig getestet; ihre
  reale Erreichbarkeit, Kosten- und Quotenlage ist noch nicht akzeptiert.
- SimHash liefert bewusst nur einen Hinweis. Die menschliche
  Duplicate-Entscheidung bleibt offen.
- `verified_against_official_source` ist keine Förderzusage und kein formales
  Projektpartner-Gate.
- RUN 3B liefert noch keine echten feldbezogenen LLM-Vorschläge. Strukturierte
  Ausgabe, `selected_anchor_ids`, `missing_inputs`, Grounding, Suggestion-
  Versionierung und Accept als neue DraftVersion gehören ausschließlich in
  RUN 3C nach bestandenem Web-Smoke.
- Live darf weiterhin niemals auf Fake zurückfallen.

## 10. Haltepunkt

Offline-Implementierung und Dokumentation von RUN 3B sind abgeschlossen.
Es wurden keine echten externen Calls ausgeführt. Der nächste zulässige Schritt
ist ausschließlich der beaufsichtigte Web-Smoke nach der exakten Freigabe:

```text
RUN_LIVE_SMOKES_APPROVED
```

Ohne diese Freigabe wird weder ein Provider-Call noch RUN 3C gestartet.
