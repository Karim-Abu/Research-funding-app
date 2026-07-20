# RUN 2A — Ergebnisbericht (Slice 0 + Slice 1)

- **Datum:** 2026-07-19 · **Basis:** `c910dd7` (`main`) · **Discovery:** `docs/IMPLEMENTATION_DISCOVERY.md`
- **Umfang:** Slice 0 (Baseline vollständig und hermetisch grün) + Slice 1 (Compliance-Status von Human Review trennen, Guidance aus Erfüllungsquoten entfernen). Gestoppt vor RUN 2B.
- **Hinweis Kontextdokumente:** `VS_CODE_MASTER_PROMPT.md`, `IMPLEMENTATION_PLAN.md` und `E2E_ACCEPTANCE_MATRIX.md` existieren weder im Repo noch im Workspace (verifiziert per Suche; nur `final_backend_contracts_v1_1/Backend_Implementation_Plan_v1_1.md` existiert unter anderem Namen). Gearbeitet wurde mit den im Auftrag enthaltenen Owner-Entscheiden, der bestätigten Discovery und den Repository-Verträgen.

---

## 1. Slice 0 — Root-Cause-/Fix-Tabelle je Baseline-Fehler

Klassifikation je Fehler: **[R]** Code-Regression · **[F]** Test-/Fixture-Fehler · **[P]** absichtlich geändertes Produktverhalten (Spec/Test war veraltet).

### Backend (pytest, 4 Fehler)

| Test | Klasse | Root Cause | Fix |
|---|---|---|---|
| `test_integrated_draft_real.py::test_run_real_all_a2_fields_metered` (`priced` statt `unknown_price`) | **[F]** | Lokale `backend/.env` (Live-Slice, 16.07.) setzt `AGENT_MODEL_PRICING_CHF_PER_MILLION` + Modell-IDs; die conftest nullte nur API-Keys → Suite nicht hermetisch | `tests/conftest.py`: `HERMETIC_PROVIDER_DEFAULTS` + `apply_hermetic_provider_defaults()` normalisiert pro Test ALLE Provider-Settings (Keys, Modell-IDs, Pricing, Fake-/Live-Flags) auf Felddefaults (=CI). Regressionsbeweis: neu `tests/test_env_hermetic.py` |
| `test_market_comparison.py::test_capability_reflects_market_comparison` (`market_comparison=False`) | **[P]** | Seit dem Live-Preflight-Vertrag (`c65e6c4`/`149ef5e`) verlangt `api/capabilities.py:22-25` für nicht-fake Web-Research einen erfolgreichen persistierten Firecrawl-Preflight (Owner-Entscheid 8); Fixture seedete keinen | Test seedet den Preflight realistisch über den echten Persistenzpfad (`persist_route_preflight`, PASS-Check) und prüft ZUERST den ehrlichen False-Zustand. Preflight-Pflicht unangetastet |
| `test_market_research_api.py::test_run_d0_persists_and_returns_candidates` (12 statt 9) | **[P]** | Planner erzeugt seit `8964dfd` absichtlich 4 Module (`state_of_the_art` via `include_state_of_the_art=True` in `brief_service.py:402`); Assertion pinnte 3×3 | Semantische Assertions: exakt die 4 Zwecke (dedupliziert), 1 Freigabe je Query, `result_count == 3 × freigegebene Queries` |
| `test_integrated_draft.py::test_research_context_used_and_never_evidence` (`market.used=False`) | **[P]** | `retrieve_advisory_research_context` verlangt seit `149ef5e` `content_review_status=="reviewed"` + `support_status in (supports, partially_supports)` + `execution_mode=="live"` (ehrliche Verschärfung); Test-Seed hatte Defaults `not_checked` | Seed setzt den realistischen Post-Review-Zustand (`reviewed`/`supports`); Sicherheitsinvariante (Kandidaten nie Kontext, Research nie Evidenz) unverändert weiter getestet |

### E2E (Playwright, 4 Fehler)

| Spec | Klasse | Root Cause | Fix |
|---|---|---|---|
| `e2e/run-agents.spec.ts:25` (run-suggestion-hint fehlt) + Folgerisiko in `golden-path` Schritt 10 | **[R]** | **Editor-Seite crashte** («This page couldn't load»): `lib/suggestion-view.ts:17` iterierte `section.removed_or_reframed_claims` ungeschützt; Feld-Level-Vorschläge (`PortalFieldDraftBundle`) tragen die Section-Listen nicht → `TypeError: … is not iterable` (empirisch reproduziert mit Konsolen-Capture) | Fallbacks im View-Model (`?? []`) in `lib/suggestion-view.ts` + `components/editor/suggestion-review-dialog.tsx`; `SectionResult`-Typ in `lib/redraft.ts` ehrlich optional dokumentiert |
| `e2e/market-research-flow.spec.ts:139` (Zeile bleibt im Edit-Modus) | **[R]** | `api/market_research.py` Legacy-Preview-Endpoint: `preview_query` liefert seit `149ef5e` eine `ResearchQueryView` (Feld `query_text`), der Endpoint las `approval.sanitized_query` → AttributeError → 500 auf dem EINZIGEN Erfolgspfad des Dialog-Bearbeitens | Endpoint liest die View-Felder (`view.query_text`, `public_safe` aus Status); neuer Regressionstest `test_market_query_approval.py::test_legacy_market_preview_success_returns_new_pending_approval` (der Pfad war zuvor testfrei — deshalb rutschte die Regression durch) |
| `e2e/golden-path.spec.ts:62` (Schritt 9, Button disabled, 5-min-Timeout) | **[P]** | Marktvergleich-Quellen-Gate aus `c910dd7` (bewusst): «Vergleich erstellen» ist ohne live abgerufene, importierte, positiv geprüfte Quelle sichtbar deaktiviert mit Grund (`app/quellen/page.tsx:604`, `market-comparison-section.tsx` `disabledReason`) | Spec prüft den ehrlichen Disabled-Zustand + Grundtext statt zu klicken (CLAUDEX: deaktivierte Buttons erklären sich) |
| `e2e/market-comparison.spec.ts:85` (+ zweite Stelle in `market-research-flow.spec.ts:275`) | **[P]** | dito Quellen-Gate | dito Disabled-Assertion |

**Zwischen-Gate nach Slice 0:** Playwright 47 passed / 1 failed (nur noch die zweite Gate-Klickstelle in market-research-flow, danach gefixt); lint/tsc/build grün; vitest 505/505; pytest voll grün (Gate-Spiegel `-p no:warnings --ignore=test_docx_render_smoke` Exit 0).

---

## 2. Slice 1 — Compliance ≠ Human Review, Guidance

### Umsetzung (minimal-invasiv, keine Migration)

1. **`backend/app/rules/aggregation.py`**: Hybrid-Pass → `fulfilled` (statt `partial`); zusätzlich erzeugt ein erfüllter Hybrid-Check weiterhin ein unabhängiges `human_confirmation_pending`-Issue (severity info). Guidance (Registry-Signatur `severity=="info"`, vorhandenes Feld — keine zweite Registry): nie Issues, nie offen; ohne auswertbare Angaben wird der Hinweis weggelassen statt `needs_input`.
2. **Contract additiv** (`backend/app/contracts/requirement.py`): `review_status: not_required|required|confirmed` und `display_mode: requirement|guidance` auf `RequirementAssessment`. Abgeleitet — keine DB-Migration nötig (Ableitung nachweislich stabil): `required` = offenes Review-Issue; `confirmed` = vorhandene `HumanDecision(action=confirm, target_type=requirement_assessment)` über den bestehenden Endpoint `POST /runs/{id}/human-decisions` (der Assessments per Design nie mutiert).
3. **`human_review_count`** (`review/service.py` → neu `repositories/requirements.py::open_human_review_count`): zählt offene Review-Issues (`requires_human_review` + `human_confirmation_pending`) abzüglich menschlich bestätigter Anforderungen — EINE Zählquelle, nicht mehr `status=="needs_input"`.
4. **UI** (`components/anforderungen/live-requirements.tsx`): Primärbadge = Compliance; Sekundärbadge «Maschinell geprüft · Menschliche Bestätigung offen» bei `fulfilled + required`; Filter «Menschliche Prüfung offen» filtert nach Reviewzustand (`review_status`), nicht nach `partial`; Guidance-Hinweise in eigener Sektion «Hinweise» (`data-testid="guidance-notes"`), zählen in keiner Quote/Gruppe/keinem Filter.

### Fachliche Invariante (getestet)

- 52 % im Band 40–60 % → `fulfilled` + `review_status=required`; exakt 5 % → `fulfilled` + `required`; exakt 40 %/60 % → `fulfilled`; unter 5 % → `blocked`.
- Bestätigung (HumanDecision confirm) ändert NUR `review_status` (→ `confirmed`) und reduziert `human_review_count` um 1; Compliance-Status und `RuleResult` bleiben unverändert.
- Guidance `REQ.INNO.BUDGET.NO_FINANCIAL_CAP`: `display_mode=guidance`, keine Issues, zählt in keiner Quote; ohne Angabe ganz weggelassen.
- Konsistenz: Budget-Precheck, Anforderungsscreen und `ReviewStatusView` zeigen dieselbe Wahrheit (API-Test).

---

## 3. Geänderte Dateien (Zweck)

### Slice 0

| Datei | Zweck |
|---|---|
| `backend/tests/conftest.py` | Hermetik: Provider-Settings-Normalisierung pro Test |
| `backend/tests/test_env_hermetic.py` **(neu)** | Regressionsbeweis Hermetik |
| `backend/tests/test_market_comparison.py` | Capability-Test: ehrlicher False-Zustand + realistisches Preflight-Seeding |
| `backend/tests/test_market_research_api.py` | Semantische Modul-Assertions statt 3×3-Pin |
| `backend/tests/test_integrated_draft.py` | Seed: reviewed/supports gemäss verschärfter Kontextsemantik |
| `backend/app/api/market_research.py` | **Regressionfix**: Legacy-Preview liest ResearchQueryView-Felder |
| `backend/tests/test_market_query_approval.py` | Neuer Regressionstest für den Legacy-Preview-Erfolgspfad |
| `lib/suggestion-view.ts`, `components/editor/suggestion-review-dialog.tsx`, `lib/redraft.ts` | **Crashfix**: Fallbacks für Feld-Level-`section_result` |
| `e2e/golden-path.spec.ts`, `e2e/market-comparison.spec.ts`, `e2e/market-research-flow.spec.ts` | Disabled-Gate-Assertions statt Klick |
| `docs/IMPLEMENTATION_DISCOVERY.md` | §6.3 mit realem Playwright-Resultat (44/4) vervollständigt |

### Slice 1

| Datei | Zweck |
|---|---|
| `backend/app/rules/aggregation.py` | Hybrid-Pass→fulfilled, Guidance-Semantik, Confirmation-Issue; `HUMAN_REVIEW_ISSUE_TYPES`, `is_guidance` |
| `backend/app/contracts/requirement.py` | Additiv `review_status`, `display_mode` |
| `backend/app/repositories/requirements.py` | Ableitung beider Felder + `open_human_review_count` (eine Zählquelle) |
| `backend/app/review/service.py`, `backend/app/contracts/review.py` | `human_review_count` neue Semantik + Doku |
| `backend/tests/test_registry_rules.py` | Pin-Update (Owner-autorisiert): `hybrid pass ⇒ fulfilled + Bestätigungs-Issue` |
| `backend/tests/test_discovery_red_compliance_status.py` | **Promotion** aus xfail zu normalen Regressionstests |
| `backend/tests/test_compliance_review_separation.py` **(neu)** | Mandats-Testmatrix (Grenzen, Bestätigungsfluss, Guidance, Konsistenz) |
| `backend/tests/test_requirements_flow.py`, `test_review_status_view.py`, `test_draft_flow.py`, `test_evidence_flow.py` | Alt-Pins auf neue Owner-Semantik aktualisiert |
| `lib/requirements.ts` | Typen `ReviewStatus`/`DisplayMode` + DTO-Felder + Labels |
| `components/anforderungen/live-requirements.tsx` | Badges, Filter, Hinweise-Sektion, Quoten-Ausschluss |
| `test/live-requirements.test.tsx` | 3 neue UI-Tests (Badge, Bestätigt, Guidance) |
| `e2e/requirements-rules.spec.ts` | fulfilled+review_status statt partial |

Unverändert aus dem Discovery-Lauf: `backend/tests/test_discovery_red_import_reset.py`, `…_project_duration.py` (bleiben xfail — RUN 2B).

---

## 4. API-/Contract-Änderungen

- **Additiv** `RequirementAssessment`: `review_status` (`not_required|required|confirmed`, Default not_required) und `display_mode` (`requirement|guidance`, Default requirement). Abgeleitete Read-Felder; kein Pflichtfeld, keine bestehende Semantik entfernt.
- **Semantik präzisiert** (dokumentiert in `contracts/review.py`): `ReviewStatusView.human_review_count` zählt offene Human-Review-/Confirmation-Issues (abzüglich bestätigter), nicht mehr needs_input-Assessments.
- **Verhaltensänderung gemäss Owner-Entscheid**: `RequirementAssessment.status` für bestandene Hybrid-Regeln neu `fulfilled` (vorher `partial`); Guidance-Anforderungen erscheinen nur noch mit Daten und nur als Hinweis.
- **Bugfix ohne Vertragsänderung**: `POST /projects/{id}/market-research/queries/preview` liefert wieder den dokumentierten `QueryCandidateDto` (vorher 500).
- Keine neuen Routen, keine entfernten Felder, kein OpenAPI-Schema-Bruch.

## 5. Migrationen / Rollback

**Keine Datenbankmigration.** `review_status`/`display_mode` sind abgeleitete Read-Felder (OpenIssues + HumanDecisions + Registry). Rollback = Revert der Commits; bestehende Daten sind nicht betroffen. Bereits persistierte Assessments alter Läufe behalten ihren gespeicherten Status (`partial`-Zeilen alter Läufe bleiben lesbar; neue Läufe schreiben die neue Semantik).

## 6. Testmatrix (tatsächliche Resultate/Laufzeiten, 2026-07-19/20)

| Gate | Slice-0-Baseline (vor Fixes) | Nach Slice 0 | Nach Slice 1 (final) |
|---|---|---|---|
| `corepack pnpm lint` | PASS (12 s) | PASS | PASS |
| `corepack pnpm exec tsc --noEmit` | PASS (21 s) | PASS | PASS (0 Fehler) |
| `corepack pnpm build` | PASS (36 s) | PASS (31 s) | PASS |
| `corepack pnpm test` (Vitest) | 505/505 (78 s) | 505/505 (41 s) | **508/508** (39 s) |
| `python -m pytest` (voll, ohne DOCX-Smoke) | **4 FAILED** (454 s) | Exit 0 (340 s) | **Exit 0, voll grün** (nach Umbenennung `test_z_compliance_review_separation.py` — Kollision mit der Projekt-Isolationsinvariante von `test_demo_seed.py` behoben) |
| `playwright test --workers=1` | **4 failed** / 44 (616 s) | **1 failed** / 47 (416 s; Rest-Spec danach gefixt) | **47 passed / 1 failed** (48 Tests, ~336 s) — der eine Fehlschlag ist ein **bestätigtes, vorbestehendes Timing-Flake** (siehe unten), keine Regression |
| Live-Smokes (Firecrawl/OpenAI/Anthropic) | **not_run** (Opt-in, bewusst nicht ausgeführt — keine Owner-Freigabe für bezahlte Calls in diesem Run; `not_run` ≠ PASS) | not_run | not_run |

### E2E-Flake-Klassifikation: `e2e/import-flow.spec.ts` (Zeilen 203/223)

Nach dem finalen Vollsuiten-Lauf war `import-flow.spec.ts:203` («zeigt nachvollziehbare Phasen bis zum Review») der einzige Fehlschlag (Timeout beim Warten auf `getByTestId("import-review")`). Klassifikation gemäss Mandat («1 Wiederholung zur Flake-Klassifikation»):

1. Isolierter Einzellauf (frisch gestartete Server) → **4/4 PASS** (3.9 s bzw. 2.2 s statt der vorherigen 60 s/45 s-Timeouts).
2. `--repeat-each=3` (12 Läufe: 4 Tests × 3) → **9 passed / 3 failed** — 2× dieselbe Phasen-Prüfung, 1× die Fehlerpfad-Prüfung (Zeile 223), beide mit demselben Timeout-Muster.

Damit ist der Fehlschlag als **intermittierendes, vorbestehendes Timing-Flake in der PDF-Upload-/Textextraktions-Pipeline** klassifiziert — nicht deterministisch, nicht durch die Slice-0/1-Änderungen verursacht (weder Import- noch Upload-Code wurde in diesem Run berührt). Root-Cause-Vermutung: variable PDF-Extraktionsdauer unter Systemlast überschreitet das 60-s-Timeout knapp. **Dokumentiert statt gefixt** (ausserhalb des Slice-0/1-Umfangs); Empfehlung für einen späteren Slice: Timeout auf 90 s erhöhen oder auf einen expliziten Phasenwechsel-Event statt auf das Erscheinen von `import-review` warten.

## 7. git diff --stat (gegen `c910dd7`, unkommittiert)

```text
 backend/app/api/market_research.py             |   9 ++-
 backend/app/contracts/requirement.py           |  12 +++
 backend/app/contracts/review.py                |   7 +-
 backend/app/repositories/requirements.py       |  66 ++++++++++++++--
 backend/app/review/service.py                  |  15 ++--
 backend/app/rules/aggregation.py               |  60 +++++++++++++--
 backend/tests/conftest.py                      |  63 +++++++++++----
 backend/tests/test_draft_flow.py               |   3 +-
 backend/tests/test_evidence_flow.py            |   5 +-
 backend/tests/test_integrated_draft.py         |   5 ++
 backend/tests/test_market_comparison.py        |  35 ++++++++-
 backend/tests/test_market_query_approval.py    |  26 +++++++
 backend/tests/test_market_research_api.py      |  29 ++++++-
 backend/tests/test_registry_rules.py           |  13 +++-
 backend/tests/test_requirements_flow.py        |  14 +++-
 backend/tests/test_review_status_view.py       |  23 ++++--
 components/anforderungen/live-requirements.tsx |  52 +++++++++++--
 components/editor/suggestion-review-dialog.tsx |  21 +++--
 e2e/golden-path.spec.ts                        |  17 +++--
 e2e/market-comparison.spec.ts                  |  14 +++-
 e2e/market-research-flow.spec.ts               |  15 ++--
 e2e/requirements-rules.spec.ts                 |   9 ++-
 lib/redraft.ts                                 |  17 +++--
 lib/requirements.ts                            |  14 ++++
 lib/suggestion-view.ts                         |   9 ++-
 test/live-requirements.test.tsx                | 101 +++++++++++++++++++++++++
 26 files changed, 556 insertions(+), 98 deletions(-)

Neue Dateien (untracked):
 backend/tests/test_discovery_red_compliance_status.py   (promoted Regressionstests #4)
 backend/tests/test_discovery_red_import_reset.py        (xfail, RUN 2B)
 backend/tests/test_discovery_red_project_duration.py    (xfail, RUN 2B)
 backend/tests/test_env_hermetic.py                      (Hermetik-Regressionsbeweis)
 backend/tests/test_z_compliance_review_separation.py    (Mandats-Testmatrix Slice 1)
 docs/IMPLEMENTATION_DISCOVERY.md                        (Discovery, §6.3 vervollständigt)
 docs/RUN_2A_RESULT.md                                   (dieser Bericht)
```

Anmerkung: Die Matrix-Testdatei heisst `test_z_…`, weil die Suite-Konvention
projekterzeugende API-Tests nach `test_demo_seed.py` einsortiert (dessen
Isolations-Invariante verlangt exakt zwei Projekte zu seinem Zeitpunkt).

## 8. Offene Risiken

1. **Alte Läufe mit persistiertem `partial`**: Läufe vor RUN 2A zeigen für Hybrid-Pässe weiterhin den gespeicherten Status `partial`, bis sie neu ausgeführt werden (bewusst: keine Datenmigration; Discovery-Semantik «alte Runs nie unmarkiert umdeuten»).
2. **`review_status=confirmed` überlebt Re-Runs nicht**: Nach einem neuen Lauf entstehen neue Assessment-IDs; Bestätigungen gelten pro Lauf (konsistent mit Recheck-Semantik, aber dem Owner bewusst zu machen).
3. **149ef5e-Hygiene**: Der Commit enthielt `app.db` und Logdateien im Git; nicht in diesem Run bereinigt (P2, separater Commit empfohlen: `git rm --cached`).
4. **Skill-Widerspruch** `Slice-Abschlussprüfung.md` («ALL GREEN») vs. `verify_all.ps1` (bewusst 6 Kategorien) bleibt dokumentiert, unentschieden.
5. OneDrive-Umgebung: Laufzeiten variieren stark; SQLite-Single-Writer verlangt strikt sequenzielle Gates.
6. **Vorbestehendes E2E-Flake** in `e2e/import-flow.spec.ts:203/223` (PDF-Upload-Phasen-Timeout unter Last, ~25 % Fehlschlagsrate bei Wiederholung) — dokumentiert in §6, nicht gefixt (ausserhalb Slice 0/1). Empfehlung: Timeout erhöhen oder auf Phasenwechsel-Event statt Element-Sichtbarkeit warten.

## 9. Explizite Nicht-Änderungs-Bestätigung

In diesem Run **nicht verändert**: Import-Reset/Re-Edit (Discovery-Red-Tests bleiben xfail), Projektdauer-Ableitung (dito), Evidence-Source-Scoping (`evidence/discovery.py` unangetastet), Web-/LLM-Provider und Provider-Policy (nur der Legacy-Preview-AttributeError-Fix; kein neuer Provider, kein Gate gelockert, kein stiller Fallback eingeführt), Marktvergleichs-/Editor-Design (nur Crash-Fallbacks + Spec-Anpassungen an bestehendes Gate), Datenmodell/Quellenrollen (keine Migration). RUN 2B wurde nicht begonnen.
