# EVAL.1 — Usage-/Cost-Metering Smoke-Report (F1, Fake-Provider)

*Generiert:* deterministisch (ohne Zeitstempel) · *Preistabelle:* `2026-07-08.0`

## Pflichthinweise

- **Fake-/Demo-Provider**: Alle LLM- und Web-Calls liefen über die
  deterministischen Fake-Provider. **Es wurden keine echten API-Calls**
  (OpenAI/Anthropic/Azure/Firecrawl) ausgeführt.
- **Keine Aussage zu realen Modellkosten**: Dieser Report beweist die
  Mess-Pipeline (cost_status), er ist **keine Kostenrechnung**.
- `cost_chf=0.0` bedeutet **nie** automatisch "kostenlos": Summen
  werden ausschliesslich über `cost_status='priced'` gebildet;
  `unknown_price`/`not_applicable` tragen nie zu Summen bei.
- Die Preistabelle ist bewusst leer (Owner-Entscheid EVAL.1, keine
  Realpreise); jede künftige Preiszeile braucht source_url +
  last_checked.

## Abweichungen (dokumentiert)

- **docs/-Ausnahme**: M10-Konvention schreibt Summaries nur nach
  git-ignoriertem `var/` ("never to docs/", corr 5). Dieser eine
  deterministische Pipeline-Nachweis wird gemäss Ticket EVAL.1
  bewusst committet.
- **F1-Ableitung**: Kanonisches F1 ist confidential+deterministic_only
  (0 LLM-Calls). Der Smoke nutzt eine F1-abgeleitete synthetische
  D0-Variante (public/synthetic/cloud_assisted), damit die
  Metering-Pfade (Gateway + Web-Research) real durchlaufen werden.
- **Latenzen**: Wall-Clock-Werte würden den committeten Report bei
  jedem Lauf ändern — sie erscheinen hier nur gebucketed; exakte
  ms-Werte gibt der Smoke auf stdout aus.

## data_mode: `fake_test`

Abgeleitetes Label (kein Enforcement; Gates bleiben data_policy ×
provider_policy × policy_matrix).

## LLM-Calls (Fake-Gateway, Profil A1.project_fact_extraction)

| run_id | UsageRecords | input_tokens | output_tokens | cost_status | cost_chf (nur priced) |
| --- | --- | --- | --- | --- | --- |
| eval1-f1-run-1 | 1 | 11 | 22 | not_applicable=1 | 0.0 |
| eval1-f1-run-2 | 1 | 13 | 29 | not_applicable=1 | 0.0 |

## Pro agent_task

| run_id | agent_task | Invocations | Tokens (in/out) | Latenz | cost_statuses |
| --- | --- | --- | --- | --- | --- |
| eval1-f1-run-1 | A1.project_fact_extraction | 1 | 11/22 | gemessen (< 60000 ms) | not_applicable |
| eval1-f1-run-2 | A1.project_fact_extraction | 1 | 13/29 | gemessen (< 60000 ms) | not_applicable |

## Web-Research (Fake-Provider, Credits nativ)

Research-Task: `eval1-f1-task` · Provider: `fake`

| tool_id | Zeilen nach Status | Credits (nativ = gezählte ToolInvocations) |
| --- | --- | --- |
| search_public_professional_sources | running=1, succeeded=1 | 2 |

Credits werden als native Einheit gezählt (identische Semantik wie
`research/cost_guard.tool_calls_used`); keine spekulative CHF/USD-
Umrechnung (Owner-Entscheid EVAL.1).

---

Erzeugt mit `python scripts/run_eval_usage_smoke.py --case F1 --provider fake` gegen eine frische Temp-SQLite-DB über die
produktiven Grenzen (`gateway.invoke`, Research-Service/Executor).
