# EVAL.0 — Inventar & Designentscheid: LLM-, Firecrawl- und Cost-Evaluation

- **Datum:** 2026-07-08
- **Ticket:** EVAL.0 (read-only Inventar + Designreport; keine Codeänderung)
- **Methode:** Read-only-Untersuchung von `backend/app/agents/`, `backend/app/research/`, `backend/app/market/`, `backend/app/config/`, `backend/app/db/models.py`, `backend/app/security/` (nur gelesen), `backend/app/evaluation/`, `scripts/`, `backend/tests/`. Alle Pfade relativ zum Repo-Root.
- **Status:** Entwurf zur Owner-Freigabe. Offene Owner-Entscheidungen: siehe §6.3 (D1–D11).

---

## 1. Ist-Inventar

### 1.1 Provider-Bestand

| Frage | Antwort | Ort |
|---|---|---|
| OpenAIProvider? | **Ja** — dormant, lazy `httpx`-POST auf `api.openai.com/v1/chat/completions`; `available()` = Key gesetzt | `backend/app/agents/providers/openai.py:21` (`name="openai_direct"`) |
| AnthropicProvider? | **Ja** — dormant, lazy `httpx`-POST auf `api.anthropic.com/v1/messages`; `available()` = Key gesetzt | `backend/app/agents/providers/anthropic.py:23` (`name="anthropic_direct"`) |
| AzureOpenAIProvider? | **Nein** — es existiert kein Adapter. Azure ist nur als `ProviderKind.AZURE` vorgesehen und in der ProviderPolicy **immer blockiert**, bis ein separater Slice Adapter + institutionelle Freigabe bringt. `.env.example` dokumentiert `AZURE_OPENAI_*`-Variablen, aber `Settings` hat **keine** Felder dafür; einziger Nutzer ist der Out-of-App-Check `scripts/azure-smoke-test.mjs` | `backend/app/config/provider_policy.py:14-16,34,44` |
| FirecrawlProvider? | **Ja** — realer Web-Research-Provider (nicht LLM-Gateway), env-gated über `firecrawl_api_key`; `search()` → POST `/search`, `fetch()` → POST `/scrape` auf `api.firecrawl.dev/v1`; Key nur im Bearer-Header, nie geloggt | `backend/app/research/providers/firecrawl.py:29` |
| Fake-Provider (LLM)? | **Ja** — deterministisch, ohne Netz/Key; Modi `success/malformed/malformed_json/timeout/error`; trägt alle Pflichttests | `backend/app/agents/providers/fake.py:30` (`name="fake"`) |
| Fake-Provider (Web)? | **Ja** — `FakeWebProvider`, deterministisch, eigener DNS-Fake-Resolver | `backend/app/research/providers/fake.py:45` |

Zwei getrennte Provider-Schichten mit je eigenem Protokoll:

- **LLM:** `ProviderAdapter`-Protocol (`backend/app/agents/providers/base.py:43-49`): `name`, `available()`, `generate(ProviderRequest) -> ProviderResult`; `ProviderResult` = `raw_output` + `ProviderUsage(input_tokens, output_tokens)`. Typisierte Fehler `ProviderError/ProviderTimeout/ProviderUnavailable`.
- **Web:** `WebResearchProvider`-Protocol (`backend/app/research/providers/base.py:61-72`): `name`, `available()`, `search()`, `fetch()`; zusätzlich `CreditExceeded`.

### 1.2 Gateway und Fake-Anbindung

`backend/app/agents/gateway.py` ist die **einzige** Grenze Agent→LLM (funktionsbasiert): `invoke(db, request, *, provider_resolver=None, registry=None) -> ModelResponse | SafeFailure` (Z. 214–278). Gate-Reihenfolge pro Call:

1. `data_policy.evaluate` (Z. 255–262) — deny-by-default, NDA/Sensitivität/Processing-Mode,
2. `cost_guard.pre_check` (Z. 265–271) — Call-/Retry-/Timeout-Limits pro Run,
3. `provider_policy.decide_for_adapter` (Z. 291–295) — **vor** `adapter.available()`: ein gesetzter API-Key kann eine blockierte Datenklasse nie öffnen,
4. Source-Trust / Prompt-Injection (Z. 274–275),
5. Schema-Validierung des Outputs.

Provider-Auswahl: kein Klassen-Registry, sondern ein injizierbarer Resolver. `default_provider_resolver` (Z. 105–115) mappt `"anthropic_direct"→AnthropicProvider`, `"openai_direct"→OpenAIProvider`, sonst `None`. Die Route (Provider+Model) kommt aus der `AgentRegistry` (`backend/app/agents/registry.py`, YAML `agents_v1_1.yaml`, fail-closed validiert).

**Fake-Anbindung:**
- Tests: Dependency Injection über `tests/agent_helpers.py` (`fake_resolver`, `per_route_resolver`).
- Runtime: Flag `agent_fake_provider` (`backend/app/config/settings.py:108`, Default `False`) — jeder Orchestrator (z. B. `field_drafting.py:41-60`, `critic_review.py:88-114`) tauscht dann den Resolver.
- Web-Fake separat: `web_research_fake_provider` (`settings.py:121`) über `research/providers/resolver.get_web_provider` — bewusst **nicht** durch `agent_fake_provider` impliziert.

### 1.3 UsageRecords — wo geschrieben

`UsageRecord` (`backend/app/db/models.py:512`): `input_tokens`, `output_tokens`, `cost_chf` (Default **0.0 = expliziter Platzhalter**, nie berechnet), `provider`, `model`, `run_id` (nullable), `research_task_id`. Schreibstellen:

| Stelle | Kontext |
|---|---|
| `backend/app/agents/cost_guard.py:75-97` (`record_usage`) | pro erfolgreichem Gateway-Call; aufgerufen aus `gateway.py:336-342`, `AgentInvocation.usage_record_id` wird verknüpft |
| `backend/app/runs/service.py:170` | Seed-Record bei Run-Erstellung |

Latenz: `AgentInvocation.latency_ms` (`gateway.py:172-176`). Web-Latenz existiert ebenfalls bereits: `ToolInvocation.duration_ms` + `started_at`/`finished_at` (`models.py:1102-1108`).

### 1.4 Tool Calls — wo geloggt

`ToolInvocation` (`backend/app/db/models.py:1080`) wird geschrieben von `research/executor.py`, `research/import_service.py` (via `research/recording.py` — nur Hashes/Metadaten, nie Rohpayloads), `market/executor.py`, `exports/tool.py`. `ControlResult` (`models.py:346`) verlinkt `tool_invocation_id`, `agent_invocation_id`, `research_task_id`.

### 1.5 CostGuard — wo er greift

„CostGuard" ist kein Modell, sondern drei Logik-Module mit klaren Hook-Punkten:

| Modul | Greift bei | Hooks |
|---|---|---|
| `backend/app/agents/cost_guard.py` | jedem LLM-Call | `pre_check` (Budget-Gate vor Call), `output_within_limit` (Token-Cap nach Call), `record_usage` (Persistenz) — alle als `CTRL.COST_GUARD` auditiert |
| `backend/app/research/cost_guard.py` | jedem Web-Tool-Call | `pre_check_tool` zählt `ToolInvocation` pro `research_task_id` gegen `web_research_max_credits` (Default 50) |
| `backend/app/market/cost_guard.py` | Market-Generierung | max. 1 erfolgreiche Generierung pro Comparison, max. 20 Items |

Ein `CostProfile`-Modell und eine Preistabelle existieren **nicht**; CHF-Kosten werden nirgends erfunden (`RunQualitySummary.cost_placeholder`, `evaluation/summary.py:95-99`). Vorhandene, ungenutzte Kosten-Felder: `AnalysisRun.estimated_cost_chf/actual_cost_chf`, `RunPolicySnapshot.max_cost_chf`.

### 1.6 Security-Schicht (nur gelesen, Do-not-touch)

- `backend/app/security/data_class.py`: `DataClass` D0–D3/UNKNOWN, deny-by-default-Ableitung aus der per-Objekt-`DataClassification`.
- `backend/app/security/policy_matrix.py`: eine fail-closed (DataClass × Tool)-Matrix. Firecrawl-Spalte: D0→`ALLOW`, D1/D2→`REQUIRE_SANITIZED_APPROVAL`, D3/UNKNOWN→`BLOCKED`. Logs: überall `METADATA_ONLY`.
- `backend/app/config/provider_policy.py`: (ProviderKind × DataClass)-Matrix. Direkte Consumer-APIs für **echte** D1/D2 blockiert, unabhängig von Keys (DP-04); Eval-Ausnahme **nur** bei `origin ∈ {synthetic, anonymized}` **und** `AI_EVAL_MODE=real` (Z. 98–112); Azure immer blockiert; D3/UNKNOWN für alle blockiert, auch Fake.
- Search Query Firewall (`security/search_query_firewall.py`) + Approval Flow (`security/approval_service.py`, Modell `SearchQueryApproval`, `models.py:1581`): Preview → Risk-Score → `allow`/`require_human_approval`/`block`; D1/D2 nie ohne Approval; Approvals single-use; Rohquery nur als Hash. Chokepoint: `research/service.py:_firewall_query` (Z. 61–135) — Agents können die Firewall nicht umgehen.
- `security/redaction.py` + `RedactingFilter` (`config/logging.py:23`): keine Rohqueries/Secrets in Logs/Audit/Control-Details.

### 1.7 Research / Market / Partner (Ist)

- **Research-Kette (M9I-A/M9J):** `research/service.py` (Firewall-Chokepoint) → `research/executor.py` (Web-Data-Policy → Research-CostGuard → `provider.search()` → SSRF-Gate `url_safety.py` → persistiert `ResearchResult`) → `research/import_service.py` (`fetch()` → `SourceDocument` type=url + `SourceVersion` → bestehende Ingestion → `SourceFragment`s → advisory A1-Synthese).
- **Market (M9I-B):** vergleicht **nur bereits importierte öffentliche Quellen** — kein Live-Web, kein Firewall-Call. Deterministischer Prefilter `market/source_scope.py` (`MARKET_SIGNAL_TERMS`, `FragmentCandidate`, `source_scope_hash`), Strukturierung über Beta-Agent `MC.market_comparison` (`allowed_tools=()`, kein Netz), deterministische Exact-Quote-Verifikation `market/verify.py` (verlinkt nur bestehende EvidenceAnchors, erzeugt nie neue).
- **Partner:** kein eigenes Research-Modul. Bausteine: `Partner`-Modell (`models.py:539`) + CRUD (`api/partners.py`), `ResearchTask.purpose="partner_role_suggestion"` + `requested_partner_roles` (`models.py:1417`), `ResearchResult.partner_role_suggestions` (`models.py:1476`), advisory A1-Synthese `agents/public_competence_research.py` („never selects partners"). Die Firewall-Lexikon-Logik entfernt Partnernamen aus Queries.
- **Datenmodelle:** `SourceDocument` (`models.py:200`), `SourceFragment` (270), `EvidenceAnchor` (762) existieren. **`ResearchCandidate` existiert nicht** — nächstes Analogon ist `ResearchResult` (`models.py:1447`, Status `candidate|imported|rejected|failed`, `identity_match_status`, `source_document_id`).

### 1.8 Evaluation, Scripts, Tests (Ist)

- `backend/app/evaluation/`: `harness.py` (R0-Smoke-Skelett, `provider_mode="fake/local"`, `external_provider_calls=0`, Metriken inkl. `latency_seconds`/`cost` = `None`-Platzhalter), `summary.py` (`EvaluationRunSummary` mit `fake_provider_used`/`web_research_used`/`market_comparison_used`, Kosten = Platzhalter), `__main__.py` (CLI → `var/evaluation`).
- `scripts/`: `baseline_f1.py` (R0.3-Baseline am synthetischen Goldfall F1/QUALIMON, Fake-Provider), `check_testdata_markers.py` (R0.4 CI-Gate gegen sensible Marker in Fixtures), `azure-smoke-test.mjs` (Out-of-App-Konnektivitätscheck), `smoke_api.py`, `verify_all.ps1/.sh`.
- Tests (`backend/tests/`): Fake ist Default; Real-Provider-Smokes existieren bereits, aber env-gated (`RUN_REAL_PROVIDER_SMOKE=true`-Skips in `test_agent_real_provider_smoke.py:17-19`, `test_a1_real_provider_smoke.py`, `test_a1_mapping_real_provider_smoke.py`) — **nie in CI**. Abdeckung: `test_agent_gateway.py`, `test_provider_policy.py`, `test_privacy_firewall.py` (inkl. Provider-Boundary-Test: nur Research-Module importieren `get_web_provider`), `test_market_comparison.py`, `test_import_no_raw_logging.py` u. a.
- Migrationen: einzelner Head `backend/app/migrations/versions/a3f8c2d91e47_import_candidates.py`.

### 1.9 Festgestellte Lücken (Zusammenfassung)

1. Kein `data_mode`-Konzept (nur `ai_eval_mode` + `DataClassification.origin` + Fake-Flags).
2. Keine Kostensemantik: `cost_chf=0.0` ist nicht unterscheidbar von „wirklich kostenlos"; keine Preistabelle; kein `cost_status`.
3. Kein Azure-Adapter, keine `AZURE_OPENAI_*`-Settings-Felder.
4. Kein Live-Web-Vorschritt für Market (nur bereits importierte Quellen); Partner-Research nicht konsolidiert.
5. Kein `ResearchCandidate`-Modell (aber `ResearchResult` deckt die Semantik ab).

---

## 2. Design: data_mode

**Empfehlung: dünnes, ableitendes Validierungs-Enum — kein neuer Enforcement-Pfad, keine neue DB-Spalte, keine Migration.**

`DataMode ∈ {fake_test, synthetic_eval, anonymized_eval, real_project}` wird aus bestehenden Mechanismen **abgeleitet** und validiert nur deren Konsistenz (fail-fast). Enforcement bleibt ausschliesslich bei `data_policy` × `provider_policy` × `policy_matrix` — der Validator kann nur früher abbrechen, nie mehr erlauben.

**Begründung:** Die geforderte Semantik existiert bereits wörtlich in `provider_policy.py:98-112`: direkte Provider für D1/D2 nur bei `origin ∈ {synthetic, anonymized}` + `AI_EVAL_MODE=real` (`provider_allowed_eval`); echte D1/D2 → blockiert unabhängig von Keys; D3/UNKNOWN → immer blockiert. Ein zweiter, paralleler Enforcement-Pfad würde eine Do-not-touch-Schicht duplizieren und Drift riskieren; die dokumentierte UND-Komposition („kann bestehende Gates nie lockern", `provider_policy.py:20-21`) bleibt am einfachsten erhalten, wenn gar kein Peer-Gate entsteht.

**Ableitungstabelle:**

| data_mode | `ai_eval_mode` | `origin` | Fake-Flags | Direct OpenAI/Anthropic | Azure | Firecrawl |
|---|---|---|---|---|---|---|
| `fake_test` | `off` | beliebig (nicht D3/UNKNOWN) | `agent_fake_provider` + `web_research_fake_provider` = true | nie | blockiert | nur Fake |
| `synthetic_eval` | `real` | `synthetic` | aus | erlaubt (D0–D2 via `provider_allowed_eval`) | blockiert (kein Adapter) | erlaubt; Queries werden trotzdem als **D0/public-source** behandelt, laufen durch Firewall + Logging |
| `anonymized_eval` | `real` | `anonymized` | aus | erlaubt (gleiche Regel) | blockiert | wie `synthetic_eval` |
| `real_project` | `off`/`real` | `real_project` | aus | nur D0 (DP-04) | blockiert | D0; D1/D2 nur sanitized + approved + `d2_web_research_enabled` |

D3/UNKNOWN: in **jedem** Modus blockiert (unverändert).

**Verortung (spätere Tickets, hier nur Design):** neues Modul `backend/app/evaluation/data_mode.py` mit `derive_data_mode(settings, classification) -> DataMode` und `validate_data_mode(settings, declared_mode)` (pure functions); Aufruf aus `backend/app/evaluation/__main__.py` vor jeder Invocation; Protokollierung als Feld `data_mode` im `EvaluationRunSummary` (`evaluation/summary.py`). Keine neue Spalte auf `AnalysisRun`/`ResearchTask` — `RunPolicySnapshot` friert Route/Confirmation bereits für Audit ein.

**Kein Eval-Bypass (Invariante, als Akzeptanztest zu formulieren):** Der Evaluations-Harness besitzt keinen eigenen Provider-Client. Alle LLM-Calls laufen über `gateway.invoke`, alle Web-Calls über den Research-Service-Chokepoint (`research/service.py:_firewall_query`). `data_mode` wählt nie einen Provider — Auswahl bleibt bei AgentRegistry-Route + `default_provider_resolver` bzw. `resolver.get_web_provider`.

---

## 3. Design: Usage/Cost (Grundlage EVAL.1)

**Bereits vorhanden (keine Änderung nötig):**
- Tokens pro LLM-Call: `UsageRecord.input_tokens/output_tokens`.
- Tool Calls pro Firecrawl-Request: `ToolInvocation` pro `research_task_id`, gezählt gegen `web_research_max_credits`.
- Latenz: `AgentInvocation.latency_ms` (LLM) und `ToolInvocation.duration_ms` (Web).

**Echte Lücke = Kostensemantik. Empfehlung:**

1. **Neue Spalte `usage_records.cost_status`** — plain String (App-seitig `Literal["priced","unknown_price","not_applicable"]`, kein DB-Enum, passend zur Codebase-Konvention), `server_default='unknown_price'` für Backfill-Sicherheit. Semantik:
   - `not_applicable` = Fake/Local-Provider (kein externer Call),
   - `priced` = `cost_chf` aus der Preistabelle berechnet,
   - `unknown_price` = realer Provider ohne Tabelleneintrag — `cost_chf` bleibt 0.0 und darf **nie** als „0 CHF" summiert werden.
   - Optional eine nullable Spalte `price_version` (String) für Reproduzierbarkeit von `priced`-Records.
2. **Statische Preistabelle im Code** (nicht Config-Datei, nicht DB): späteres Modul `backend/app/evaluation/pricing.py` — `PRICE_TABLE_VERSION` (Datum) + `dict[(provider, model_id)] -> (input_chf_per_1k, output_chf_per_1k)` mit Quellen-Kommentaren. Lookup zur Schreibzeit an den zwei bestehenden Stellen (`agents/cost_guard.py:record_usage`, `runs/service.py:170`). Tabellen-Miss ⇒ `unknown_price`. **Preise werden nie erfunden.**
3. **Firecrawl:** Credits (= ToolInvocation-Count) als native Einheit reporten; zugehörige Usage-Zeilen `unknown_price`, ausser der Owner liefert einen CHF-Preis pro Credit. Keine spekulative Umrechnung.
4. **Latenz-Aggregation:** nichts Neues persistieren; EVAL.1 aggregiert `latency_ms`/`duration_ms` (p50/max) in `evaluation/summary.py` und ersetzt die `None`-Platzhalter in `harness.py`.
5. **Keine Rohinhalte:** Metering-Zeilen enthalten nur Zahlen, Provider-/Modellnamen, Hashes, IDs — Akzeptanzkriterium mit Test.

**Migrationsbedarf:** genau **eine** Alembic-Revision auf Head `a3f8c2d91e47` (`cost_status` + optional `price_version`). SQLite/Postgres-kompatibel (plain String), geringes Risiko.

**Verworfene Alternativen:** (a) Kosten nur zur Reportzeit berechnen — keine Migration, aber die Unterscheidung priced/Platzhalter wäre nicht pro Record persistiert und historische Records würden bei Tabellenänderung stillschweigend „umgepreist"; (b) CostProfile-/Pricing-Tabelle in der DB — Overengineering für den MVP.

---

## 4. Design: Firecrawl Research (RESEARCH.1 Market / RESEARCH.2 Partner)

**Leitentscheid: die bestehende Research-Vertikale wird end-to-end wiederverwendet; es entsteht kein zweiter Web-Pfad.** Firewall, `policy_matrix`, Approval-Flow, Executor, SSRF-Gate und Import-Pipeline bleiben unangetastet und werden as-is genutzt.

**Query Planner (gemeinsam für beide MVPs):** deterministisch, template-basiert, **ohne LLM** — späteres Modul `backend/app/research/planning.py`. Erzeugt Query-Vorschläge: für Market aus `MARKET_SIGNAL_TERMS` + öffentlichen Projektfeldern, für Partner aus `requested_partner_roles`/Kompetenzbedarf. Der Planner **schlägt nur Text vor**; Klassifikation und Gating bleiben vollständig Sache der Firewall. MVP-Scope: **D0-only-Inputs** (öffentliche/synthetische Felder) — keine Approval-Roundtrips; D1/D2-abgeleitete Begriffe würden automatisch im bestehenden `REQUIRE_SANITIZED_APPROVAL`-Pfad landen und sind bewusst deferred.

**Firecrawl Query Execution:** unverändert der bestehende Pfad `research/service.py` (Firewall-Chokepoint) → `research/executor.py` (Policy → CostGuard → `search()` → SSRF → Persistenz). Kein neuer Code an dieser Kette.

**ResearchCandidate-Struktur: dokumentierter Contract über das bestehende `ResearchResult` — kein neues Modell, keine Migration.** Definition:

```
ResearchCandidate (View über ResearchResult):
  result_id, research_task_id, purpose (vom Task),
  source_url / final_url, title, snippet (explizit KEINE Evidence),
  provider_rank, identity_match_status,
  status (candidate | imported | rejected | failed),
  partner_role_suggestions[], source_document_id?
```

Ein neues Modell würde Lifecycle, Import-Verdrahtung und Firewall-Provenienz duplizieren — ohne MVP-Nutzen. Die Market↔Research-Verknüpfung existiert bereits (`MarketComparison.research_task_ids`, `models.py:1505`).

**SourceDocument/SourceFragment/EvidenceAnchor-Anbindung:** unverändert über den bestehenden Import (`import_service.py`): Kandidat → menschlicher Review → Import → `SourceDocument` (type=url) → Ingestion → `SourceFragment`s. EvidenceAnchors entstehen wie bisher **nur** über die deterministische Exact-Quote-Verifikation, nie direkt aus Web-Resultaten.

**RESEARCH.1 Market MVP:** optionaler, explizit human-getriggerter „Live-Research"-**Vorschritt** vor der Comparison: Planner → bestehende ResearchTasks (empfohlen: neuer `ResearchTask.purpose`-Wert `market_comparison` — Owner-Entscheid, da Contract-/OpenAPI-Erweiterung) → Mensch prüft Kandidaten → bestehender Import → importierte Quellen fliessen automatisch via `source_scope.py` in die nächste Comparison-Version (`source_scope_hash`-Änderung ⇒ vorhandene Staleness-Erkennung). Die Vergleichs-/Verifikationslogik selbst bleibt unangetastet; Market ruft weiterhin **nie** Firewall oder Web direkt.

**RESEARCH.2 Partner MVP:** Konsolidierung, keine neue Maschinerie. Fehlende dünne Schicht: (1) deterministischer Planner aus angefragten Rollen, (2) Aggregations-/Read-Endpoint für `partner_role_suggestions` über die Results eines Tasks (Human Review), (3) explizites manuelles „Suggestion übernehmen → Partner anlegen" über das bestehende CRUD. Harte Invarianten: **kein automatisches Kontaktieren von Partnern** (Firecrawl holt nur öffentliche Seiten; keine E-Mails, keine Formulare), Suggestions bleiben advisory („never selects partners"), keine Auto-Erstellung von `Partner`-Rows, Firewall-Lexikon entfernt weiterhin Partnernamen aus Queries. Datenschutz: MVP-Subjekte nur `organisation`/`topic`; personenbezogene Recherche ist deferred (Owner-Entscheid D10).

**synthetic_eval + Firecrawl:** Queries aus synthetischen Daten sind trotzdem echte externe Calls — identischer Firewall-/Approval-/Logging-Pfad, Behandlung als D0/public-source, volle Metering-Erfassung (ToolInvocation + Credits). Kein Eval-Shortcut.

---

## 5. Go/No-Go

| Ticket | Empfehlung | Vorbedingungen |
|---|---|---|
| **EVAL.1 Metering** | **Go** | (1) Owner bestätigt `cost_status`-Spalte + Preistabellen-Scope (D3/D4); (2) eine Alembic-Revision freigegeben (einzelner Head, geringes Risiko); (3) Akzeptanztest „keine Rohinhalte in Metering-Zeilen". Tokens/Latenz/Tool-Counts existieren bereits — kleinstes Ticket, zuerst umsetzen. |
| **EVAL.2 Real Provider Smoke** | **Conditional-Go — Scope: OpenAI + Anthropic + Firecrawl. Azure = No-Go innerhalb EVAL.2** | (1) Azure hat keinen Adapter, keine Settings-Felder und ist policy-blockiert (`provider_policy.py:14-16`) — EVAL.2 darf Azure nicht durch die App versuchen; `scripts/azure-smoke-test.mjs` bleibt reiner Out-of-App-Konnektivitätscheck. (2) EVAL.1 zuerst, damit Smoke-Läufe `cost_status`-Daten produzieren. (3) Manuell, env-gated (`RUN_REAL_PROVIDER_SMOKE=true`); CI bleibt fake-only. (4) Inputs ausschliesslich synthetisch: `data_mode=synthetic_eval`, `AI_EVAL_MODE=real`, `origin=synthetic`. (5) Owner-Spend-Cap pro Session (D7). Hinweis: env-gated Real-Smokes für OpenAI/Anthropic existieren bereits — EVAL.2 ist überwiegend Formalisierung + Metering-Erfassung. |
| **RESEARCH.1 Market MVP** | **Conditional-Go** | (1) Owner-Entscheid purpose-Wert `market_comparison` (D8); (2) D0-only-Planner bestätigt (D9); (3) Firecrawl-Key + Credit-Budget (D11); (4) Regressionstests: Firewall/policy_matrix unangetastet, Market ruft weiterhin nie Web direkt; (5) UI-Scope entscheiden (API-only für die Thesis akzeptabel). |
| **RESEARCH.2 Partner MVP** | **Conditional-Go** | (1) Invariante „Suggestion→Partner nur manuell, kein Auto-Kontakt" dokumentiert + getestet (D10); (2) Subjekt-Scope organisation/topic (Datenschutz); (3) Reihenfolge: nach RESEARCH.1 (gemeinsamer Planner). |

**Empfohlene Reihenfolge:** EVAL.1 → EVAL.2 → RESEARCH.1 → RESEARCH.2.

---

## 6. Risiken

### 6.1 Risikobewertung

| Risiko | Bewertung | Mitigation |
|---|---|---|
| **Datenschutz** | Echte D2 → direkte Provider ist bereits maschinell blockiert (DP-04, key-unabhängig). Restrisiken: Anonymisierungsqualität bei `anonymized_eval`; Personenbezug bei Partner-Research; Firecrawl ist ein US-Dienst, der Query-Text verarbeitet. | `anonymized_eval` ggf. aus Scope nehmen (D2); Partner-MVP nur organisation/topic (D10); D0-only-Planner. |
| **API-Key-Leakage** | Keys nur env-only via `Settings`; `RedactingFilter` + `redaction.py` vorhanden; Metering fügt nur Zahlen/Namen hinzu. Restfokus: `.env`-Handling während manueller EVAL.2-Sessions. | Vorbedingung EVAL.2: Keys nie im Repo, nie in Report-Artefakten; bestehender Guard-Test „kein `NEXT_PUBLIC_*`-Provider-Secret" bleibt Pflicht. |
| **Firecrawl-Query-Leakage** | Sanitization ist explizit Risikoreduktion, keine Geheimhaltungsgarantie. | D0-only-MVP-Planner; `d2_web_research_enabled` bleibt default off; Rohqueries nur als Hash; Approvals single-use. |
| **Kostenexplosion** | Es gibt bewusst **keine CHF-Budget-Durchsetzung** — Guards limitieren Calls/Credits, nicht Geld. | Für MVP so belassen; EVAL.1 macht Spend via `cost_status` post-hoc sichtbar; Smoke-Sessions klein + manuell beaufsichtigt; `RunPolicySnapshot.max_cost_chf` existiert als späterer Hook für einen harten Abbruch (Owner-Entscheid, nicht MVP). |
| **Fehlende Provider-Interfaces (Azure)** | Jeder Plan, der Azure-Evaluation annimmt, scheitert heute (kein Adapter, keine Settings-Felder, policy-blockiert). | EVAL.2-Scope-Ausschluss (§5); zukünftiger Azure-Slice = Adapter + Settings-Felder + `provider_policy`-Tabelleneintrag + institutionelle Freigabe — ausserhalb des Thesis-Eval-Scopes. |
| **Notwendige Migrationen** | Genau eine neue Revision (`usage_records.cost_status` [+ `price_version`]) auf dem einzelnen Head `a3f8c2d91e47`; plain-String-Spalten (Codebase-Konvention). RESEARCH.1/2 benötigen **keine** Migration (Wiederverwendung ResearchTask/ResearchResult; neuer purpose-Wert ist app-level). | Revision klein halten, `server_default` für Backfill. |
| **Eval-Bypass-Versuchung** | Ein Harness mit eigenem Provider-Client würde alle Gates umgehen. | Invariante mit Akzeptanztest: Evaluations-Harness hat keinen eigenen Client — alle LLM-Calls via `gateway.invoke`, alle Web-Calls via Research-Chokepoint (bestehender Provider-Boundary-Test in `test_privacy_firewall.py` als Vorbild). |

### 6.2 Nicht-Ziele (bestätigt)

Keine automatischen Antragseinreichungen; keine automatische finale Übernahme von KI-Texten; keine Budgetlogik im LLM; kein automatisches Kontaktieren von Partnern; Firewall/`policy_matrix`/`redaction` unangetastet; D3/UNKNOWN bleibt in jedem Modus blockiert.

### 6.3 Offene Owner-Entscheidungen

| # | Entscheidung | Empfehlung |
|---|---|---|
| D1 | `data_mode` nur deskriptiv/validierend (kein Enforcement-Pfad)? | Ja (§2) |
| D2 | `anonymized_eval` im Thesis-Scope? (erfordert dokumentiertes Anonymisierungs-Review gem. `testdata-policy.md`) | Deferred — nur `fake_test`/`synthetic_eval`/`real_project` ausliefern |
| D3 | `cost_status`-Spalte + `price_version` ja/nein? | Ja, beide (eine nullable String-Spalte, vernachlässigbare Kosten) |
| D4 | Welche (provider, model)-Paare erhalten Tabellenpreise; Preisquelle/-datum? | Owner liefert; ohne Eintrag bleibt `unknown_price` |
| D5 | Firecrawl: Credits-only-Reporting vs CHF-Preis pro Credit? | Credits-only für MVP |
| D6 | EVAL.2 ohne Azure (No-Go in-App)? | Ja (§5) |
| D7 | Spend-Cap pro EVAL.2-Smoke-Session? | Owner setzt Betrag; Sessions klein halten |
| D8 | Neuer `ResearchTask.purpose`-Wert `market_comparison` (Contract-/OpenAPI-Erweiterung) vs Wiederverwendung eines bestehenden purpose? | Neuer Wert (saubere Audit-Semantik) |
| D9 | Planner MVP D0-only vs D1/D2-Begriffe mit Approval-Flow? | D0-only |
| D10 | Partner-Research: Subjekte nur organisation/topic; Partner-Anlage nur manuell; kein Auto-Kontakt? | Ja, alle drei als Invarianten |
| D11 | Credit-Budget: gemeinsames `web_research_max_credits=50` vs Budget pro Purpose? | Gemeinsames Budget für MVP |
