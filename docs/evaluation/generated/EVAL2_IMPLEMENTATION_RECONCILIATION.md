---
title: "EVAL2 — Implementation Reconciliation"
date: 2026-07-25
commit: 8416914
status: generated
tags: [eval2, reconciliation, requirements, design-decisions]
---

# EVAL2 — Implementation Reconciliation

Abgleich der formativen Design- und Feedback-Entscheidungen gegen den Code —
und gegen **tatsächlich ausgeführte** Tests.

> **Namensklärung.** Das Repository verwendet `EVAL0/EVAL1/EVAL2` bereits anders:
> `docs/evaluation/eval2_real_provider_smoke_report.md` ist ein
> *Real-Provider-Smoke*, nicht diese Reconciliation. Dieses Dokument ist die
> **Thesis-EVAL2**.

Grundlage: [[EVALUATION_BASELINE]] · Testergebnisse: [[EVAL3_TECHNICAL_VERIFICATION]] ·
Requirement-Abdeckung: [[EVAL3_REQUIREMENT_COVERAGE]]

## Lesart (drei getrennte Spalten)

Bewusst getrennt, weil sie oft verwechselt werden:

- **Implementierungsstatus** — existiert der Code?
- **Testpfad** — existiert ein Test?
- **Aktuelles Testergebnis** — ist dieser Test in diesem Lauf gelaufen und grün?

Ein Plan oder Milestone-Bericht ist **kein** Implementierungsnachweis.
Ein Codepfad ist **kein** bestandener Test. Eine Testdatei ist **kein**
ausgeführtes Ergebnis.

Wo die ursprüngliche Feedbackquelle nicht im Repository liegt, steht
`feedback-source-in-obsidian` — der Inhalt wurde **nicht** rekonstruiert.

## Übersicht

| Status | Anzahl |
|---|---|
| `implemented` | 20 |
| `partially-implemented` | 2 |
| `contract-only` | 1 |
| `not-found` | 1 |

Testergebnisse beziehen sich auf die Läufe `R-BACKEND-01` (1514 Tests, 6 Fehler),
`R-VITEST-01` (631 Tests, 0 Fehler) und `R-GATE-01`.

## Reconciliation-Tabelle

| FDC ID | Entscheidung | Quelle im Repository | Requirement/ADR | Implementierungsstatus | Codepfad | Testpfad | Aktuelles Testergebnis | Lücke |
|---|---|---|---|---|---|---|---|---|
| FDC-01 | Scope-Reduktion auf Innosuisse | `Milestone_4`, `instrument_scope.not_valid_for` | Registry `innosuisse-innovation-project-…` | `implemented` | `backend/app/registry/loader.py` (`EXPECTED_PROFILE_ID`) | `test_registry_rules.py`, `test_registry_metadata.py`, `test_draft_scope.py` | **tested-pass** | — |
| FDC-02 | Portal-Field-Orientierung | `Milestone_6`, `06_INNOLINK_FIELD_WORKFLOW` | 165 `portal_fields` | `implemented` | `registry/loader.py::PortalFieldDef`, `api/fields.py`, `lib/portal-fields.ts` | `test_portal_fields.py`, `test/fields.test.ts`, `test/subsections.test.ts` | **tested-pass** | Nur 18 Felder `agent_writable`, A2-Allow-List sogar nur 6 — dokumentiert, nicht als Lücke gewertet |
| FDC-03 | Partner- und Budget-Schritt | `Milestone_4`, `Repair_R3` | `REQ.INNO.PARTNER.*`, `REQ.INNO.BUDGET.*` | `implemented` | `api/partners.py`, `rules/handlers.py`, `components/partner/*` | `test_partners.py`, `test_project_budget.py`, `e2e/partner-budget.spec.ts` | **tested-pass** | — |
| FDC-04 | Editierbare feldbasierte Entwürfe | `Milestone_6` | — | `implemented` | `backend/app/drafts/`, `fields/service.py`, `components/editor/draft-editor.tsx` | `test_draft_flow.py`, `test_draft_versions.py`, `e2e/template-drafts.spec.ts` | **tested-pass** | — |
| FDC-05 | Zweispaltiger Entwurf-/Vorschlagseditor | `Milestone_9D`, `Milestone_10_3` | — | `implemented` | `draft-workspace-shell.tsx:716` (`lg:grid-cols-2`), `suggestion-review-dialog.tsx` | `live-editor-a2.test.tsx`, `suggestion-review-dialog.test.tsx`, `e2e/run4b-editor.spec.ts` | **tested-pass** | «Side-by-side» = *eigener Text vs. ein Vorschlag* |
| **FDC-06** | **Auswählbare KI-Textvarianten** | — (keine Requirement-/ADR-Quelle auffindbar) | — | **`not-found`** | siehe Befund unten | `suggestion-review-dialog.test.tsx` prüft **einen** Vorschlag | **n/a** | **Mehrfachvarianten existieren nicht** |
| FDC-07 | Versionsverlauf | `Milestone_7` | — | `implemented` | `api/fields.py:198` `GET …/versions`, `repositories/drafts.py` | `test_draft_versions.py`, `test/fields-versions.test.ts`, `live-editor-versions.test.tsx` | **tested-pass** | — |
| FDC-08 | Innolink-Copy-/Export-Workflow | `Milestone_8`, `Milestone_8_1` | — | `implemented` | `lib/portal-transfer.ts`, `api/fields.py:542` `create_copy_event`, `app/exports/` | `test_field_copy_events.py`, `test_z_copy_readiness.py`, `e2e/portal-transfer.spec.ts`, `e2e/export.spec.ts` | **tested-pass** | — |
| FDC-09 | Offene Fragen / fehlende Informationen | `Repair_R2` | `OpenIssue` | `implemented` | `agents/missing_inputs.py`, `lib/fix-queue.ts`, `components/review/fix-queue.tsx` | `test_run3c_missing_inputs.py`, `test_fix_queue.py`, `test/placeholders.test.ts` | **tested-pass** | — |
| FDC-10 | Requirements-/Conditions-Prüfung | `Milestone_4` | 12 `official_core_rules` | `implemented` | `rules/engine.py`, `handlers.py`, `aggregation.py` | `test_requirements_flow.py`, `test_registry_rules.py`, `e2e/requirements-rules.spec.ts` | **tested-pass** | 4 der 12 Regeln ohne eigene Testreferenz → [[EVAL3_REQUIREMENT_COVERAGE]] |
| FDC-11 | Evidence Anchoring | `Milestone_5`, `Milestone_9C` | — | `implemented` | `backend/app/evidence/` (discovery, verification, scope_policy) | `test_evidence_flow.py`, `test_evidence_verification.py`, `e2e/evidence.spec.ts` | **tested-pass** | — |
| FDC-12 | Human Review und Approval | `Milestone_7` | — | `implemented` | `backend/app/review/`, `security/approval_service.py` | `test_review_approval.py`, `test_review_truth.py`, `e2e/review-recheck-approval.spec.ts` | **tested-pass** | — |
| **FDC-13** | **Quality Gates** | `innosuisse_…_v1_1.yaml` (64 `QG.*` + 17 `XF.*`) | `REQ.PORTAL.*` (64) | **`contract-only`** | **keine** — 0 Codetreffer | — | **n/a** | **64 Gates spezifiziert, nicht implementiert** (Befund unten) |
| FDC-13b | Quality-Layer (implementierte Variante) | `Milestone_9K` | — | `implemented` | `review/checks.py`, `review/rubric.py` (Rubric v0, nie blockierend) | `test_z_rubric_v0.py`, `test_review_findings.py` | **tested-pass** | Andere Ebene als FDC-13 — nicht deren Ersatz |
| FDC-14 | Markt-/Konkurrenzvergleich | `Milestone_9I_B` | — | `implemented` | `backend/app/market/`, `components/editor/market-*.tsx` | `test_market_comparison.py`, `test_market_judgment.py`, `e2e/market-comparison.spec.ts` | **tested-pass** | Frontend-WIP nicht committet (siehe Baseline) |
| FDC-15 | Markdown-Ausgabe | `Milestone_8` | — | `implemented` | `exports/generators/markdown.py` | `test_export_generators.py`, `test/exports.test.ts`, `e2e/export.spec.ts` | **tested-pass** | — |
| FDC-16 | Datenschutz und Datenklassifikation | `Data_Classification_and_Tool_Policy.md`, `Milestone_9D_2` | `data_policy_v1_1.yaml` | `implemented` | `policy/classification.py`, `security/policy_matrix.py`, `runs/cloud_policy.py` | `test_data_class.py`, `test_processing_gate.py`, `test/data-classification.test.ts` | **tested-pass** | — |
| FDC-17 | Search Query Firewall | `Search_Query_Firewall.md`, `Milestone_9J` | — | `implemented` | `security/search_query_firewall.py`, `research/query_composer.py` | `test_privacy_firewall.py`, `e2e/privacy-firewall.spec.ts` | **tested-pass** | Sanitisierung ist Risikoreduktion, keine Geheimhaltungsgarantie (so dokumentiert) |
| FDC-18 | No-Raw-Logging | `No_Raw_Logging_Guide.md`, `Milestone_10_1` (F1) | — | `implemented` | `security/redaction.py` (`assert_no_raw_query`), `config/logging.py` | `test_import_no_raw_logging.py`, `test_eval1_smoke_no_raw.py`, `test_m10_smoke.py::test_no_raw_log` | **tested-pass** | — |
| FDC-19 | Browser Storage | `Milestone_10_4` | — | `implemented` | `lib/intake-store.ts`, `lib/rich-editor-cache.ts` (sessionStorage, nie localStorage) | `test/intake-store.test.ts`, `test/rich-editor-cache.test.ts` | **tested-pass** | Einziges `localStorage`: Sidebar-Flag (kein Inhalt) |
| FDC-20 | Provider-/Policy-Gateway | `Milestone_9A`, `provider-policy.md` | `controls.yaml` | `implemented` | `agents/gateway.py`, `config/provider_policy.py` | `test_agent_gateway.py`, `test_provider_policy.py`, `test_env_hermetic.py` | **partially-tested** | `test_a2_generation.py` (2 Fälle) und `test_live_readiness.py` **fehlgeschlagen** — siehe `runs/BACKEND-01/failures.md` |
| FDC-21 | Lokale Datenhaltung | `Milestone_1`, `Milestone_2` | — | `implemented` | `config/settings.py` (SQLite, `var/`), `storage/local.py` | `test_m10_migrations.py`, `test_sources.py`, `test_export_security.py` | **tested-pass** | — |
| FDC-22 | Kein automatisches Innolink-Submit | `Innolink_Copy_Paste_Guide.md`, `13_FABLE_REVIEW_BRIEF` | — | `implemented` | **kein Submit-Endpoint vorhanden**; nur `copy.requested`-Events | `test_field_copy_events.py`, `test/clipboard.test.ts`, `e2e/portal-transfer.spec.ts` | **tested-pass** | Negativnachweis (Abwesenheit) — sauber belegbar |
| FDC-23 | Laufzeit- und Kostentransparenz | `Milestone_10`, HEAD-Commit | — | `partially-implemented` | `evaluation/pricing.py` (`effective_from`, fail-closed), `api/costs.py`, `lib/kosten-live.ts` | `test_eval1_pricing.py`, `test_costs_api.py`, `test/kosten-live-view.test.ts` | **partially-tested** | `test_live_readiness.py::test_fresh_persisted_route_preflight_expires` **fehlgeschlagen** (`pricing_version` `'2026-07-25.1'` statt `'test-v1'`) |

## Die zwei wesentlichen Abweichungen

### FDC-06 — «Auswählbare KI-Textvarianten» existieren nicht

Selbst am Code verifiziert:

- `backend/app/repositories/draft_suggestions.py:135` —
  `get_proposed_for(...) -> DraftSuggestion | None` über `db.scalar(...)`.
  Strukturell **höchstens ein** Vorschlag je (Draft, `base_version_id`,
  `target_section`).
- `backend/app/agents/field_drafting.py:573` — eine Wiederholungsanfrage gibt
  denselben Vorschlag mit `status="reused"` zurück, erzeugt keine zweite Variante.
- `expire_superseded(...)` verwirft ältere Vorschläge, statt sie als
  Alternativen zu halten.
- `components/editor/suggestion-review-dialog.tsx` rendert genau **einen**
  Vorschlag; `onRegenerate` (Z. 61/81/823) **ersetzt** ihn.
- Die 7 `AI_GOALS`-Chips in `lib/draft-ai-actions.ts` steuern **eine** folgende
  Generierung — keine parallelen Varianten.

**Einordnung:** ein Vorschlag zur Zeit, sequenziell neu erzeugbar, nie eine
Auswahl nebeneinander. Das «side-by-side» aus `Milestone_9D` meint *aktueller
Text vs. ein Vorschlag*. Für die Arbeit heisst das: dieses Feedback ist
**nicht umgesetzt** — weder als Lücke im Code noch als Fehlfunktion, sondern als
nie gebaute Funktion. Eine Requirement- oder ADR-Quelle dafür liess sich im
Repository nicht finden → sofern das Feedback existiert, liegt es ausserhalb
(`feedback-source-in-obsidian`).

### FDC-13 — 64 Quality Gates sind spezifiziert, aber nicht implementiert

- `final_backend_contracts_v1_1/innosuisse_innovation_project_v1_1.yaml`
  definiert **64 `QG.*`-Portal-Quality-Gates** und **17 `XF.*`-Cross-Field-Rules**
  mit vollständiger `condition`, `severity`, `triggers`, `implementation_state`.
- `backend/app/registry/loader.py:222` liest ausschliesslich
  `raw.get("official_core_rules")` und wirft ohne diesen Block einen
  `RegistryError`. `portal_quality_gates` und `cross_field_rules` werden nie
  gelesen.
- Ein Grep nach `QG.` und `XF.` über `backend/app`, `lib`, `components` liefert
  **null Treffer** (selbst verifiziert).
- Folge: die 64 `REQ.PORTAL.*`-Requirements tragen keine ausgewertete Regel.

**Einordnung:** Der Contract wirkt vollständiger als das System. Für die
Coverage-Rechnung ist das entscheidend — deshalb weist
[[EVAL3_REQUIREMENT_COVERAGE]] beide Nenner getrennt aus (12/76 gegen 12/12).
Die implementierte Qualitätsebene (`review/checks.py`, Rubric v0) ist eine
**andere** Ebene und wird als FDC-13b separat geführt, nicht als Erfüllung von
FDC-13.

## Was diese Tabelle nicht behauptet

- **tested-pass** heisst: der genannte Test lief in diesem Lauf und war grün.
  Es heisst nicht, dass die Anforderung fachlich vollständig geprüft ist.
- Für die E2E-Zeilen gilt das Ergebnis aus `R-GATE-01`; wo das Gate rot ist,
  steht das in [[EVAL3_TECHNICAL_VERIFICATION]].
- Kein Eintrag stützt sich auf einen Milestone-Bericht als Nachweis. Wo nur ein
  Bericht existierte, steht `contract-only`, `not-found` oder `partially-*`.
