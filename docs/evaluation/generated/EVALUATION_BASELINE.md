---
title: "EVALUATION BASELINE — EVAL2/EVAL3"
date: 2026-07-25
commit: 8416914
status: non-frozen-working-tree
tags: [evaluation, baseline, eval2, eval3, reproducibility]
---

# Evaluation Baseline

Reproduzierbarer Ausgangszustand für [[EVAL2_IMPLEMENTATION_RECONCILIATION]] und
[[EVAL3_TECHNICAL_VERIFICATION]]. Erhoben **vor** jeder Testausführung.

> **Statuskennung: `non-frozen-working-tree`.**
> Der Working Tree ist nicht sauber. Alle in diesem Lauf erhobenen Messwerte
> beziehen sich auf **Commit `8416914` + 34 nicht committete Dateien**, nicht auf
> einen versionierten Stand. Es wurde bewusst **nichts committet** und nichts
> gestasht.

## 1. Umgebung

| Feld | Wert |
|---|---|
| Repository-Pfad | `c:\Users\karim\OneDrive - FHNW\Documents\Bachelorthesis\App\Reasearch-funding-app` |
| Datum und Uhrzeit (Start) | 2026-07-25 22:57:56 +0200 (`2026-07-25T20:57:56Z`) |
| Git-Branch | `main` |
| Git-Commit | `841691415750862644cdd2c1c9af2dc63208db9b` (`8416914`) |
| Commit-Datum | 2026-07-25 17:41:05 +0200 |
| Commit-Betreff | `feat: add live cost tracking and system status features` |
| Git-Tag auf HEAD | **keiner** (`git describe`: `repair-r3-done-125-g8416914` → 125 Commits nach dem letzten Tag) |
| Working Tree | **dirty** — 31 geändert/gelöscht, 3 unversioniert |
| Betriebssystem | Windows 11 Pro, Build 10.0.26200 |
| Python-Version | 3.13.6 (`backend/.venv`) |
| Node-Version | v24.16.0 |
| Package-Manager | pnpm 11.5.3 (via corepack) |
| Frontend-Version | Next.js 16.2.6, React 19.2.4 |
| Backend-Version | `api_version` 1.1.0, `policy_version` 1.1.0, `agent_registry_version` 1.1.0, `rule_registry_version` 1.1.0, `requirement_registry_version` 1.0.0 |
| Alembic-Head | `c4d7e1f9a2b3` (`c4d7e1f9a2b3_usage_exact_costs_usd.py`), 40 Migrationen |
| Datenbankmodus | Tests: temporäre SQLite je Lauf (`conftest.py`); Gate-E2E: Wegwerf-DB `backend/var/verify_e2e.db`. `backend/app.db` wird **nicht** berührt |
| Provider-Modus | deterministic / fake — erzwungen (siehe §3) |
| Verwendete Testdaten | synthetisch/öffentlich; Demo-Seed `--reset --evaluation` gemäss [[Evaluation_Dataset]] |

## 2. Nicht committete Dateien (Stand bei Laufbeginn)

Inhalte werden **nicht** wiedergegeben — nur Pfade und Änderungsart.

Herkunft: (a) unfertiger Markt-WIP, der bereits vor dieser Sitzung bestand,
(b) die UI-Bereinigung vom 2026-07-25 (dokumentiert in `docs/UI_CLEANUP_2026-07-25.md`).

```
 M backend/app/agents/prompts/CHANGELOG.md
 D backend/app/agents/prompts/market_comparison_v2.md
 M backend/tests/test_prompt_snapshots.py
 M components/anforderungen/live-requirements.tsx
 M components/anforderungen/requirements-controls.tsx
 M components/editor/draft-workspace-shell.tsx
 M components/editor/live-editor.tsx
 M components/editor/live-market-comparison.tsx
 M components/editor/market-comparison-basis.tsx
 M components/editor/market-comparison-sheet.tsx
 M components/editor/market-research-panel.tsx
 M components/quellen/market-comparison-section.tsx
 M components/quellen/public-research-panel.tsx
 M components/research/query-approval-list.tsx
 M docs/repair/message-catalog.md
 M final_backend_contracts_v1_1/role_skills_v2.yaml
 M lib/evidence-ladder.ts
 M lib/evidence.ts
 M lib/market-comparison.ts
 M lib/market-view.ts
 M lib/requirements-view.ts
 M lib/requirements.ts
 M lib/review-view.ts
 M test/evidence.test.ts
 M test/live-editor-a2.test.tsx
 M test/live-market-comparison.test.tsx
 M test/live-requirements.test.tsx
 M test/market-comparison-section.test.tsx
 M test/market-comparison-sheet.test.tsx
 M test/market-research-panel.test.tsx
 M test/market-view.test.ts
?? backend/app/agents/prompts/market_comparison_v3.md
?? components/editor/market-blocks.tsx
?? docs/UI_CLEANUP_2026-07-25.md
```

**Konsequenz für die Interpretation:** Ergebnisse dieses Laufs sind nicht ohne
Weiteres von Dritten reproduzierbar, solange diese Änderungen nicht committet
sind. Für eine zitierfähige Messung müsste der Stand eingefroren werden.

## 3. Provider-Modus und Kostenschutz

`backend/.env` ist auf dieser Maschine **live** konfiguriert:

| Flag | Wert |
|---|---|
| `APP_ENV` | `development` |
| `AI_EVAL_MODE` | `real` |
| `AGENT_FAKE_PROVIDER` | `false` |
| `WEB_RESEARCH_ENABLED` | `true` |
| `WEB_RESEARCH_FAKE_PROVIDER` | `false` |
| `DEMO_DATA_ENABLED` | `false` |

Echte Schlüssel für Anthropic, OpenAI, Azure OpenAI und Firecrawl liegen vor.
**Es werden keine Schlüsselwerte in diesem oder einem anderen erzeugten Bericht
wiedergegeben.**

Trotzdem erfolgt in diesem Lauf **kein einziger kostenpflichtiger Aufruf**. Drei
unabhängige Schutzschichten:

1. **`backend/tests/conftest.py`** setzt `AI_EVAL_MODE=off`, solange
   `RUN_REAL_PROVIDER_SMOKE != "true"`, und neutralisiert über die autouse-Fixture
   `_no_real_provider_keys` pro Test sämtliche Keys, Modell-IDs, Preistabellen und
   Live-/Fake-Flags auf die CI-Defaults (`HERMETIC_PROVIDER_DEFAULTS`).
   Regressionsbeweis: `backend/tests/test_env_hermetic.py`.
2. **`scripts/verify_all.ps1`** exportiert vor dem E2E-Abschnitt
   `AI_EVAL_MODE=off`, `AGENT_FAKE_PROVIDER=true`, `WEB_RESEARCH_FAKE_PROVIDER=true`.
3. **Laufregel:** `RUN_REAL_PROVIDER_SMOKE` wird nie gesetzt; `backend/.env` wird
   nicht verändert.

Damit bleiben folgende Tests bewusst unausgeführt
(`blocked-requires-explicit-live-approval`):
`test_a1_real_provider_smoke.py`, `test_a1_mapping_real_provider_smoke.py`,
`test_agent_real_provider_smoke.py`, `test_role_routing_real_e2e.py` sowie
sämtliche kostenpflichtigen Skripte unter `scripts/`.

Modi 3–5 der [[Provider_Mode_Matrix]] (real OpenAI/Anthropic, real Firecrawl,
Azure Enterprise) sind **nicht** Teil dieses Laufs.

## 4. Begründung der Neuerhebung (Reuse-First)

Vorhandene Laufartefakte wurden nicht blind wiederholt. Geprüft wurde, ob seit
ihrer Erzeugung Code geändert wurde, von dem sie abhängen.

Der HEAD-Commit `8416914` (2026-07-25) liegt **nach allen** vorhandenen
Artefakten (≤ 2026-07-23) und umfasst:

- **105 Dateien, +6386 / −2907 Zeilen**
- **eine neue Migration:** `c4d7e1f9a2b3_usage_exact_costs_usd.py` — das
  DB-Schema hinter Usage/Kosten hat sich geändert
- Änderungen an genau den Modulen, aus denen die Artefakte stammen:
  `app/evaluation/pricing.py`, `app/evaluation/reprice.py`,
  `app/evaluation/auto_preflight.py`, `app/db/models.py`, `app/api/costs.py`,
  `app/market/{executor,judgment,service}.py`
- **16 geänderte Backend-Testdateien**

`backend/var/evaluation/EvaluationRunSummary.json` (2026-07-23) wurde folglich
gegen ein anderes Schema und eine andere Preistabelle erzeugt → `stale`.
Die vollständige Wiederverwendungs-Entscheidung je Artefakt steht in
[[TECHNICAL_EVIDENCE_INVENTORY]].

## 5. Geltungsbereich

- Kein Produktionscode, keine Requirements, keine Contracts werden verändert.
- Keine Tests werden angepasst, gelöscht oder abgeschwächt.
- Fehlgeschlagene Tests bleiben fehlgeschlagen und werden als solche berichtet.
- Keine EVAL4-Bewertung.

Siehe [[EVAL3_EXECUTION_PLAN]] für die geplanten Läufe und
[[README]] für den Einstieg.
