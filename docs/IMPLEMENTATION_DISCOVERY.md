# Implementation Discovery — Abschnitt B (Discovery und Baseline)

- **Datum:** 2026-07-19
- **Baseline-Commit:** `c910dd71962fe2a02b4e97e518098586afff48d0` (`main`, Working Tree clean)
- **Auftrag:** Abschnitt B des Finalisierungs-Mandats (Innosuisse-Innovationsprojekte mit Umsetzungspartner, Innolink-Format). Nur Discovery: Baseline-Läufe, rote Diagnose-Tests, dieser Bericht. Keine Produktivlogik geändert.
- **Verdikt-Legende:** `REAL` (Fehler existiert) · `BY-DESIGN` (Verhalten existiert, ist aber bewusstes, testgepinntes Design im Widerspruch zum Mandat) · `BEHOBEN` (in früheren Slices gefixt) · `TEILS` (teilweise vorhanden) · `UNCONFIRMED` (nicht reproduzierbar / nicht belegbar)

> Wichtigste Gesamterkenntnis: Der Auftragsprompt basiert auf einem älteren statischen Audit. Von den zehn gemeldeten Fehlern sind vier bereits behoben, zwei sind echte Lücken, zwei sind bewusstes gepinntes Design im Widerspruch zum Mandat, zwei sind nicht reproduzierbar. Die vom Mandat vorausgesetzten Dateien `CODE_AUDIT_REPORT.md` und `innolink_rule_catalog.seed.json` existieren nirgends im Repo oder Workspace.

---

## 1. Tech-Stack und Startbefehle

**Stack (verifiziert):**

- Frontend: Next.js 16.2.6 (Turbopack), React 19, TypeScript 5.7 (strict), Tailwind, shadcn/ui, Tiptap. Paketmanager pnpm 11.5.3 (via `corepack`; pnpm ist nicht global installiert).
- Backend: FastAPI 0.115.6, Python 3.13, SQLAlchemy 2.0.36 + Alembic 1.14.0 (36 Revisionen), SQLite, LangGraph 0.2.76, pypdf/PyMuPDF/python-docx. Kein Anthropic-/OpenAI-/Firecrawl-SDK — Provider-Adapter sind handgeschrieben über `httpx`.
- **Flask ist ein Falsch-Positiv des statischen Scans** — weder in `backend/requirements.txt` noch in `spike/` vorhanden.
- Tests: Vitest (jsdom, 70 Dateien), Pytest (~113 Dateien inkl. 3 neue DISCOVERY-RED), Playwright (28 Specs, chromium, `workers: 1` wegen SQLite-Single-Writer). Jest existiert nicht (Scan-Falsch-Positiv; nur Vitest).
- `spike/` (PII-Gateway-Prototyp) und `private_inputs/` (gitignoriert, reale PDF-Abnahme) sind keine Produktivpfade.

**Startbefehle (verifiziert ausgeführt):**

```powershell
# Backend (aus Reasearch-funding-app/backend, venv unter backend/.venv)
$env:DATABASE_URL="sqlite:///./var/<db>.db"; $env:APP_ENV="development"; $env:DEMO_DATA_ENABLED="true"
.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
.venv\Scripts\python.exe -m app.demo.seed --reset --evaluation   # deterministischer Demo-Datensatz (2 Projekte)
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend (aus Repo-Root; corepack liefert pnpm)
corepack pnpm build
$env:APP_BACKEND_MODE="live"; $env:FASTAPI_BRIDGE_URL="http://127.0.0.1:8000/api/v1"
node node_modules/next/dist/bin/next start --port 3000
```

Gate-Skript: `scripts/verify_all.ps1` — druckt bewusst **kein** «ALL GREEN», sondern 6 getrennte Abnahmekategorien; Live-Kategorien sind Opt-in und melden `not_run`. (Widerspruch zur Skill-Anweisung `.claude/skills/Slice-Abschlussprüfung.md`, die «ALL GREEN» verlangt — dokumentierter Wording-Konflikt, kein Code-Defekt.)

**Gemessene Baseline-Laufzeiten (2026-07-19, OneDrive-Verzeichnis):**

| Kommando | Resultat | Dauer |
|---|---|---|
| `corepack pnpm lint` | PASS | 12 s |
| `corepack pnpm exec tsc --noEmit` | PASS | 21 s |
| `corepack pnpm build` | PASS (32 Routen) | 36 s |
| `corepack pnpm test` (Vitest) | **PASS — 70 Dateien, 505/505 Tests** | 78 s |
| `python -m pytest -q` (Backend) | **4 FAILED** (siehe §6.2) | 454 s |
| `pnpm exec playwright test --workers=1` | _wird nach Suitelauf ergänzt_ | _läuft_ |

---

## 2. Architekturkarte UI → API → Service → Repository/DB → Provider

```text
Browser (Next.js Screens, app/*/page.tsx)
  │  Mock/Live-Weiche: lib/app-mode.ts (server-injiziertes APP_BACKend_MODE);
  │  Client ruft ausschliesslich same-origin /api/* (BFF)
  ▼
Next.js Route Handlers (app/api/**/route.ts)
  │  lib/bridge.ts: callBridge/forwardToBridge/proxyToBridge
  │  liest FASTAPI_BRIDGE_URL NUR serverseitig; fehlt sie → 502 bridge_unreachable
  ▼
FastAPI (backend/app/main.py, Präfix /api/v1, 24 Router in backend/app/api/*)
  │  Lifespan: DB-Check, fail-closed Registry-Load, Agent-Registry, Recovery
  ▼
Application Services
  │  runs/graph.py (LangGraph-Knoten: prepare_documents → detect_facts →
  │  formal_checks → web_research → draft_fields → quality_review)
  │  imports/service.py · research/{brief_service,service,executor}.py ·
  │  market/{service,executor}.py · fields/redraft_service.py ·
  │  review/{service,check_status,recheck}.py · reliability/* · exports/*
  ▼
Domain: rules/{engine,handlers,aggregation,inputs}.py (deterministisch, kein LLM)
  │  Registry-Loader backend/app/registry/loader.py ← YAML-Verträge
  │  final_backend_contracts_v1_1/{innosuisse_innovation_project_v1_1,requirements}.yaml
  ▼
Repositories (backend/app/repositories/*) → SQLAlchemy → SQLite (backend/app/db/models.py)
  ▼
Provider-Adapter (hinter Interfaces, fail-closed):
  · LLM: agents/gateway.py → providers/{openai,anthropic,fake}.py
    (Policy-Matrix config/provider_policy.py VOR Verfügbarkeit; CostGuard;
    live+fake gleichzeitig = harter Fehler `live_fake_conflict`)
  · Web: research/providers/resolver.py → {firecrawl,fake}.py
    (eigenes Flag WEB_RESEARCH_FAKE_PROVIDER; Chokepoint
    research/service.py::_firewall_query → security/search_query_firewall.py)
```

Detailliertere Architekturdokumente: `docs/fable-context/00–13` und `final_backend_contracts_v1_1/` (ADR-001 v4, API_Contract v1.1, Domain_Model v4) — dieser Bericht dupliziert sie bewusst nicht.

**Aufrufpfade der im Mandat genannten UI-Texte (Stichprobe, verifiziert):**

- «Antrag importieren»: `components/shell/sidebar.tsx` → `/import` → `components/import/import-review.tsx` → `lib/imports.ts` (`/api/projects/{id}/imports`, `/api/imports/{id}/decision`) → `backend/app/api/imports.py` → `imports/{mapping,service}.py` → `ImportCandidate`/`StructuredImportCandidate` (models.py:303/370).
- «Teilweise erfüllt»: `components/anforderungen/requirements-screen.tsx` bzw. `live-requirements.tsx` → `lib/requirements.ts:50` (Label für Status `partial`) ← `/api/runs/{id}/requirements` ← `RequirementAssessment.status` ← **`app/rules/aggregation.py:54-56`** (Hybrid-Pass→partial; Root Cause, siehe §5 #4).
- «Textstelle gefunden»: `lib/evidence-ladder.ts` (`location_found`, neutral-blau) ← `backend/app/review/evidence_status.py` (7-Stufen-Leiter, Coverage ≠ Correctness).
- «Demo-Recherche»: `components/quellen/public-research-panel.tsx:281` (Badge/Banner) ← `workspace.provider_mode` ← `backend/app/research/brief_service.py:416-422`; Import-Verbot: `backend/app/research/import_service.py:85`.
- «Demo-Vorschlag»: `lib/generation-kind.ts:8` («Demo-Vorschlag (kein echtes KI-Modell)») ← `DraftSuggestion.generation_kind == "fake_demo"` ← `backend/app/agents/generation.py` (Provenance vom tatsächlich dienenden Adapter).
- «Markt- und Konkurrenzvergleich»: EIN Artefakt (`MarketComparison`, models.py:1790) — Arbeitsfläche `components/quellen/market-comparison-section.tsx`, Editor read-only `components/editor/live-market-comparison.tsx` + `market-comparison-sheet.tsx`, gemeinsamer Client `lib/market-comparison.ts`. Keine Doppellogik.
- «Qualitätsübersicht»: `components/review/quality-summary.tsx` ← `/api/runs/{id}/reliability` ← `backend/app/reliability/*` (`RunQualitySummary`).
- «Technische Details»: collapsed `<details>`-Abschnitte gemäss CLAUDEX §2 (sanktioniertes Muster). Vorkommen im Standard-Flow: `components/run/run-technical-details.tsx:30`, `components/status/active-run-details.tsx:28`, `components/review/claim-details-drawer.tsx:109`, `components/editor/suggestion-review-dialog.tsx:448`, `components/import/import-review.tsx:1092,1494`, `components/quellen/public-research-panel.tsx:387`, `components/quellen/upload-error-notice.tsx:72`, `components/ki-team/role-drawer.tsx:223`. **Zielkonflikt:** Mandat D3 verlangt Entfernung aus dem Standard-Flow; CLAUDEX definiert genau dieses Muster als den erlaubten Ort für technische Details → Owner-Entscheid nötig (§8).

---

## 3. Datenmodelle (backend/app/db/models.py, 2056 Zeilen)

| Domäne | Modelle (Zeile) | Kernfelder/Status |
|---|---|---|
| Source | `SourceDocument` (209) → `SourceVersion` (238) → `SourceFragment` (280) | `type` pdf/docx/txt/url · `status` uploaded/processing/processed/needs_manual_input/failed · `data_classification` JSON (`origin`: public_source/real_project/synthetic/anonymized; `sensitivity`) |
| Import | `ImportCandidate` (303), `StructuredImportCandidate` (370) | `decision` pending/conflict/accepted/saved_as_source/ignored · `extracted_text` unveränderlich + separates `edited_text` · `confidence` found/uncertain |
| Rule/Requirement | `RuleResult` (741), `RequirementAssessment` (768), `OpenIssue` (796) | RuleResult.status passed/failed/needs_input/not_applicable · Assessment.status fulfilled/partial/open/needs_input/blocked · `basis` deterministic_rule/semantic_assessment/hybrid/human_override · `stale` |
| Evidence | `EvidenceCandidate` (839) → `EvidenceAnchor` (897) → `EvidenceLink` (949) | Anchor.`verification_status` unverified/exact_verified/human_verified/rejected · Link.status active/stale/removed · abgeleitete 7-Stufen-Supportleiter in `review/evidence_status.py` (nie persistiert) |
| Analysis | `AnalysisRun` (462) + Snapshots (`RunSourceSnapshot` 550, `RunPolicySnapshot` 571, `RunProjectSnapshot` 720, `RunPhase` 596) | RunStatus + separates `live_execution_status` · `recheck_required`, `semantic_findings_stale` · `content_hash` für Staleness · partieller Unique-Index «ein aktiver Run pro Projekt» |
| Research | `ResearchBrief` (1615), `ResearchTask` (1659), `ResearchResult` (1725), `SearchQueryApproval` (1888) | Task.`execution_mode` fake_demo/live (vom TATSÄCHLICH dienenden Provider gestempelt) · Result.status candidate/imported/rejected/failed + `support_status`/`coverage_status`/`content_review_status` · Approval single-use, Raw-Query nur gehasht |
| Draft | `PortalFieldDraft` (988), `DraftVersion` (1021), `DraftSuggestion` (1521) | Suggestion.`generation_kind` rule_template/fake_demo/model_generated · Accept erzeugt neue DraftVersion (nie destruktiv) |
| Reliability | `DraftClaim` (1939), `ClaimLineage` (1976), `RunQualitySummary` (2009) | `sufficiency_status` getrennt von Coverage · Summary.status current/stale/failed |
| Markt | `MarketComparison` (1790), `MarketComparisonItem` (1829) | nur aus importierten Public-Sources (`market/source_scope.py`) |

**Abweichungen von den Mandats-Annahmen (A1/A2):**

1. **Kein Quellenrollen-Enum** (`PRIMARY_APPLICATION`/`OFFICIAL_RULE`/…). Rollensemantik verteilt sich auf `SourceDocument.type` + `data_classification`-JSON + `ResearchResult`-Status. Offizielle Regeln sind KEINE Sources, sondern die versionierte YAML-Registry (reviewte Domänendaten — entspricht inhaltlich Mandat E.7).
2. **Keine `compliance_status`-Spalte.** `RequirementAssessment.status` kodiert Compliance UND offenes Human Review in einer Dimension (Hybrid-Mapping) — der Kern von Fehler #4.
3. `verification_status`, `run_status` und Evidenz-Supportstufen existieren getrennt und funktionieren; das Vokabular weicht vom Mandat ab (`supports_partially`/`supports_strongly`/`conflict_or_uncertain` statt `partially_supported`/`strongly_supported`/`contradicted`; `not_required`/`evidence_missing` statt `not_evaluated`/`no_evidence`).
4. **`innolink_rule_catalog.seed.json` existiert nicht** (auch kein anderes `*.seed.json`). Regelkatalog = `final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml` (12 official_core_rules mit source_type/official_url/evidence_quote) + `requirements.yaml`; Loader fail-closed (`backend/app/registry/loader.py`); Evaluationen speichern die Registry-Version.

---

## 4. Demo-/Fake-/Stub-Inventar (Datei · Funktion · Caller · erreichbares UI)

### 4.1 Backend-Fake-Pfade (ehrlich gelabelt, fail-closed)

| Pfad | Funktion | Aktivierung | UI-Sichtbarkeit |
|---|---|---|---|
| `backend/app/agents/providers/fake.py` | deterministischer LLM-Fake | `AGENT_FAKE_PROVIDER=true`; hart blockiert bei `AI_EVAL_MODE=real` (`gateway.py` → `live_fake_conflict`) | Badge «Demo» / «Demo-Vorschlag (kein echtes KI-Modell)» via `generation_kind=fake_demo` |
| `backend/app/research/providers/fake.py` | Fake-Webprovider | eigenes Flag `WEB_RESEARCH_FAKE_PROVIDER` (explizit NICHT von `AGENT_FAKE_PROVIDER` impliziert, `resolver.py:32`) | Banner «Demo-Recherche – keine echten Webquellen…» (`public-research-panel.tsx:284`); Import-Button ausgeblendet |
| `backend/app/research/import_service.py:85` | Import-Verbot für Demo-Resultate | immer | Fehlertext «…kann nicht übernommen werden» |
| `backend/app/market/executor.py:160` + `market/service.py:170` | kein Marktvergleich aus Demo-Recherche; `demo_comparison_not_acceptable` (409) | immer | Hinweis im Markt-Panel |
| `backend/app/market/source_scope.py:81-98` | Live-Marktvergleich nur aus `execution_mode=="live"` + importierten, geprüften Public-Sources | immer | — (Retrieval-Filter) |
| `backend/app/demo/{seed,dataset,evaluation,reset}.py` | deterministischer Demo-Datensatz (2 synthetische Projekte) | `DEMO_DATA_ENABLED=true` + CLI `python -m app.demo.seed` | Demo-Projekte im Dashboard |
| `backend/app/api/integrated_draft.py` | DEMO.1-Draft-Paket; 503 ohne Fake-Modus; `/real` ist read-only Whitelist ohne Provider-Call | Fake-Modus | `/antragsentwurf` (nur via `/admin`-Hub) |

**Kein stiller live→fake-Fallback gefunden.** «Fallback» bezeichnet im Code ausschliesslich Primär-/Fallback-Routen zwischen ECHTEN Modellen (`gateway.py:_execute_routes`). Provenance (`generation_kind`, `execution_mode`) stammt immer vom tatsächlich dienenden Adapter. Live-Fehler bleiben Fehler (typisierte Reason-Codes, `fields/reason_codes.py`; Tests `test_live_readiness.py`).

### 4.2 Frontend-Mock-Modus (getrennt vom Live-Pfad)

- Weiche: `lib/app-mode.ts` (`APP_BACKEND_MODE`, `LIVE_RESOURCES`). Im Live-Modus sind Mock-Zweige unerreichbar.
- Mock-Datenquellen: `lib/api.ts` (`isMock("legacy")`-Zweige, als DEMO-ONLY markiert) + 7 Dateien `lib/{mock-data,anforderungen-mock-data,quellen-mock-data,export-mock-data,draft-mock-data,review-mock-data,kosten-mock-data}.ts`; Importiert von den Screens (`app/*/page.tsx`) nur im Mock-Zweig.
- `app/export/page.tsx:140` «Demo: Seitenzustände testen» — Mock-only Szenario-Schalter.
- 501-Stubs (tote Routen, im Live-Pfad nie aufgerufen): `app/api/sections/[fieldId]/route.ts`, `app/api/suggestions/[id]/accept/route.ts` («Späterer Slice»).
- `app/api/demo/integrated-draft{,/real}/route.ts` proxen ans Backend (dort gegated) — **keine lokalen Demodaten im BFF**.

### 4.3 Sonstige Befunde

- `backend/.env` (lokal, nicht im Git) enthält eine **korrupte Zeile `m,n.p0`** sowie die Live-Slice-Konfiguration (Modell-IDs + Preistabelle + echte Keys). Beides beeinflusst die Test-Baseline (§6.2). `AZURE_OPENAI_DEPLOYMENT` enthält eine URL statt eines Deployment-Namens (Azure-Adapter existiert nicht — dokumentierte Zielarchitektur).
- `.claude/skills/Bug-Hunter.md` u. a. referenzieren `.claude/skills/_shared/project-invariants.md` — **Datei existiert nicht** (toter Verweis). Ebenso ist der Pfad der Portal-Field-Matrix im Wahrheits-Guard-Skill ein `<PFAD_SETZEN>`-Platzhalter.

---

## 5. Tatsächliche Ursachen der zehn gemeldeten Fehler

| # | Gemeldet | Verdikt | Tatsächliche Ursache / Beleg | Red-Test |
|---|---|---|---|---|
| 1 | Fehlendes Reset/Re-Edit beim Import | **BY-DESIGN-Lücke** | UI zeigt Entscheidungsaktionen nur bei `pending`/`conflict` (`components/import/import-review.tsx:1290`); Backend antwortet auf Re-Decide mit 409 `import_already_decided` — als Invariante gepinnt in `tests/test_import_api.py:207`. Mandat D1 fordert Umkehrbarkeit → Vertragsänderung mit Owner-Freigabe nötig | `test_discovery_red_import_reset.py` (2× XFAIL) |
| 2 | Falsche Projektdauerbehandlung | **REAL** | `duration_months` ist manueller Integer (`contracts/project.py:44`, `budget-form.tsx:277`); `start_date`/`end_date` existieren (models.py:102) als reine Passthrough-Felder. **Keine Kalendermonatslogik im gesamten Repo**; PDF-Import extrahiert die Dauer nur als Text. Divergenz Datum↔Dauer wird still akzeptiert | `test_discovery_red_project_duration.py` (2× XFAIL) |
| 3 | Supporting Docs beeinflussen formale Analyse | **UNCONFIRMED (Status) / TEILS (Anzeige)** | Statusrelevant NICHT reproduzierbar: Rule-Inputs stammen ausschliesslich aus dem strukturierten Projekt-/Partner-Snapshot (`rules/inputs.py`); A1-Fakten sind advisory. ABER: `evidence/discovery.py` generiert Evidenzkandidaten **rollenlos über alle Snapshot-Fragmente** — Passagen aus Begleitdokumenten können als «Belege» an Anforderungen erscheinen (Links «supplementary only», Status unberührt). Wahrer Kern der Meldung ist eine Anzeige-/Scoping-Frage, kein Statusfehler | — (Doku; Scoping-Entscheid §8) |
| 4 | 52 % / exakt 5 % «teilweise erfüllt» | **BY-DESIGN, verletzt Mandat A2** | Handler rechnen inklusiv korrekt (`rules/handlers.py:159,178`: 52 % → `in_range`, 5 % → `at_or_above_min`, beides `passed`). `rules/aggregation.py:54-56` mappt Pass + `assessment_basis: hybrid` (beide Budget-Requirements, `requirements.yaml:110-150`) auf `partial` → UI «Teilweise erfüllt». Gepinnt in `tests/test_registry_rules.py:135`. **Zusatzbefund:** Budget-Precheck (`api/projects.py:225-233`) zeigt für dieselben Werte «fulfilled» (eigenes Vokabular) — die Inkonsistenz Precheck↔Anforderungsscreen ist die konkrete Nutzerverwirrung | `test_discovery_red_compliance_status.py` (2× XFAIL) |
| 5 | Irrelevante Evidenzzuordnungen | **TEILS** | Typisierte Hard-Rejections existieren: A1-Mapping (`agents/evidence_mapping.py:_candidate_reason` — 8 Ablehnungsgründe inkl. quote_not_in_fragment, fragment_out_of_snapshot) und deterministische Verifikation (`tests/test_evidence_verification.py`: Fremd-Source rejected, Fuzzy nie exact_verified). **Lücke:** kein struktureller Numerik-/Einheiten-Check für numerische Claims (Mandat I3) — thematische Wortähnlichkeit reicht für einen lexikalischen Kandidaten (`evidence/discovery.py`, Token-Overlap); Absicherung erst nachgelagert über Suffizienz (`reliability/sufficiency.py`) | — (Doku) |
| 6 | Fehlende Supportstufen | **BEHOBEN** | 7-Stufen-Leiter `review/evidence_status.py:25-33` (deterministisch, fail-closed `most_cautious`), gerendert via `components/status/support-status-badge.tsx` in `live-evidence.tsx`/`evidence-drawer.tsx`; `location_found` ist neutral, grün NUR bei `supports_strongly`. Vokabular ≠ Mandat (Mapping in §3) | vorhandene Tests (`test_evidence_support_status.py`, `test/support-status-badge.test.tsx`, `e2e/review-truth.spec.ts`) |
| 7 | Demo-Webresearch statt echter Recherche | **BEHOBEN** (seit a2c9b1c/3183bcc) | Live-Pfad = Firecrawl (`research/providers/firecrawl.py`); Fake nur über eigenes Flag; `execution_mode` vom tatsächlichen Provider gestempelt (`executor.py:303`); Demo-Resultate nie importierbar (§4.1); Brief-Gate + Query-Firewall + Single-Use-Approvals davor | `test_live_readiness.py`, `test_privacy_firewall.py`, `e2e/public-web-research.spec.ts` |
| 8 | Demo-KI-Vorschläge | **BEHOBEN** | Live-Provider hinter Gateway; `generation_kind` ehrlich; `live_fake_conflict` fail-closed; fehlende Konfiguration → typisierter Reason-Code, nie Fake-Ersatz (`test_configured_but_unavailable_live_route_never_falls_back_to_fake`) | `test_live_readiness.py`, `test/live-editor-a2.test.tsx` |
| 9 | Alte Review-Prosa als Feldtext | **UNCONFIRMED** | Kein Pfad gefunden: Override-Kommentare liegen auf dem Issue (`issue.overrideComment`), Partner-`review_comment` ist ein Partner-Feld; Feldtexte entstehen nur als `DraftVersion` (Accept-only). Zusätzlich existiert die deterministische Wächter-Metrik `no_review_notes_as_prose` (`evaluation/model_quality.py`, Test `test_model_quality_metrics.py:78`) | — |
| 10 | Verwirrende Qualitätszahlen | **TEILS** | Gruppierung/Fix-Queue/Top-5 existieren (`fix-queue.ts`, 6 Schweregradklassen); Not-run wird ehrlich als «Noch keine Zuverlässigkeitsprüfung ausgeführt» bzw. «Nicht geprüft» gezeigt (nie «0 gestützt»; `check_status.py` fail-closed, `canonical-status.tsx`). **Verbleibend:** Fachjargon «Beleg-Suffizienzprüfung», «Falsches Konsensrisiko», «Semantische Drift» prominent im Standard-Flow (`quality-summary.tsx:141-145`) — Mandat K will diese Begriffe nur in Audit-/Developer-Ansicht | — (Owner-Entscheid, Copy-Katalog; §8) |

**Zusätzlich (nicht in der 10er-Liste): 4 rote Backend-Tests auf sauberem `main`** — Details §6.2; Ursachenklassen: 1× umgebungsabhängige Testannahme (Preistabelle), 3× mutmassliche Regressionen der letzten zwei Commits (`149ef5e`, `c910dd7`).

---

## 6. Vorhandene und fehlende Tests

### 6.1 Bestand

- **Backend:** ~110 Pytest-Module (`backend/tests/`), conftest mit eigener Temp-DB und automatischem Nullen der Provider-Keys (`_no_real_provider_keys`); Real-Smokes nur via `RUN_REAL_PROVIDER_SMOKE=true`.
- **Frontend:** 70 Vitest-Dateien (505 Tests, alle grün).
- **E2E:** 28 Playwright-Specs, seriell; Orchestrierung siehe `scripts/verify_all.ps1:89-156`.
- Gut abgedeckt (verifizierte Beispiele): 40–60-%-/5-%-Grenzen inkl. exakter Schwellen (`test_project_budget.py`), Query-Firewall/Leakage (`test_privacy_firewall.py`, `test_m10_smoke.py`), Evidence-Hard-Rejection (`test_evidence_verification.py`), Live-`not_configured` (`test_live_readiness.py`), Stale-Runs (`test_reliability_pass.py`, `e2e/reliability-stale.spec.ts`), Human-Review≠Compliance-Zählung (`test_z_check_status_view.py`, `e2e/status-parity.spec.ts`), Quellen-Scope im A2-Kontext (`test_a2_research_context.py`).

### 6.2 Baseline-Fehlschläge (pytest, sauberer Tree @ c910dd7)

| Test | Symptom | Ursache (verifiziert/Hypothese) |
|---|---|---|
| `test_integrated_draft_real.py::test_run_real_all_a2_fields_metered` | `cost_status == 'priced'` statt erwartet `'unknown_price'` | **Umgebungsabhängig (verifiziert):** lokale `backend/.env` enthält seit dem Live-Slice (16.07.) `AGENT_MODEL_PRICING_CHF_PER_MILLION` mit realen Preisen; die conftest nullt nur Provider-KEYS, nicht Preistabelle/Modell-IDs → Suite ist gegenüber diesen Settings nicht hermetisch |
| `test_market_comparison.py::test_capability_reflects_market_comparison` | `features.market_comparison == False` | **Test-vs-Code-Drift (verifiziert):** `api/capabilities.py:22-25` verlangt seit dem Live-Preflight-Feature (`c65e6c4`/`149ef5e`) bei nicht-fake Web-Research einen erfolgreichen persistierten Firecrawl-Preflight; die Fixture `web_enabled` setzt nur einen Key und seedet keinen Preflight-Eintrag |
| `test_market_research_api.py::test_run_d0_persists_and_returns_candidates` | 12 statt 9 Resultate | **Hypothese (hoch plausibel):** Planner liefert seit `8964dfd` («Markt, Wettbewerb, State of the Art und Partner») 4 statt 3 Briefmodule (Log zeigt 4 Query-Freigaben); Assertion pinnt 3×3=9 |
| `test_integrated_draft.py::test_research_context_used_and_never_evidence` | `research_summary["market"]["used"] is False` | **Hypothese:** `c910dd7` (Live-Run-Funktionalität) verschärfte das Research-Kontext-Gating; der geseedete Fake-Kontext qualifiziert nicht mehr als «used». Genaue RCA in Phase 1 |

### 6.3 E2E-Baseline (Playwright, volle Suite, workers=1, frische Demo-DB)

**Resultat 2026-07-19: 44 passed, 4 failed — 616 s (10.2 min).**

| Fehlgeschlagener Spec | Testtitel | Dauer |
|---|---|---|
| `e2e/golden-path.spec.ts:62` | Technischer E2E (Fake-Provider): Idee + PDF bis Innolink-Kopieransicht, Zustand übersteht Reload | 5.0 min (Timeout-Nähe) |
| `e2e/market-comparison.spec.ts:85` | market comparison UI: Quellen section shows the honest empty state | 1.0 min |
| `e2e/market-research-flow.spec.ts:139` | Query-Freigabe, Recherche im Lauf, Verwerfen/Übernahme, Zusammenfassung | 22.6 s |
| `e2e/run-agents.spec.ts:25` | Analyse starten erzeugt echte Feldvorschläge und Critic-Findings | 27.3 s |

Ursachenanalyse und Fixes: RUN 2A Slice 0 (`docs/RUN_2A_RESULT.md`).

### 6.4 Fehlende Tests / neu angelegt (DISCOVERY-RED)

Konvention: `@pytest.mark.xfail(strict=True)` in **neuen Dateien**, bestehende Tests unangetastet. Strict = Ratsche: Ein späterer Fix macht den Test XPASS (Gate rot), bis er bewusst promoted wird. Die in den Tests skizzierten Vertragsformen (`POST /imports/{id}/reset`, `duration_conflict`) sind genehmigungspflichtige Platzhalter.

| Neue Datei | Tests | dokumentiert |
|---|---|---|
| `backend/tests/test_discovery_red_import_reset.py` | Reset-auf-pending; Re-Decide | Fehler #1 (Gegen-Pin: `test_import_api.py::test_already_decided_cannot_be_redecided`) |
| `backend/tests/test_discovery_red_project_duration.py` | Kalendermonats-Ableitung (18); Divergenz-Konflikt | Fehler #2 |
| `backend/tests/test_discovery_red_compliance_status.py` | 52 %-Band-Pass; exakt-5 %-Pass nicht herabgestuft | Fehler #4 (Gegen-Pin: `test_registry_rules.py::test_aggregate_hybrid_pass_is_partial`) |

Weiterhin ungetestet (bewusst nicht in diesem Lauf): Numerik-/Einheiten-Rejection für numerische Claims (#5), Jargon-Sichtbarkeit (#10, Owner-Copy-Entscheid), UI-Sichtbarkeit rollenfremder Evidenzlinks (#3).

---

## 7. Migrations- und Rückwärtskompatibilitätsbedarf (für Phase 1)

| Vorhaben | Migration | Kompatibilität / Rollback |
|---|---|---|
| #4 Statusdimensionstrennung | Additive Spalte (z. B. `compliance_status`) auf `requirement_assessments` ODER reine Aggregations-/Contract-Änderung ohne Schema | `RequirementAssessment.status`-Enum NICHT destruktiv ändern; Frontend-Buckets (`lib/requirements-view.ts`), Export-Snapshot (`exports/snapshot.py:96` mappt passed→«Erfüllt») und `ReviewStatusView`-Zählungen müssen konsistent nachziehen; Pin-Test-Update nur mit Freigabe; Rollback = Spalte ignorieren (additiv) |
| #2 Dauer-Ableitung | Keine Schemaänderung nötig (`start_date`/`end_date`/`duration_months` existieren); ggf. additives Konfliktfeld | Backfill-/Konfliktpolicy für Bestandsprojekte mit manueller Dauer definieren; Konsumenten: `rules/inputs.py:129`, `runs/project_snapshot.py:95`, `exports/snapshot.py:249`, `imports/mapping.py:702`, `budget-form.tsx`; Unicode-/Randtage-Semantik einheitlich Backend+Frontend |
| #1 Import-Reset | Kein Schemabedarf für Re-Open (Decision-Felder existieren); Audit-Trail über bestehendes `AuditEvent` | Neuer Endpoint = API-Vertragsänderung (CLAUDEX-Freigabe); Konsum-Semantik klären: bereits in einen Run übernommene Werte (`accepted_draft_version_id`) beim Reset NICHT rückwirkend löschen, sondern stale/Konflikt markieren; Pin-Test-Update mit Freigabe |
| #10 Copy-Verlagerung | keine | `test/quality-summary.test.tsx` pinnt heutige Texte → Anpassung mit freigegebenem Copy-Katalog (`docs/repair/message-catalog.md`) |
| Baseline-Fixes §6.2 | keine | Fixture-Härtung (Preistabelle/Modell-IDs in conftest nullen; Preflight seeden) bzw. Assertions an 4 Briefmodule anpassen — je nach RCA-Bestätigung |

Alle 36 Alembic-Revisionen haben Downgrade-Pfade; neue Migrationen müssen dem Muster folgen (`render_as_batch=True` für SQLite).

---

## 8. Priorisierte Datei-/Commit-Liste für Phase 1

Reihenfolge nach Risiko/Nutzen; jede Zeile = ein reviewbarer Commit. **Vorab nötig: Owner-Entscheide** zu (a) Re-Decide/Reset-Vertrag (#1), (b) Statusdimensionstrennung inkl. Pin-Test-Update (#4), (c) «Technische Details»-Zielkonflikt Mandat D3 vs. CLAUDEX, (d) Jargon-Copy (#10), (e) Evidenz-Discovery-Scoping (#3: Rollenfilter oder sichtbare Kennzeichnung).

1. `fix: baseline pytest failures (env-hermetic fixtures, live-slice drift)` — `backend/tests/conftest.py` (Pricing/Modell-IDs nullen), `test_market_comparison.py`-Fixture (Preflight seeden) ODER `capabilities.py`-RCA, `test_market_research_api.py`-Assertion, `test_integrated_draft.py`-RCA. Ziel: Gate-Basis grün.
2. `refactor: split machine compliance from human confirmation in requirement aggregation` (#4) — `backend/app/rules/aggregation.py`, ggf. `contracts/requirement.py` + additive Migration, `requirements.yaml` unverändert; Frontend `lib/requirements-view.ts`/`requirements-screen`; Promotion der DISCOVERY-RED-#4-Tests + freigegebenes Update von `test_registry_rules.py:135`; Precheck↔Anforderung konsistent.
3. `feat: derive project duration from start/end dates with conflict surfacing` (#2) — `backend/app/repositories/projects.py` oder neuer Domain-Helper, `contracts/project.py`, `components/partner/budget-form.tsx`, `components/import/import-review.tsx`; Promotion DISCOVERY-RED #2; Kalendermonats-Randfälle als Unit-Tests (N1).
4. `feat: reversible import decisions with audit trail` (#1) — `backend/app/imports/service.py`, `api/imports.py`, `lib/imports.ts`, `components/import/import-review.tsx`; Promotion DISCOVERY-RED #1 + freigegebenes Update des Gegen-Pins.
5. `refactor: quality overview copy relocation` (#10) — `components/review/quality-summary.tsx` (+ Test-Update mit Copy-Freigabe); Jargon in `claim-details-drawer` («Technische Details») belassen.
6. `fix: typed numeric evidence rejection` (#5-Restlücke) — Numerik-/Einheiten-Vorprüfung vor Kandidatenerzeugung bzw. Suffizienz (`evidence/discovery.py` oder `reliability/sufficiency.py`), plus Tests.
7. (nach Entscheid e) `refactor: evidence discovery source scoping` (#3) — Rollen-/Klassifikationsfilter oder UI-Kennzeichnung in `evidence/discovery.py` / `live-evidence.tsx`.

**Nicht empfohlen** (Mandat wörtlich vs. Ist-Architektur): Einführung des Quellenrollen-Enums als Big-Bang-Migration und JSON-Seed-Katalog parallel zur YAML-Registry — die bestehende Registry erfüllt E.7 bereits versioniert und reviewt; ein zweiter Regelpfad wäre Dead-Code-Duplikation (Mandat P verbietet genau das).
